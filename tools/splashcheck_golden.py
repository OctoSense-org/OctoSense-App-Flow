#!/usr/bin/env python3
"""splashcheck golden corpus: the checker's findings over the real apps, compared.

The Splash checker (`splashcheck`, built from the OctoSense fork of Makepad)
decides what an app's faults are. Every change to it - and every change to an
app - moves those findings, and a moved finding nobody noticed is how a
refactor silently starts missing things. This runner pins the answer: it runs
the checker over the twelve real apps, renders each report as text and compares
it with the golden file committed beside it. A difference is a readable diff and
a non-zero exit, never a silent pass.

    python3 tools/splashcheck_golden.py                 # compare
    python3 tools/splashcheck_golden.py --update        # re-record
    python3 tools/splashcheck_golden.py --only mail     # one app

The corpus is the OctoSense shell's eleven system apps plus the AppCard
assistant. Neither is in this repository, so the runner expects a workspace
that holds the sibling checkouts beside this one:

    <workspace>/
      OctoSense-App-Flow/    this repository
      OctoSense/             the shell and its system apps: apps/<app>/bundle
      OctoSense-AppCard/     the AppCard assistant: bundle
      makepad/ splash-probe/ where the checker is built

Where that workspace is, in order: `--corpus-root`, `$OCTOSENSE_WORKSPACE`, then
this repository's parent directory. `docs/NATIVE-WORKSPACE.md` documents the
runtime workspace `tools/setup-native.py` prepares; the two app checkouts are
not part of it, which is why the corpus names its own layout above rather than
pointing at that one.

The checker is `splashcheck`, built from the OctoSense fork of Makepad:
`cargo build -p makepad-widgets --bin splashcheck --features maps`. It is found
in `$SPLASHCHECK`, then `splash-probe`, `makepad` or `Octoscript-Makepad` under
the workspace root (`target/release` before `target/debug`), then `$PATH` - the
order, and the `os.X_OK` test, that `tools/octo`'s `find_binary` applies to the
tools it wraps. Build it with the features of the host it checks for: this
corpus is recorded with `maps`, or the maps app reports a `MapView` its host
does have.

What the runner reads from the checker is one contract, and it is the checker's
own rather than this repository's invention: `--json`, whose shape `print_json`
in `widgets/src/splashcheck.rs` defines - `files[].bytes`,
`manifest_found`, `declares_net`, `capabilities`, `findings`, `notes` and
`fatal`; a finding's `severity`, `code`, `line`, `column` and `message`; and the
report's `tool` and `version` - together with the exit statuses `run` in the
same file returns, 0 nothing new, 1 a finding, 2 a usage or I/O problem. Both
were read from that source and confirmed against a recorded run of the binary;
the golden files in this directory are that run, so a change to either side of
the contract shows up here as a diff rather than as a surprise.

The thirteenth entry is the fn blind spot: `fn broken(){ let x = nope }`, a
fault inside a function nothing calls at the top level. The checker evaluates
top-level code only, so its golden records no findings - and that is the
measurement this corpus exists to make: when the checker starts evaluating
every `fn`, this golden changes and the diff says so.
[ADR 0002](../../docs/adr/0002-analysis-posture-and-one-suppression-rule.md)
makes this corpus the regression gate for that change: the fixture's expectation
flips from "no findings" to "findings", and every other app's diff must be empty
or explained. Re-record with `--update`, and name what moved in the commit and
the pull request - no CI runs this corpus, so the written-down run is the only
promise there is.

Exit status, the discipline `splashcheck` itself uses: 0 every golden matches,
1 at least one differs, 2 a setup problem - no checker binary, no corpus app,
no golden file to compare against.
"""
import argparse
import difflib
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import NamedTuple

REPO = Path(__file__).resolve().parent.parent
CORPUS = Path(__file__).resolve().parent / "splashcheck_corpus"
GOLDEN = CORPUS / "golden"

TOOL = "splashcheck_golden"

EXE = ".exe" if os.name == "nt" else ""

# The OctoSense shell's eleven system apps, as its README lists them. `wasmlab`
# also ships a bundle but is a lab rather than a system app, so it is not in the
# corpus: a golden is a claim about what the checker should say, and a lab app
# is free to be wrong on purpose.
SYSTEM_APPS = (
    "news", "photos", "maps", "camera", "mail", "calendar", "ai-providers",
    "youtube", "quickdeck", "pdftools", "writer",
)

EXIT_OK = 0
EXIT_DIFF = 1
EXIT_SETUP = 2

# The VM's "Did you mean" tail names each suggestion with its kind and an
# allocation counter: `width(obj653)`. The counter is a heap index, so it moves
# when anything ahead of it in the registry moves - a golden that kept it would
# churn on every unrelated refactor and bury the change a reader came to see.
OBJECT_ID = re.compile(r"\(obj\d+\)")


class SetupError(Exception):
    """A problem with the inputs rather than the comparison: exit 2."""


def workspace_root(explicit=None):
    """The directory holding the sibling repositories. See the module docstring."""
    if explicit:
        return Path(explicit)
    return Path(os.environ.get("OCTOSENSE_WORKSPACE") or REPO.parent)


