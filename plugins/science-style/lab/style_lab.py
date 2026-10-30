"""Command line of the style lab (spec section 6). Run `python3 lab/style_lab.py --help`.

Exit codes: 0 for success, 1 for a failed check or a network failure, 2 for a usage or input
error. Only the subcommands candidates, discover and fetch use the network.
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import lab_aggregate  # noqa: E402
import lab_card_check  # noqa: E402
import lab_checklist  # noqa: E402
import lab_fetch  # noqa: E402
import lab_http  # noqa: E402
import lab_openalex  # noqa: E402
import lab_paths  # noqa: E402
import lab_quotes  # noqa: E402
import lab_registry  # noqa: E402
import lab_sample  # noqa: E402
import lab_surface  # noqa: E402
import lab_venues  # noqa: E402


class UsageError(Exception):
    """A usage or input error. main() turns it into exit code 2."""


class NetworkError(Exception):
    """A network failure with the person id in the message. main() turns it into exit code 1."""


class ArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        raise UsageError(message)


def build_parser():
    parser = ArgumentParser(prog="style_lab.py", description="The style lab of the plugin science-style.")
    parser.add_argument("--registry", default=lab_registry.REGISTRY_PATH)
    parser.add_argument("--venues", default=lab_venues.VENUES_PATH)
    parser.add_argument("--checklist", default=lab_checklist.CHECKLIST_PATH)
    parser.add_argument("--wordlists", default=lab_surface.WORDLISTS_PATH)
    sub = parser.add_subparsers(dest="command", parser_class=ArgumentParser)
    candidates = sub.add_parser("candidates", help="list the OpenAlex author records for a name")
    candidates.add_argument("name")
    commands = {}
    for name, help_text in (("discover", "find the works of people"), ("sample", "draw the sample"),
                            ("fetch", "fetch the full texts"), ("normalize", "rebuild paper files from the cache"),
                            ("surface", "measure the surface layer"), ("select", "list the agreement or spot set"),
                            ("check-quotes", "check the quotes of the extractions"),
                            ("aggregate", "write the profile data")):
        commands[name] = sub.add_parser(name, help=help_text)
        if name == "select":
            commands[name].add_argument("kind", choices=("agreement", "spot"))
        commands[name].add_argument("people", nargs="*")
        commands[name].add_argument("--all", action="store_true")
        commands[name].add_argument("--pilot", action="store_true")
    for name in ("sample", "select"):
        commands[name].add_argument("--seed", type=int, default=lab_sample.DEFAULT_SEED)
    for name in ("sample", "aggregate"):
        commands[name].add_argument("--force", action="store_true")
    for name in ("discover", "fetch"):
        commands[name].add_argument("--refresh", action="store_true")
    commands["fetch"].add_argument("--only", default="")
    commands["check-quotes"].add_argument("--run", choices=lab_checklist.RUNS, default="main")
    check_card = sub.add_parser("check-card", help="check cards or the principles file")
    check_card.add_argument("targets", nargs="+")
    check_card.add_argument("--pilot", action="store_true")
    for name in ("quality", "status"):
        sub.add_parser(name, help="write the quality file" if name == "quality" else "show the state of each person") \
            .add_argument("--pilot", action="store_true")
    return parser


class Context(object):
    def __init__(self, args, environ, http_factory, out):
        self.args = args
        self.data = lab_paths.data_dir(environ)
        self.people = lab_registry.load_registry(args.registry)
        self.out = out
        self.http_factory = http_factory or (lambda cache, **kwargs: lab_http.Http(cache, **kwargs))

    def http(self, **kwargs):
        return self.http_factory(lab_paths.ensure_dir(self.data, "raw"), **kwargs)

    def say(self, text):
        self.out.write(text + "\n")
        self.out.flush()

    def pilot(self):
        return getattr(self.args, "pilot", False)

    def selected(self):
        if getattr(self.args, "all", False):
            return list(self.people)
        if not self.args.people:
            raise UsageError("name at least one person, or give --all")
        return [lab_registry.get_person(self.people, pid) for pid in self.args.people]

    def manifest_path(self, person_id):
        return os.path.join(lab_paths.manifests_dir(self.data, self.pilot()), person_id + ".json")

    def load_manifest(self, person_id):
        path = self.manifest_path(person_id)
        if not os.path.exists(path):
            raise UsageError("no manifest for {}: run sample first".format(person_id))
        return lab_paths.read_json(path)

    def profile_path(self, person_id, suffix=".json"):
        return os.path.join(lab_paths.profiles_dir(self.data, self.pilot()), person_id + suffix)

    def checklist(self):
        return lab_checklist.load_checklist(self.args.checklist)


def cmd_candidates(ctx):
    for row in lab_openalex.candidates(ctx.http(), ctx.args.name):
        ctx.say("{}\t{}\t{}\t{}\t{}".format(row["id"], row["orcid"], row["works_count"], row["name"],
                                            "; ".join(row["institutions"])))
    return 0


def cmd_discover(ctx):
    venues = lab_venues.load_venues(ctx.args.venues)
    http = ctx.http(refresh=ctx.args.refresh)
    for person in ctx.selected():
        result = lab_openalex.discover(http, person, venues)
        lab_paths.write_json(lab_paths.works_path(ctx.data, person["id"]), result)
        ctx.say("{}: {} works, {} papers, {} dropped, {} merged".format(
            person["id"], result["n_works"], len(result["papers"]), len(result["dropped"]), len(result["merged"])))
    return 0


def cmd_sample(ctx):
    venues = lab_venues.load_venues(ctx.args.venues)
    missing = [p["id"] for p in ctx.people if not os.path.exists(lab_paths.works_path(ctx.data, p["id"]))]
    if missing:
        raise UsageError("run discover first for: " + ", ".join(missing))
    chosen = ctx.selected()
    for person in chosen:
        path = ctx.manifest_path(person["id"])
        if os.path.exists(path) and not ctx.args.force:
            raise UsageError("{} exists; give --force to replace it".format(path))
    discoveries = {p["id"]: lab_paths.read_json(lab_paths.works_path(ctx.data, p["id"])) for p in ctx.people}
    lab_openalex.assign_shared(discoveries, ctx.people)
    for person in chosen:
        manifest = lab_sample.build_sample(person["id"], discoveries[person["id"]]["papers"], seed=ctx.args.seed,
                                           venues_version=venues.get("version"))
        lab_paths.write_json(ctx.manifest_path(person["id"]), manifest)
        ctx.say("{}: {} papers, shortfall {}".format(person["id"], manifest["n_papers"], manifest["shortfall"]))
        for cell, info in sorted(manifest["cells"].items()):
            ctx.say("  {}: pool {}, target {}, drawn {}".format(cell, info["pool"], info["target"], info["allocated"]))
    return 0


def cmd_fetch(ctx):
    http = ctx.http(refresh=ctx.args.refresh)
    only = set(w for w in ctx.args.only.split(",") if w) or None
    for person in ctx.selected():
        manifest = ctx.load_manifest(person["id"])
        works = lab_paths.read_json(lab_paths.works_path(ctx.data, person["id"]))
        lookup = {p["work_id"]: p for p in works["papers"]}
        try:
            counts = lab_fetch.fetch_person(http, manifest, ctx.manifest_path(person["id"]), ctx.data, lookup,
                                            only=only, log=ctx.say)
        except lab_http.FetchError as exc:
            raise NetworkError("{}: {}".format(person["id"], exc))
        ctx.say("{}: fetched {}, replaced {}, {} papers in the manifest".format(
            person["id"], counts["fetched"], counts["replaced"], manifest["n_papers"]))
    return 0


def cmd_normalize(ctx):
    http = ctx.http(offline=True)
    failures = 0
    for person in ctx.selected():
        for failure in lab_fetch.renormalize_person(http, ctx.load_manifest(person["id"]), ctx.data):
            ctx.say("{}: {} failed: {}".format(person["id"], failure["work_id"], failure["error"]))
            failures += 1
    return 1 if failures else 0


def _fetched(manifest):
    return [p for p in manifest["papers"] if p["status"] == "fetched"]


def cmd_surface(ctx):
    wordlists = lab_surface.load_wordlists(ctx.args.wordlists)
    selected = [person["id"] for person in ctx.selected()]
    manifests = {m["person"]: m for m in _manifests(ctx)}
    for person_id in selected:
        if person_id not in manifests:
            raise UsageError("no manifest for {}: run sample first".format(person_id))
    papers_by_person = {}
    for person_id, manifest in manifests.items():
        papers_by_person[person_id] = [lab_paths.read_json(lab_paths.paper_path(ctx.data, person_id, p["work_id"]))
                                       for p in _fetched(manifest)]
    folder = lab_paths.stage_dir(ctx.data, ctx.pilot(), "surface")
    for person_id, result in sorted(lab_surface.run_surface(papers_by_person, wordlists).items()):
        if person_id not in selected:
            continue
        lab_paths.write_json(os.path.join(folder, person_id + ".json"), result)
        note = "; " + result["distinctive_note"] if result["distinctive_note"] else ""
        ctx.say("{}: {} papers, {} sentences{}".format(person_id, result["n_papers"],
                                                       result["pooled"]["n_sentences"], note))
    return 0


def cmd_select(ctx):
    for person in ctx.selected():
        fetched = [p["work_id"] for p in _fetched(ctx.load_manifest(person["id"]))]
        if ctx.args.kind == "agreement":
            k = lab_sample.agreement_count(len(fetched))
        else:
            k = 1
        seed_text = "{}:{}:{}".format(ctx.args.seed, ctx.args.kind, person["id"])
        ctx.say("{}: {}".format(person["id"], " ".join(lab_sample.seeded_subset(fetched, k, seed_text))))
    return 0


def cmd_check_quotes(ctx):
    checklist = ctx.checklist()
    bad = 0
    for person in ctx.selected():
        checks = lab_quotes.check_person(ctx.data, ctx.load_manifest(person["id"]), checklist, ctx.args.run)
        for check in checks:
            bad += check["status"] != "ok"
            errors = ("; " + "; ".join(check["errors"][:3])) if check["errors"] else ""
            ctx.say("{} {} {} ({} of {} quotes failed){}".format(person["id"], check["work_id"], check["status"],
                                                                 len(check["failed"]), check["checked"], errors))
        ctx.say("{}: {} papers checked".format(person["id"], len(checks)))
    return 1 if bad else 0


def _manifests(ctx):
    paths = [ctx.manifest_path(p["id"]) for p in ctx.people]
    return [lab_paths.read_json(path) for path in paths if os.path.exists(path)]


def cmd_aggregate(ctx):
    checklist = ctx.checklist()
    stability = lab_aggregate.compute_stability(lab_aggregate.collect_pairs(ctx.data, _manifests(ctx), checklist),
                                                checklist)
    surface_dir = lab_paths.stage_dir(ctx.data, ctx.pilot(), "surface")
    digest_dir = lab_paths.stage_dir(ctx.data, ctx.pilot(), "digest")
    for person in ctx.selected():
        manifest = ctx.load_manifest(person["id"])
        checks = {c["work_id"]: c for c in lab_quotes.check_person(ctx.data, manifest, checklist)}
        extractions = {}
        for paper in _fetched(manifest):
            path = lab_paths.extraction_path(ctx.data, person["id"], paper["work_id"])
            if os.path.exists(path):
                extractions[paper["work_id"]] = lab_paths.read_json(path)
        surface_path = os.path.join(surface_dir, person["id"] + ".json")
        surface = lab_paths.read_json(surface_path) if os.path.exists(surface_path) else None
        profile = lab_aggregate.build_profile(person, manifest, extractions, checks, checklist, stability, surface)
        lab_paths.write_json_guarded(ctx.profile_path(person["id"]), profile, force=ctx.args.force)
        digest = lab_aggregate.build_digest(person["id"], manifest, extractions, checklist, profile["papers_used"])
        lab_paths.write_json(os.path.join(digest_dir, person["id"] + ".json"), digest)
        ctx.say("{}: {} papers used, {} left out, {} quotes".format(
            person["id"], profile["n_papers"], len(profile["left_out"]), len(profile["quotes"])))
    return 0


def _profiles(ctx):
    paths = [ctx.profile_path(p["id"]) for p in ctx.people]
    return [lab_paths.read_json(path) for path in paths if os.path.exists(path)]


def cmd_check_card(ctx):
    total = 0
    for target in ctx.args.targets:
        if target == "principles":
            kind, profiles = "principles", _profiles(ctx)
        else:
            lab_registry.get_person(ctx.people, target)
            if not os.path.exists(ctx.profile_path(target)):
                raise UsageError("no profile for {}: run aggregate first".format(target))
            kind, profiles = "card", [lab_paths.read_json(ctx.profile_path(target))]
        path = ctx.profile_path(target, ".md")
        if not os.path.exists(path):
            raise UsageError("no file " + path)
        with open(path, encoding="utf-8") as handle:
            failures = lab_card_check.check_text(handle.read(), kind, profiles)
        for failure in failures:
            ctx.say("{}: {}".format(target, failure))
        ctx.say("{}: {}".format(target, "{} failures".format(len(failures)) if failures else "passes"))
        total += len(failures)
    return 1 if total else 0


def cmd_quality(ctx):
    checklist = ctx.checklist()
    manifests = {m["person"]: m for m in _manifests(ctx)}
    profiles = _profiles(ctx)
    checks = {p["person"]: lab_quotes.check_person(ctx.data, manifests[p["person"]], checklist)
              for p in profiles if p["person"] in manifests}
    spot = {}
    for person in ctx.people:
        path = os.path.join(ctx.data, "spot", person["id"] + ".json")
        if os.path.exists(path):
            spot[person["id"]] = lab_paths.read_json(path)["marks"]
    report = lab_aggregate.quality_report(profiles, checks, spot, checklist)
    path = os.path.join(lab_paths.profiles_dir(ctx.data, ctx.pilot()), "quality.md")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(report)
    ctx.say("wrote " + path)
    return 0


def cmd_status(ctx):
    for person in ctx.people:
        pid = person["id"]
        works_path = lab_paths.works_path(ctx.data, pid)
        works = len(lab_paths.read_json(works_path)["papers"]) if os.path.exists(works_path) else 0
        manifest = lab_paths.read_json(ctx.manifest_path(pid)) if os.path.exists(ctx.manifest_path(pid)) else None
        fetched = _fetched(manifest) if manifest else []
        replaced = len(manifest["replacements"]) if manifest else 0
        extractions = sum(os.path.exists(lab_paths.extraction_path(ctx.data, pid, p["work_id"])) for p in fetched)
        ctx.say("{}: works {}, sample {}, fetched {}, replaced {}, extractions {}, profile {}, card {}".format(
            pid, works, manifest["n_papers"] if manifest else 0, len(fetched), replaced, extractions,
            "yes" if os.path.exists(ctx.profile_path(pid)) else "no",
            "yes" if os.path.exists(ctx.profile_path(pid, ".md")) else "no"))
    return 0


HANDLERS = {"candidates": cmd_candidates, "discover": cmd_discover, "sample": cmd_sample, "fetch": cmd_fetch,
            "normalize": cmd_normalize, "surface": cmd_surface, "select": cmd_select,
            "check-quotes": cmd_check_quotes, "aggregate": cmd_aggregate, "check-card": cmd_check_card,
            "quality": cmd_quality, "status": cmd_status}


def main(argv=None, http_factory=None, environ=None, out=None, err=None):
    out = out or sys.stdout
    err = err or sys.stderr
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
        if not args.command:
            raise UsageError("name a subcommand; see --help")
        ctx = Context(args, os.environ if environ is None else environ, http_factory, out)
        return HANDLERS[args.command](ctx)
    except SystemExit as exc:
        return 0 if exc.code in (0, None) else 2
    except (UsageError, lab_paths.PathError, lab_registry.RegistryError, lab_checklist.ChecklistError) as exc:
        err.write("error: {}\n".format(exc))
        return 2
    except (lab_http.FetchError, NetworkError) as exc:
        err.write("network error: {}\n".format(exc))
        return 1
    except (OSError, ValueError, KeyError) as exc:
        err.write("error: cannot read or parse a data file: {}\n".format(exc))
        return 2


if __name__ == "__main__":
    sys.exit(main())
