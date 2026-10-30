"""HTTP for the style lab: a disk cache, a minimum interval per host, and retries.

No request carries an email address. The user agent names the tool and the repository. Only the
subcommands candidates, discover and fetch make requests. The normalize step uses offline mode,
which reads the cache and never makes a request.
"""
import hashlib
import http.client
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

USER_AGENT = "science-style-lab/0.1 (+https://github.com/yangjun9095/claude-plugins)"
MIN_INTERVAL = {
    "api.openalex.org": 0.2,
    "eutils.ncbi.nlm.nih.gov": 0.4,
    "www.ebi.ac.uk": 0.2,
    "api.biorxiv.org": 1.0,
    "www.biorxiv.org": 1.0,
    "www.medrxiv.org": 1.0,
    "arxiv.org": 3.0,
}
DEFAULT_INTERVAL = 1.0
RETRY_STATUSES = frozenset([429, 500, 502, 503, 504])


class FetchError(Exception):
    """A request failed for good. status is the HTTP status, or None for a network error."""

    def __init__(self, url, status, message):
        Exception.__init__(self, "{} ({}): {}".format(url, status, message))
        self.url = url
        self.status = status


class Response(object):
    def __init__(self, url, status, body, from_cache):
        self.url = url
        self.status = status
        self.body = body
        self.from_cache = from_cache

    def json(self):
        return json.loads(self.body.decode("utf-8"))


def urllib_opener(url, headers, timeout):
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.getcode(), response.read()


class Http(object):
    def __init__(self, cache_dir, opener=urllib_opener, clock=time.monotonic, sleep=time.sleep,
                 refresh=False, offline=False, retries=3, timeout=60):
        self.cache_dir = cache_dir
        self.opener = opener
        self.clock = clock
        self.sleep = sleep
        self.refresh = refresh
        self.offline = offline
        self.retries = retries
        self.timeout = timeout
        self._last = {}

    def cache_paths(self, url):
        """Return the paths of the cached body and of its sidecar file."""
        host = urllib.parse.urlparse(url).netloc or "unknown"
        key = hashlib.sha1(url.encode("utf-8")).hexdigest()
        folder = os.path.join(self.cache_dir, host)
        return os.path.join(folder, key), os.path.join(folder, key + ".json")

    def get(self, url, retries=None):
        """Return the Response for url from the cache or the network, or raise FetchError."""
        body_path, meta_path = self.cache_paths(url)
        cached = os.path.exists(body_path) and os.path.exists(meta_path)
        if cached and (self.offline or not self.refresh):
            with open(body_path, "rb") as handle:
                return Response(url, 200, handle.read(), True)
        if self.offline:
            raise FetchError(url, None, "not in the cache, and offline mode makes no request")
        limit = self.retries if retries is None else retries
        attempt = 0
        while True:
            self._wait(url)
            message = ""
            try:
                status, body = self.opener(url, {"User-Agent": USER_AGENT}, self.timeout)
            except urllib.error.HTTPError as err:
                status, body, message = err.code, b"", str(err)
            except (OSError, http.client.HTTPException) as err:
                status, body, message = None, b"", str(err)
            if status == 200:
                self._store(url, body_path, meta_path, body)
                return Response(url, 200, body, False)
            if (status is not None and status not in RETRY_STATUSES) or attempt >= limit:
                raise FetchError(url, status, message or "HTTP status {}".format(status))
            attempt += 1
            self.sleep(2 ** attempt)

    def _wait(self, url):
        host = urllib.parse.urlparse(url).netloc
        interval = MIN_INTERVAL.get(host, DEFAULT_INTERVAL)
        last = self._last.get(host)
        if last is not None:
            gap = interval - (self.clock() - last)
            if gap > 0:
                self.sleep(gap)
        self._last[host] = self.clock()

    def _store(self, url, body_path, meta_path, body):
        os.makedirs(os.path.dirname(body_path), exist_ok=True)
        with open(body_path, "wb") as handle:
            handle.write(body)
        with open(meta_path, "w", encoding="utf-8") as handle:
            json.dump({"url": url, "status": 200, "date": time.strftime("%Y-%m-%d")}, handle)