def corpus(root):
    """Every bundle the corpus checks, as (name, path), in a stable order."""
    entries = [("appcard", root / "OctoSense-AppCard" / "bundle")]
    entries += [(name, root / "OctoSense" / "apps" / name / "bundle") for name in SYSTEM_APPS]
    # The blind-spot fixture ships in this repository, so it is checked wherever
    # the checker is.
    entries.append(("fn-blindspot", CORPUS / "fn-blindspot"))
    return sorted(entries)


def checker_candidates(root):
    """Where a `splashcheck` binary may be, in the order the module docstring gives.

    Each item is the path searched, not only the ones that exist: a reader told
    the binary is missing needs to see where the runner looked, which is what
    `tools/octo`'s `need` prints for the tools it wraps.
    """
    from_env = os.environ.get("SPLASHCHECK")
    if from_env:
        yield f"$SPLASHCHECK={from_env}", Path(from_env)
    # `splash-probe` first: it is the standalone package that adopts
    # `makepad-widgets` as a path dependency and builds the checker with the
    # host's features, which is the build this corpus is recorded against.
    for project in ("splash-probe", "makepad", "Octoscript-Makepad"):
        for profile in ("release", "debug"):
            path = root / project / "target" / profile / f"splashcheck{EXE}"
            yield str(path), path


def find_checker(explicit=None, root=None):
    """The checker binary and where it was found, or `(None, searched)`.

    `os.X_OK`, not `is_file`: a candidate that exists but is not executable is
    not a checker, and picking it anyway would turn into an `OSError` from
    `subprocess` rather than into the exit 2 this tool owes its caller.
    """
    if explicit:
        path = Path(explicit)
        if path.is_file() and os.access(path, os.X_OK):
            return path, [str(path)]
        return None, [str(path)]
    searched = []
    for label, candidate in checker_candidates(root or workspace_root()):
        searched.append(label)
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate, searched
    on_path = shutil.which("splashcheck")
    searched.append("PATH (splashcheck)")
    if on_path:
        return Path(on_path), searched
    return None, searched


