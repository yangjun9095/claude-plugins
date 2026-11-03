"""Tests for lab/lab_http.py. No test uses the network."""
import os
import socket
import ssl
import sys
import tempfile
import unittest
import urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "lab"))
sys.path.insert(0, HERE)

import lab_http as lh  # noqa: E402


class FakeClock(object):
    def __init__(self):
        self.now = 100.0
        self.sleeps = []

    def clock(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(round(seconds, 3))
        self.now += seconds


class FakeOpener(object):
    """Answers each URL from a list of scripted results: (status, body) or an exception."""

    def __init__(self, script):
        self.script = {url: list(results) for url, results in script.items()}
        self.calls = []

    def __call__(self, url, headers, timeout):
        self.calls.append((url, headers, timeout))
        result = self.script[url].pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def http_error(url, code, headers=None):
    return urllib.error.HTTPError(url, code, "status {}".format(code), headers or {}, None)


class HttpTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.clock = FakeClock()

    def make(self, script, **kwargs):
        opener = FakeOpener(script)
        http = lh.Http(self.tmp.name, opener=opener, clock=self.clock.clock, sleep=self.clock.sleep, **kwargs)
        return http, opener

    def test_a_200_answer_is_cached_and_read_back_without_a_request(self):
        url = "https://api.openalex.org/works?x=1"
        http, opener = self.make({url: [(200, b'{"a": 1}')]})
        first = http.get(url)
        second = http.get(url)
        self.assertEqual(first.json(), {"a": 1})
        self.assertFalse(first.from_cache)
        self.assertTrue(second.from_cache)
        self.assertEqual(second.body, b'{"a": 1}')
        self.assertEqual(len(opener.calls), 1)

    def test_refresh_downloads_again(self):
        url = "https://api.openalex.org/works?x=2"
        http, opener = self.make({url: [(200, b"1"), (200, b"2")]})
        http.get(url)
        fresh = lh.Http(self.tmp.name, opener=opener, clock=self.clock.clock, sleep=self.clock.sleep, refresh=True)
        self.assertEqual(fresh.get(url).body, b"2")
        self.assertEqual(len(opener.calls), 2)

    def test_offline_mode_reads_the_cache_and_refuses_a_missing_url(self):
        url = "https://arxiv.org/html/0000.00001"
        http, opener = self.make({url: [(200, b"<html></html>")]})
        http.get(url)
        offline = lh.Http(self.tmp.name, opener=opener, offline=True)
        self.assertEqual(offline.get(url).body, b"<html></html>")
        with self.assertRaises(lh.FetchError) as ctx:
            offline.get("https://arxiv.org/html/0000.00002")
        self.assertIn("not in the cache", str(ctx.exception))
        self.assertEqual(len(opener.calls), 1)

    def test_requests_to_one_host_wait_for_the_interval(self):
        a, b = "https://api.openalex.org/a", "https://api.openalex.org/b"
        http, _ = self.make({a: [(200, b"a")], b: [(200, b"b")]})
        http.get(a)
        http.get(b)
        self.assertEqual(self.clock.sleeps, [0.2])

    def test_arxiv_waits_three_seconds_and_other_hosts_do_not_wait_for_it(self):
        a, b, c = "https://arxiv.org/html/1", "https://arxiv.org/html/2", "https://api.biorxiv.org/x"
        http, _ = self.make({a: [(200, b"a")], b: [(200, b"b")], c: [(200, b"c")]})
        http.get(a)
        http.get(c)
        http.get(b)
        self.assertEqual(self.clock.sleeps, [3.0])

    def test_a_500_is_retried_with_backoff(self):
        url = "https://eutils.ncbi.nlm.nih.gov/x"
        http, opener = self.make({url: [http_error(url, 500), (200, b"ok")]})
        self.assertEqual(http.get(url).body, b"ok")
        self.assertEqual(len(opener.calls), 2)
        self.assertIn(2, self.clock.sleeps)

    def test_a_429_waits_for_the_retry_after_seconds(self):
        url = "https://www.biorxiv.org/content/early/2020/01/01/222222.source.xml"
        http, opener = self.make({url: [http_error(url, 429, {"Retry-After": "47"}), (200, b"ok")]})
        self.assertEqual(http.get(url).body, b"ok")
        self.assertEqual(self.clock.sleeps, [47])

    def test_a_long_retry_after_is_capped_at_120_seconds(self):
        url = "https://www.biorxiv.org/content/early/2020/01/01/333333.source.xml"
        http, opener = self.make({url: [http_error(url, 429, {"retry-after": "500"}), (200, b"ok")]})
        self.assertEqual(http.get(url).body, b"ok")
        self.assertEqual(self.clock.sleeps, [120])

    def test_a_429_without_a_numeric_retry_after_backs_off(self):
        url = "https://api.biorxiv.org/details/biorxiv/10.1101/222222"
        date = "Wed, 21 Oct 2026 07:28:00 GMT"
        http, opener = self.make({url: [http_error(url, 429), http_error(url, 429, {"Retry-After": date}),
                                        (200, b"ok")]})
        self.assertEqual(http.get(url).body, b"ok")
        self.assertEqual(self.clock.sleeps, [2, 4])

    def test_a_retry_after_on_a_503_does_not_replace_the_backoff(self):
        url = "https://eutils.ncbi.nlm.nih.gov/y"
        http, opener = self.make({url: [http_error(url, 503, {"Retry-After": "47"}), (200, b"ok")]})
        self.assertEqual(http.get(url).body, b"ok")
        self.assertEqual(self.clock.sleeps, [2])

    def test_the_preprint_web_hosts_wait_five_seconds_and_the_apis_one(self):
        self.assertEqual(lh.MIN_INTERVAL["www.biorxiv.org"], 5.0)
        self.assertEqual(lh.MIN_INTERVAL["www.medrxiv.org"], 5.0)
        self.assertEqual(lh.MIN_INTERVAL["api.biorxiv.org"], 1.0)
        self.assertEqual(lh.MIN_INTERVAL["api.medrxiv.org"], 1.0)
        a, b = "https://www.medrxiv.org/a.xml", "https://www.medrxiv.org/b.xml"
        http, _ = self.make({a: [(200, b"a")], b: [(200, b"b")]})
        http.get(a)
        http.get(b)
        self.assertEqual(self.clock.sleeps, [5.0])

    def test_a_404_fails_at_once(self):
        url = "https://www.ebi.ac.uk/x"
        http, opener = self.make({url: [http_error(url, 404)]})
        with self.assertRaises(lh.FetchError) as ctx:
            http.get(url)
        self.assertEqual(ctx.exception.status, 404)
        self.assertEqual(len(opener.calls), 1)

    def test_retries_can_be_limited_per_call(self):
        url = "https://www.ebi.ac.uk/europepmc/webservices/rest/PMC1/fullTextXML"
        http, opener = self.make({url: [http_error(url, 500), http_error(url, 500), (200, b"never")]})
        with self.assertRaises(lh.FetchError) as ctx:
            http.get(url, retries=1)
        self.assertEqual(ctx.exception.status, 500)
        self.assertEqual(len(opener.calls), 2)

    def test_network_errors_are_retried(self):
        url = "https://api.biorxiv.org/y"
        http, opener = self.make({url: [urllib.error.URLError("down"), socket.timeout("slow"), (200, b"ok")]})
        self.assertEqual(http.get(url).body, b"ok")
        self.assertEqual(len(opener.calls), 3)

    def test_ssl_errors_are_retried_then_raise_fetch_error(self):
        url = "https://api.biorxiv.org/ssl"
        http, opener = self.make({url: [ssl.SSLError("eof"), ssl.SSLError("eof")]})
        with self.assertRaises(lh.FetchError) as ctx:
            http.get(url, retries=1)
        self.assertIsNone(ctx.exception.status)
        self.assertEqual(len(opener.calls), 2)

    def test_a_failed_answer_is_not_cached(self):
        url = "https://api.openalex.org/z"
        http, opener = self.make({url: [http_error(url, 404), (200, b"later")]})
        with self.assertRaises(lh.FetchError):
            http.get(url)
        self.assertEqual(http.get(url).body, b"later")

    def test_the_user_agent_names_the_repository_and_holds_no_email(self):
        url = "https://api.openalex.org/ua"
        http, opener = self.make({url: [(200, b"x")]})
        http.get(url)
        agent = opener.calls[0][1]["User-Agent"]
        self.assertIn("github.com/yangjun9095/claude-plugins", agent)
        self.assertNotIn("@", agent)

    def test_the_cache_keeps_a_sidecar_with_the_url(self):
        url = "https://api.openalex.org/side"
        http, _ = self.make({url: [(200, b"x")]})
        http.get(url)
        body_path, meta_path = http.cache_paths(url)
        self.assertTrue(os.path.exists(body_path))
        with open(meta_path, encoding="utf-8") as handle:
            self.assertIn(url, handle.read())


if __name__ == "__main__":
    unittest.main()