def run_checker(checker, bundle):
    """One checker invocation over one bundle: its JSON report.

    The JSON is the contract (`--json` is the machine face of the same analysis
    the human output prints), and bytes are decoded as UTF-8 rather than with
    the platform locale: a message quoting an app's own text is UTF-8 wherever
    this runs.
    """
    try:
        proc = subprocess.run(
            [str(checker), "--json", str(bundle)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except OSError as error:
        # A path that will not run: no permission, not an executable at all.
        raise SetupError(f"{checker} will not run: {error}")
    if proc.returncode == EXIT_SETUP:
        raise SetupError(f"{checker} refused {bundle}: {proc.stderr.decode('utf-8', 'replace').strip()}")
    try:
        return json.loads(proc.stdout.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as error:
        raise SetupError(f"{checker} said nothing usable about {bundle}: {error}")
def app_id(bundle):
    """The app's own id, as its manifest declares it."""
    path = bundle / "manifest.json"
    if not path.is_file():
        return "none"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, ValueError):
        return "unreadable"
    return str(value.get("id") or "none")


def bundle_digest(bundle):
    """A digest of the bundle's `.splash` files and its manifest.

    Recorded in the golden so that a changed app says so. Without it, a diff
    after an app update reads as a checker regression, and the reader cannot
    tell which of the two moved.

    Those files and no others, because they are the checker's whole input: it
    evaluates the `.splash` files it scans and reads the manifest's
    declarations, so nothing else in a bundle - an icon, a `tools.json`, a
    screenshot - can move a finding. A bundle file that changes without moving
    a finding therefore leaves the golden alone, which is the point.
    """
    digest = hashlib.sha256()
    for path in sorted(bundle.rglob("*"), key=lambda p: p.as_posix()):
        if not path.is_file():
            continue
        relative = path.relative_to(bundle).as_posix()
        if path.suffix != ".splash" and relative != "manifest.json":
            continue
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def relative_to_bundle(bundle, path_text):
    """A report's file path as a path inside its bundle, never as a checkout path."""
    path = Path(path_text)
    try:
        return path.relative_to(bundle).as_posix()
    except ValueError:
        return path.name


def scrub(text, bundle):
    """Take the bundle's own path out of a message, so a golden is checkout-free."""
    for spelling in (str(bundle), str(bundle).replace("\\", "/")):
        text = text.replace(spelling, "<bundle>")
    return text


def finding_message(finding):
    """A finding's message, with the VM's allocation counters taken out."""
    return OBJECT_ID.sub("(obj)", finding.get("message") or "")


def finding_key(finding):
    """Findings are ordered, not listed: a golden must not depend on report order."""
    return (finding.get("line") or 0, finding.get("column") or 0, finding.get("code") or "", finding_message(finding))


def finding_line(finding):
    """One finding as a golden line: `3:17 error splash.eval <message>`."""
    at = ""
    if finding.get("line"):
        at = f"{finding['line']}:{finding.get('column') or 0} "
    return f"{at}{finding.get('severity')} {finding.get('code')} {finding_message(finding)}"


def render(bundle, report):
    """One bundle's report as the text its golden file holds."""
    lines = [
        f"# {TOOL} golden corpus",
        f"# checker: {report.get('tool', '?')} {report.get('version', '?')}",
        f"app {app_id(bundle)}",
        f"digest {bundle_digest(bundle)}",
    ]
    files = sorted(report.get("files") or [], key=lambda entry: entry.get("path") or "")
    for entry in files:
        lines.append(f"file {relative_to_bundle(bundle, entry.get('path') or '')}")
        lines.append(f"bytes {entry.get('bytes', 0)}")
        lines.append(f"manifest {'found' if entry.get('manifest_found') else 'missing'}")
        lines.append(f"declares {'net' if entry.get('declares_net') else 'no net'}")
        lines.append("capabilities " + (", ".join(entry.get("capabilities") or []) or "none"))
        findings = sorted(entry.get("findings") or [], key=finding_key)
        lines.append(f"findings {len(findings)}")
        lines += [f"  {finding_line(finding)}" for finding in findings]
        notes = list(entry.get("notes") or [])
        lines.append(f"notes {len(notes)}")
        lines += [f"  {note}" for note in notes]
        if entry.get("fatal"):
            lines.append("fatal " + scrub(str(entry["fatal"]), bundle))
    return "\n".join(lines) + "\n"


def finding_count(report):
    """How many findings the whole run carries, for the one-line status."""
    return sum(len(entry.get("findings") or []) for entry in report.get("files") or [])


def display(path):
    """A path as a reader would type it: relative to the working directory."""
    path = Path(path)
    try:
        return path.resolve().relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def setup_error(message):
    print(f"{TOOL}: {message}", file=sys.stderr)
    return EXIT_SETUP


def parse(argv):
    parser = argparse.ArgumentParser(
        prog=TOOL,
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--update", action="store_true", help="re-record the golden files instead of comparing them")
    parser.add_argument("--corpus-root", type=Path, help="the workspace holding OctoSense/ and OctoSense-AppCard/")
    parser.add_argument("--checker", help="the splashcheck binary to run")
    parser.add_argument("--golden-dir", type=Path, help=f"where the golden files live (default: {display(GOLDEN)})")
    parser.add_argument("--only", action="append", metavar="APP", help="one corpus app, by name; repeatable")
    return parser.parse_args(argv)


class Recorded(NamedTuple):
    """One bundle's golden text, with the name and count a reader wants first."""

    name: str
    path: Path
    text: str
    findings: int


def main(argv=None):
    args = parse(argv)
    golden_dir = args.golden_dir or GOLDEN
    root = workspace_root(args.corpus_root)

    entries = corpus(root)
    if args.only:
        known = {name for name, _ in entries}
        unknown = [name for name in args.only if name not in known]
        if unknown:
            return setup_error(f"no corpus app {unknown[0]!r}: {', '.join(sorted(known))}")
        wanted = set(args.only)
        entries = [entry for entry in entries if entry[0] in wanted]

    checker, searched = find_checker(args.checker, root)
    if checker is None:
        if args.checker:
            return setup_error(f"no splashcheck binary at {args.checker}")
        return setup_error(
            "no splashcheck binary. Searched:\n  " + "\n  ".join(searched)
            + f"\nSet $SPLASHCHECK, or build it with `cargo build -p makepad-widgets"
              f" --bin splashcheck --features maps` in a sibling checkout under {root}."
        )
    for name, path in entries:
        if not path.is_dir():
            return setup_error(
                f"no corpus app {name!r}: {path} is not a directory "
                f"(the workspace root is {root}: --corpus-root or $OCTOSENSE_WORKSPACE)"
            )

    recorded = []
    for name, path in entries:
        try:
            report = run_checker(checker, path)
        except SetupError as error:
            return setup_error(f"{name}: {error}")
        recorded.append(Recorded(name, path, render(path, report), finding_count(report)))

    if args.update:
        golden_dir.mkdir(parents=True, exist_ok=True)
        for entry in recorded:
            (golden_dir / f"{entry.name}.txt").write_text(entry.text, encoding="utf-8")
            print(f"  rec  {entry.name} - {entry.findings} finding(s)")
        print(f"{TOOL}: wrote {len(recorded)} golden file(s) to {display(golden_dir)}")
        return EXIT_OK

    changed = 0
    for entry in recorded:
        golden_path = golden_dir / f"{entry.name}.txt"
        if not golden_path.is_file():
            return setup_error(f"no golden file for {entry.name!r}: {display(golden_path)} (record it with --update)")
        expected = golden_path.read_text(encoding="utf-8")
        if expected == entry.text:
            print(f"  ok   {entry.name} - {entry.findings} finding(s)")
            continue
        changed += 1
        print(f"  DIFF {entry.name} - {entry.findings} finding(s)")
        for line in difflib.unified_diff(
            expected.splitlines(), entry.text.splitlines(),
            fromfile=f"golden/{entry.name}.txt", tofile="current", n=3, lineterm="",
        ):
            print(line)
    print(f"{TOOL}: {len(recorded) - changed} ok, {changed} changed")
    return EXIT_DIFF if changed else EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
