#!/usr/bin/env python3
"""uitest: run a Splash script app's scenarios in card-host, the way a backend runs unit tests.

    uitest.py run <bundle> <scenario.json | directory> [--card-host PATH] [--out DIR] [--keep-going]
    uitest.py doctor [--card-host PATH]

A scenario is a JSON file: the host-service replies the app gets, files to put
in its storage jail before it starts, the window sizes to test, and steps that
act on the app and check what it shows. See references/SCENARIOS.md.

For each scenario and size the runner:

1. copies the bundle and prepends a fake `host` to the copy's `main.splash`
   (the source under test is otherwise byte-for-byte the original), so every
   `host.request` gets the scenario's reply instead of needing a real service;
2. starts card-host on the copy with a remote-control port, hidden, and on
   Linux under a private Xvfb display when there is none;
3. drives the steps through the remote routes (`/snap`, `/click`, `/t`, `/k`,
   `/m`), checks each expectation against the widget list, the calls the app
   made, the files in its jail and the runtime log;
4. on the first failure, writes the evidence and FEEDBACK.md: a repair request
   in the shape docs/MODEL-VALIDATION.md asks for, scoped to that one failure.

It never edits the bundle under test. Exit status: 0 all passed, 1 a scenario
failed, 2 the environment or a scenario file is broken.

Python 3.9+, standard library only.
"""
import argparse
import hashlib
import json
import math
import os
import re
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL = HERE.parent
DEFAULT_SIZE = "412x892"
RUNTIME_ERROR_MARKERS = ("[E] splash", "on_render closure failed", "splash host callback error",
                         "isolate panic", "card-host: refused",
                         # Runtimes before makepad a772b370 (Rinx still ships one) stop a heap
                         # whose instruction budget is spent, in these words:
                         "spent its instruction budget", "instruction budget is spent")
SHIM_BEGIN = "// ---- uitest fake host: test copy only ----"
SHIM_END = "// ---- end uitest fake host ----"
CALL_MARK = "UITEST_CALL_"     # + run nonce: one line per host.request in the card-host log
READY_MARK = "UITEST_READY_"   # + run nonce: the fake host is installed
RUNNER_VERSION = 3

# How a host treats a request for a service the manifest does not name.
#   octosense: capability names are disclosures, not gates (App Hub e1fdf28,
#              makepad d653bc44); the request is answered and the runner
#              reports the missing declaration.
#   rinx:      Rinx grants a mini-app only the services it was granted and
#              refuses the rest with this text (Rinx crates/miniapp-core/src/lib.rs:103).
HOST_PROFILES = ("octosense", "rinx")
RINX_REFUSAL = "Mini app was not granted "
HOST_WIDGETS = ("Window", "KeyboardView", "Splash")

# Every key a scenario may use. An unknown key is a typo, and a typo that the
# runner ignored would make a check pass without running.
SCENARIO_KEYS = {"name", "description", "note", "use", "host", "storage", "steps", "sizes", "size", "viewport",
                 "startup_timeout", "fake_host", "allow_runtime_errors", "host_profile"}
STEP_ACTIONS = {"click", "type", "key", "scroll", "scroll_to", "sleep", "expect", "wait"}
STEP_MODIFIERS = {"click": {"note", "allow_runtime_errors"},
                  "type": {"note", "allow_runtime_errors"},
                  "key": {"note", "allow_runtime_errors"},
                  "scroll": {"note", "allow_runtime_errors"},
                  "scroll_to": {"on", "max", "note", "allow_runtime_errors"},
                  "sleep": {"note", "allow_runtime_errors"},   # errors are checked after every step
                  "expect": {"timeout", "note", "allow_runtime_errors"},
                  "wait": {"timeout", "note", "allow_runtime_errors"}}
EXPECT_KEYS = {"text", "absent", "in_view", "enabled", "disabled", "count", "calls", "files"}
SELECTOR_KEYS = {"id", "type", "text", "contains", "after", "nth"}
CALL_KEYS = {"service", "count", "contains", "excludes"}
COUNT_KEYS = {"of", "n"}
FILE_KEYS = {"name", "missing", "contains"}
TYPE_KEYS = {"into", "text", "clear"}
SCROLL_KEYS = {"on", "dy"}
REPLY_FORMS = ("data", "error", "never")
REPLY_KEYS = set(REPLY_FORMS) | {"delay", "note"}
# A part may hold fixtures (taken with "use") and steps (taken with "run"); a
# part does not take other parts, and a typo in one is refused like anywhere else.
PART_KEYS = SCENARIO_KEYS - {"use"}
# Any time in a scenario is seconds, at most this: a larger number is almost
# always milliseconds, and an unbounded one can overflow a wait or never end.
MAX_SECONDS = 600
MAX_SCROLLS = 1000
MAX_DEPTH = 64          # nesting of a scenario file, fixtures included
MAX_AFTER = 8           # selectors chained with "after"


class ScenarioError(Exception):
    """The scenario file itself is wrong (not the app)."""


class EvidenceError(RuntimeError):
    """The runner cannot read its own evidence (the call log): neither a pass nor the app's fault."""


class StepFailed(Exception):
    def __init__(self, expected, actual, detail=None):
        super().__init__(expected)
        self.expected = expected
        self.actual = actual
        self.detail = detail or {}


class PendingEvidence(StepFailed):
    """Evidence still being written: a wait retries, a final read must not accept it."""


# --------------------------------------------------------------- fake host
def splash_string(text):
    """A Splash double-quoted string literal for any text."""
    out = ['"']
    for ch in text:
        if ch == "\\":
            out.append("\\\\")
        elif ch == '"':
            out.append('\\"')
        elif ch == "\n":
            out.append("\\n")
        elif ch == "\r":
            out.append("\\r")
        elif ch == "\t":
            out.append("\\t")
        else:
            out.append(ch)
    out.append('"')
    return "".join(out)


def normalise_replies(host):
    """{service: reply | [reply, ...]} -> [{service, replies: [reply...]}] with full reply objects.

    A reply is exactly one of {"data": …}, {"error": "…"} or {"never": true},
    with an optional "delay" in seconds. A host answers every request once
    (SCRIPT-API: host services), so there is no form that calls back twice.
    """
    if not isinstance(host, dict):
        raise ScenarioError(f"\"host\" is an object of replies by service, got {_short(host)}")
    out = []
    for service, value in host.items():
        if not isinstance(service, str) or not service.strip():
            raise ScenarioError(f"host: a service name is a non-empty string, got {service!r}")
        where = f"host reply for {service!r}"
        items = value if isinstance(value, list) else [value]
        if not items:
            raise ScenarioError(f"host replies for {service!r} are an empty list")
        replies = []
        for item in items:
            if not isinstance(item, dict):
                raise ScenarioError(f"{where} must be an object with \"data\", \"error\" or \"never\", "
                                    f"got {_short(item)}")
            if "stream" in item:
                raise ScenarioError(f"{where}: a host answers each request once; \"stream\" is not a reply form")
            _unknown(item, REPLY_KEYS, where, "reply")
            if len([k for k in REPLY_FORMS if k in item]) != 1:
                raise ScenarioError(f"{where} has exactly one of \"data\", \"error\" or \"never\", got {_short(item)}")
            _need("error" not in item or isinstance(item["error"], str), where, "\"error\" is the error text")
            _need("never" not in item or item["never"] is True, where,
                  "\"never\" is true; leave it out for a reply that comes")
            delay = item.get("delay", 0.05)
            _need(_seconds(delay), where, f"\"delay\" is a number of seconds from 0 to {MAX_SECONDS}")
            if "error" in item:
                reply = {"is_ok": False, "data": None, "error": item["error"]}
            else:
                reply = {"is_ok": True, "data": item.get("data"), "error": ""}
            replies.append({"never": "never" in item, "delay": float(delay), "reply": reply})
        out.append({"service": service, "replies": replies})
    return out


def shim_source(host, profile="octosense", declared=(), nonce="0"):
    """The fake host prepended to the test copy.

    `declared` is the manifest's capability list; `profile` says what a request
    for an undeclared service gets (see HOST_PROFILES). Every call is printed
    to card-host's log as one line, `UITEST_CALL_<nonce> {json}`, with whether
    it was declared. The log is the host's channel, not the app's storage, so
    the app keeps exactly its own permissions, files and quota. The nonce is
    new for every run, so the app cannot write a line the runner would take
    for a call. A ready line is printed first: without it, the call evidence
    is missing, never "no calls".
    """
    if profile not in HOST_PROFILES:
        raise ScenarioError(f"host_profile must be one of {list(HOST_PROFILES)}, got {profile!r}")
    fixtures = json.dumps({"services": normalise_replies(host), "profile": profile, "declared": list(declared)},
                          ensure_ascii=False)
    return f"""{SHIM_BEGIN}
let uitest_real_host = host
let uitest_fx = {splash_string(fixtures)}.parse_json()
let uitest_asked = []
print("{READY_MARK}{nonce}\\n")
fn uitest_later(callback, reply, delay){{ start_timeout(delay, || callback(reply)) }}
fn uitest_answer(service, nth){{
    let fallback = nil
    for entry in uitest_fx.services {{
        if entry.service == service {{
            let k = nth
            if k >= entry.replies.len() {{ k = entry.replies.len() - 1 }}
            return entry.replies[k]
        }}
        if entry.service == "*" {{ fallback = entry.replies[0] }}
    }}
    if fallback != nil {{ return fallback }}
    let family = service.split(".")[0]
    {{never: false, delay: 0.05, reply: {{is_ok: false, data: nil, error: "no service answers \\"" + family + "\\" on this device"}}}}
}}
fn uitest_declared(service){{
    let family = service.split(".")[0]
    for c in uitest_fx.declared {{ if c == family || c == service {{ return true }} }}
    false
}}
let uitest_seq = 0
let host = {{request: fn(service, args, callback){{
    let nth = 0
    for c in uitest_asked {{ if c == service {{ nth += 1 }} }}
    uitest_asked.push(service)
    uitest_seq += 1
    let declared = uitest_declared(service)
    print("{CALL_MARK}{nonce} " + {{seq: uitest_seq, service: service, args: args, at: time_now(), declared: declared}}.to_json() + "\\n")
    // Rinx answers only the services a mini-app was granted; an OctoSense
    // host treats the manifest as a disclosure and answers anyway.
    if !declared && uitest_fx.profile == "rinx" {{
        uitest_later(callback, {{is_ok: false, data: nil, error: "{RINX_REFUSAL}" + service}}, 0.0)
        return uitest_seq
    }}
    let answer = uitest_answer(service, nth)
    if !answer.never {{ uitest_later(callback, answer.reply, answer.delay) }}
    uitest_seq
}}, has: fn(name){{ uitest_real_host.has(name) }}, capabilities: fn(){{ uitest_fx.declared }}}}
{SHIM_END}
"""


def check_app_id(app_id):
    if not isinstance(app_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", app_id) or ".." in app_id:
        raise ScenarioError(f"manifest id {app_id!r} cannot name a jail directory")
    return app_id


def prepare_copy(bundle, workdir, scenario, nonce="0"):
    """Copy the bundle and prepend the fake host. Returns (copy, shim_lines).

    Only main.splash changes (and the copy's signature goes, as its bytes
    differ); capabilities, storage and everything else stay as written.
    """
    links = bundle_links(bundle)
    if links:
        raise ScenarioError(f"{bundle} contains symbolic links ({', '.join(links[:3])}); a bundle holds regular "
                            "files only, and the runner never writes through a link to the original")
    copy = workdir / "bundle"
    shutil.copytree(bundle, copy, symlinks=False)
    main = copy / "main.splash"
    if not main.is_file() or main.is_symlink():
        raise ScenarioError(f"{bundle} has no main.splash; uitest runs script apps")
    if (copy / "manifest.json").is_symlink():
        raise ScenarioError(f"{bundle}/manifest.json is a link")
    manifest_path = copy / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    check_app_id(manifest.get("id"))
    shim_lines = 0
    if scenario.get("fake_host", True):
        shim = shim_source(scenario.get("host", {}), scenario.get("host_profile", "octosense"),
                           manifest.get("capabilities", []), nonce)
        shim_lines = shim.count("\n")
        main.write_text(shim + main.read_text(encoding="utf-8"), encoding="utf-8")
        integrity = manifest.setdefault("integrity", {})
        if integrity.pop("signature", None) is not None or integrity.pop("github", None) is not None:
            manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return copy, shim_lines


def bundle_links(bundle):
    """Every symbolic link under the bundle, as paths relative to it."""
    out = []
    for root, dirs, files in os.walk(bundle, followlinks=False):
        for name in dirs + files:
            p = Path(root) / name
            if p.is_symlink():
                out.append(str(p.relative_to(bundle)))
    return out


def jail_path(jail, name, where="storage"):
    """The file `name` inside `jail`, refusing any name that would leave it.

    Scenario files come from the repository under test; a name such as
    "../../.bashrc" or "/etc/x" must never become a write outside the jail.
    """
    check_jail_name(name, where)
    root = Path(jail).resolve()
    target = (root / name).resolve()
    if target != root and root not in target.parents:
        raise ScenarioError(f"{where}: {name!r} resolves outside the app's jail")
    return target


def check_jail_name(name, where):
    if not isinstance(name, str) or not name.strip():
        raise ScenarioError(f"{where}: a file name is a non-empty string, got {name!r}")
    if any(ord(ch) < 32 or ch == "\x7f" for ch in name):
        raise ScenarioError(f"{where}: {name!r} contains a control character")
    p = Path(name)
    if p.is_absolute() or name.startswith(("/", "\\")) or re.match(r"^[A-Za-z]:", name):
        raise ScenarioError(f"{where}: {name!r} is absolute; name a file inside the app's jail")
    if "\\" in name or ".." in p.parts or any(ch in name for ch in "*?[]"):
        raise ScenarioError(f"{where}: {name!r} may not contain '..', a backslash or a glob character")
    if not p.parts or name.rstrip().endswith("/"):
        raise ScenarioError(f"{where}: {name!r} names a directory; name a file")
    # Common filesystem limits (NAME_MAX 255 bytes; well under PATH_MAX with the jail
    # in front): past them the name can only fail once the app is already running.
    if len(name.encode("utf-8")) > 1024 or any(len(part.encode("utf-8")) > 255 for part in p.parts):
        raise ScenarioError(f"{where}: {_short(name, 60)} is longer than a file name may be "
                            "(255 bytes a part, 1024 in all)")


# --------------------------------------------------------------- card-host
def config_file():
    """Where scripts/setup.sh records the card-host it found or built, for later shells."""
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "splash-app-verify" / "card-host"


def card_host_candidates(explicit):
    out = [("--card-host", explicit), ("OCTO_CARD_HOST", os.environ.get("OCTO_CARD_HOST"))]
    try:
        saved = config_file().read_text(encoding="utf-8").strip()
    except OSError:
        saved = None
    out.append((f"{config_file()} (scripts/setup.sh)", saved))
    for var in ("OCTOSENSE_APP_HUB", "CARGO_TARGET_DIR"):
        root = os.environ.get(var)
        if root:
            out += [(var, str(Path(root) / "target/release/card-host")), (var, str(Path(root) / "release/card-host"))]
    out.append(("PATH", shutil.which("card-host")))
    return out


def find_card_host(explicit, with_source=False):
    for source, c in card_host_candidates(explicit):
        if c and Path(c).is_file() and os.access(c, os.X_OK):
            found = str(Path(c).resolve())
            return (found, source) if with_source else found
    return (None, None) if with_source else None


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Display:
    """Use $DISPLAY or a native window system; on headless Linux start one private Xvfb."""

    def __init__(self):
        self.proc = None
        self.env = {}

    def __enter__(self):
        if sys.platform.startswith("linux") and not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
            xvfb = shutil.which("Xvfb")
            if not xvfb:
                raise RuntimeError("no display and no Xvfb: install xvfb (see scripts/setup.sh)")
            for n in range(90, 140):
                if not Path(f"/tmp/.X11-unix/X{n}").exists() and not Path(f"/tmp/.X{n}-lock").exists():
                    break
            self.proc = subprocess.Popen([xvfb, f":{n}", "-screen", "0", "1600x1200x24", "-nolisten", "tcp"],
                                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            for _ in range(50):
                if Path(f"/tmp/.X11-unix/X{n}").exists():
                    break
                time.sleep(0.1)
            self.env = {"DISPLAY": f":{n}", "LIBGL_ALWAYS_SOFTWARE": "1"}
        self.env["MAKEPAD_HIDE_WINDOWS"] = "1"
        return self

    def __exit__(self, *exc):
        if self.proc:
            self.proc.terminate()
            try:
                self.proc.wait(5)
            except subprocess.TimeoutExpired:
                self.proc.kill()


def is_runtime_error(line):
    """A log line that means the app's script failed: an error, a panic, a
    stop on its instruction budget, or a parse error (`splash: splash:<n>:<l>:<c>: …`)."""
    if any(m in line for m in RUNTIME_ERROR_MARKERS):
        return True
    return bool(re.search(r"splash: .* is stopped: ", line) or re.search(r"splash: splash:\d+:\d+:\d+:", line))


class App:
    def __init__(self, card_host, bundle, data_dir, size, log_path, env, jail=None, nonce=None):
        self.port = free_port()
        self.base = f"http://127.0.0.1:{self.port}"
        self.log_path = log_path
        self.data_dir = data_dir
        self.jail = Path(jail) if jail else None
        self.nonce = nonce
        self.log_file = open(log_path, "w", encoding="utf-8", errors="replace")
        full_env = dict(os.environ, **env, MAKEPAD_REMOTE=str(self.port))
        self.proc = subprocess.Popen(
            [card_host, "--bundle", str(bundle), "--app-data", str(data_dir), "--allow-unsigned", "--stamp",
             "--size", size],
            stdout=self.log_file, stderr=subprocess.STDOUT, env=full_env, cwd=str(bundle.parent),
            start_new_session=True)
        self.log_seen = 0
        self.line_offset = 0

    def get(self, route, timeout=10.0, **params):
        query = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
        url = f"{self.base}{route}" + (f"?{query}" if query else "")
        with urllib.request.urlopen(url, timeout=timeout) as r:
            body = r.read()
        if route in ("/g", "/grab") and params.get("raw"):
            return body
        try:
            return json.loads(body.decode("utf-8"))
        except ValueError:
            return body.decode("utf-8", "replace")

    def log_text(self):
        try:
            return Path(self.log_path).read_text(encoding="utf-8", errors="replace")
        except OSError:
            return ""

    def wait_ready(self, timeout):
        deadline = time.time() + timeout
        last = None
        while time.time() < deadline:
            if self.proc.poll() is not None:
                raise RuntimeError(f"card-host exited ({self.proc.returncode}); see {self.log_path}")
            log = self.log_text()
            if "card-host: refused" in log:
                raise StepFailed("the bundle is admitted", "card-host refused it",
                                 {"log": [l for l in log.splitlines() if "refused" in l][-3:]})
            try:
                snap = self.get("/snap", timeout=3)
                if isinstance(snap, dict) and snap.get("s"):
                    time.sleep(0.3)  # let start_timeout(0.05, …) loaders run
                    return
                last = snap
            except (OSError, ValueError) as e:
                last = str(e)
            time.sleep(0.25)
        raise RuntimeError(f"card-host did not answer /snap with widgets in {timeout}s (last: {last!r}); see {self.log_path}")

    def snap(self):
        data = self.get("/snap")
        widgets = data.get("s", []) if isinstance(data, dict) else []
        # The `Splash` host widget reports the whole script source as its text;
        # it is not something the app shows.
        return [w for w in widgets if w.get("ty") != "Splash"]

    def new_runtime_errors(self):
        lines = self.log_text().splitlines()
        fresh = lines[self.log_seen:]
        self.log_seen = len(lines)
        errors = [l for l in fresh if is_runtime_error(l)]
        # Error positions count the test shim's lines; report them against main.splash.
        def shift(m):
            return f"splash:{m.group(1)}:{max(1, int(m.group(2)) - self.line_offset)}:{m.group(3)}"
        return [re.sub(r"splash:(\d+):(\d+):(\d+)", shift, l) for l in errors]

    def exited(self):
        proc = getattr(self, "proc", None)
        return proc is not None and proc.poll() is not None

    def find_file(self, name):
        """The file at exactly this path in the app's jail, or None. No search:
        a file of the same name elsewhere (a backup, say) does not count."""
        if self.jail is None:
            raise EvidenceError("the runner does not know the app's jail")
        check_jail_name(name, "files")
        path = self.jail
        try:
            for part in Path(name).parts:
                path = path / part
                if path.is_symlink():   # a link may point anywhere: not the app's file
                    return None
            return path if path.is_file() else None
        except OSError as e:
            raise EvidenceError(f"cannot look at {name!r} in the app's jail: {e}") from None

    def calls(self, final=False):
        """Every host.request the app made, from the fake host's lines in card-host's log.

        The ready line comes first; without it the evidence is missing, which
        is an error, never "no calls". A line that does not parse, a gap in the
        sequence numbers, or a record cut off at the end of a finished log is an
        error too. While the host runs, a record still being written makes the
        check wait (PendingEvidence) rather than count what is there so far.
        """
        if not self.nonce:
            raise EvidenceError("this run has no fake host, so there is no call evidence")
        text = self.log_text()
        cut = text.rfind("\n") + 1
        complete, tail = text[:cut], text[cut:]
        if f"{CALL_MARK}{self.nonce}" in tail:
            if final:
                raise EvidenceError("the card-host log ends inside a call record; "
                                    "the call evidence is incomplete")
            raise PendingEvidence("the call log has no record still being written",
                                  "the last call record is still being written", {"tail": tail[:200]})
        lines = complete.splitlines()
        if f"{READY_MARK}{self.nonce}" not in (l.strip() for l in lines):
            raise EvidenceError("the fake host never reported itself ready in the card-host log, "
                                "so no call check can be trusted")
        mark = f"{CALL_MARK}{self.nonce} "
        out = []
        for l in lines:
            if l.startswith(mark):
                try:
                    call = json.loads(l[len(mark):])
                except ValueError as e:
                    raise EvidenceError(f"a call line in the card-host log does not parse ({e}): {l[:200]}")
                if not isinstance(call, dict) or not isinstance(call.get("service"), str):
                    raise EvidenceError(f"a call line in the card-host log is not a call: {l[:200]}")
                if call.get("seq") != len(out) + 1:
                    raise EvidenceError(f"call record {len(out) + 1} is missing from the card-host log "
                                        f"(the next one says seq {call.get('seq')!r})")
                out.append(call)
        return out

    def peak_rss_mb(self):
        """card-host's peak resident memory (Linux), for the resource record."""
        try:
            for line in Path(f"/proc/{self.proc.pid}/status").read_text().splitlines():
                if line.startswith("VmHWM:"):
                    return round(int(line.split()[1]) / 1024, 1)
        except OSError:
            pass
        return None

    def close(self):
        try:
            if self.proc.poll() is None:
                try:
                    self.get("/quit", timeout=3)
                except Exception:
                    pass
                try:
                    self.proc.wait(5)
                except subprocess.TimeoutExpired:
                    for sig in (signal.SIGTERM, signal.SIGKILL):
                        try:
                            os.killpg(self.proc.pid, sig)
                        except ProcessLookupError:
                            break  # it exited meanwhile
                        try:
                            self.proc.wait(5)
                            break
                        except subprocess.TimeoutExpired:
                            continue
        finally:
            self.log_file.close()


# --------------------------------------------------------------- selectors and checks
def describe(sel):
    return json.dumps(sel, ensure_ascii=False) if not isinstance(sel, str) else f'"{sel}"'


def matches(w, sel):
    if isinstance(sel, str):
        sel = {"text": sel}
    text = (w.get("t") or "") + ("\n" + str(w["value"]) if w.get("value") not in (None, "") else "")
    if "id" in sel and w.get("i") != sel["id"]:
        return False
    if "type" in sel and w.get("ty") != sel["type"]:
        return False
    if "text" in sel and (w.get("t") or "").strip() != sel["text"]:
        return False
    if "contains" in sel and sel["contains"] not in text:
        return False
    return True


def find(widgets, sel):
    """All widgets matching sel, and the one it picks.

    `after` keeps only widgets listed after the first match of another
    selector: the button in the same card as a text, in a list without ids.
    `nth` counts what is on screen now, so it shifts when the view scrolls.
    """
    pool = widgets
    if isinstance(sel, dict) and "after" in sel:
        _, anchor = find(widgets, sel["after"])
        # By identity: two cards with the same heading report equal widgets.
        at = next((i for i, w in enumerate(widgets) if w is anchor), None)
        pool = widgets[at + 1:] if at is not None else []
    found = [w for w in pool if matches(w, sel)]
    nth = sel.get("nth", 0) if isinstance(sel, dict) else 0
    return found, (found[nth] if len(found) > nth else None)


def nearest(widgets, sel, limit=5):
    """What the screen has that looks like the selector: for the feedback, not for passing."""
    key = sel if isinstance(sel, str) else (sel.get("text") or sel.get("contains") or sel.get("id") or "")
    key = str(key)
    scored = []
    for w in widgets:
        hay = f"{w.get('i','')} {w.get('t','')}"
        common = sum(1 for ch in set(key) if ch in hay)
        if common:
            scored.append((common, w))
    scored.sort(key=lambda x: -x[0])
    return [{"id": w.get("i"), "type": w.get("ty"), "text": w.get("t"), "rect": w.get("r")} for _, w in scored[:limit]]


def widget_text(w):
    """What one widget shows: its text, and an input's value."""
    text = w.get("t") or ""
    if w.get("value") not in (None, ""):
        text += "\n" + str(w["value"])
    return text


def shows(widgets, t):
    """Whether one widget shows t. Text is never matched across two widgets."""
    return any(t in widget_text(w) for w in widgets)


def inside(rect, view):
    x, y, w, h = rect
    vx, vy, vw, vh = view
    return x >= vx - 0.5 and y >= vy - 0.5 and x + w <= vx + vw + 0.5 and y + h <= vy + vh + 0.5


def clipped_by(widgets, w):
    """The container that may cut w off, if any.

    /snap reports the visible part of a widget inside a scroll view, so a
    half-hidden button looks like a short one. Its cut edge then lies exactly
    on the scroll view's edge. A whole widget can also sit flush against a
    container's edge, so this is only a suspicion: `is_clipped` settles it.
    """
    x, y, ww, hh = w["r"]
    for c in widgets:
        if c is w or c.get("ty") in ("Window", "KeyboardView"):
            continue
        cx, cy, cw, ch = c["r"]
        if ch < 2 * hh + 20 or not inside(w["r"], c["r"]):
            continue
        if abs(y - cy) < 0.5 or abs((y + hh) - (cy + ch)) < 0.5:
            return c
    return None


def _positions(widgets):
    return json.dumps([x.get("r") for x in widgets])


def is_clipped(app, widgets, w, sel):
    """Whether w is cut off, settled by looking, as a person would.

    Only when w touches a container's edge (`clipped_by`): scroll that
    container a little toward the touching edge and snap again. If the widget
    grows, part of it was hidden. If it moves without growing, or nothing
    moves (the content ends there), it was whole. The scroll is then undone.
    """
    cut = clipped_by(widgets, w)
    if cut is None:
        return None
    x, y, ww, hh = w["r"]
    at_bottom = abs((y + hh) - (cut["r"][1] + cut["r"][3])) < 0.5
    dy = 60.0 if at_bottom else -60.0
    px, py = center(cut["r"])
    before = _positions(widgets)
    app.get("/m", k="scroll", x=px, y=py, dy=dy, wait=1)
    after_widgets = app.snap()
    _, w2 = find(after_widgets, sel)
    if _positions(after_widgets) == before:
        return None  # nothing scrolls there: the widget is whole, flush against the edge
    grown = bool(w2) and w2["r"][3] > hh + 0.5
    # Undo the probe, then correct once if the content did not come back exactly.
    app.get("/m", k="scroll", x=px, y=py, dy=-dy, wait=1)
    if w2:
        _, w3 = find(app.snap(), sel)
        moved = y - w2["r"][1]
        if w3 and moved and abs(w3["r"][1] - y) > 0.5:
            app.get("/m", k="scroll", x=px, y=py, dy=round((w3["r"][1] - y) * dy / moved, 1), wait=1)
    return cut if grown else None


def fully_visible(app, widgets, w, sel, view):
    return inside(w["r"], view) and is_clipped(app, widgets, w, sel) is None


def check_expectation(app, exp, view):
    """Raise StepFailed unless every clause of exp holds now (ScenarioError for a malformed exp)."""
    validate_expect(exp, "expectation")
    widgets = app.snap()
    for t in exp.get("text", []):
        if not shows(widgets, t):
            raise StepFailed(f'text "{t}" is shown', "not on screen",
                             {"similar": nearest(widgets, {"contains": t})})
    for t in exp.get("absent", []):
        if isinstance(t, str):
            hits = [w for w in widgets if t in widget_text(w)]
            what = f'text "{t}"'
        else:
            hits, _ = find(widgets, t)
            what = f"a widget {describe(t)}"
        if hits:
            raise StepFailed(f"{what} is not shown", "it is on screen",
                             {"widgets": [{"id": w.get("i"), "type": w.get("ty"), "text": w.get("t"), "rect": w.get("r")}
                                          for w in hits[:5]]})
    for sel in exp.get("in_view", []):
        found, w = find(widgets, sel)
        if not w:
            raise StepFailed(f"{describe(sel)} is fully inside the viewport {view}", "no such widget",
                             {"similar": nearest(widgets, sel)})
        if not inside(w["r"], view):
            x, y, ww, hh = w["r"]
            over = {"right": round(x + ww - (view[0] + view[2]), 1), "bottom": round(y + hh - (view[1] + view[3]), 1)}
            raise StepFailed(f"{describe(sel)} is fully inside the viewport {view}",
                             f"its rect is {w['r']}: past the right edge by {over['right']} and the bottom by {over['bottom']} points",
                             {"widget": {"id": w.get("i"), "type": w.get("ty"), "text": w.get("t"), "rect": w.get("r")}})
        cut = is_clipped(app, widgets, w, sel)
        if cut is not None:
            raise StepFailed(f"{describe(sel)} is fully inside the viewport {view}",
                             f"only {w['r']} of it shows: the scroll view {cut.get('i') or cut.get('ty')} {cut['r']} cuts it off "
                             "(scrolling it toward that edge shows more of the widget)",
                             {"widget": {"id": w.get("i"), "type": w.get("ty"), "text": w.get("t"), "rect": w.get("r")}})
    for sel in exp.get("enabled", []):
        _, w = find(widgets, sel)
        if not w or not w.get("enabled", True):
            raise StepFailed(f"{describe(sel)} is enabled", "missing" if not w else "disabled", {})
    for sel in exp.get("disabled", []):
        _, w = find(widgets, sel)
        if not w or w.get("enabled", True):
            raise StepFailed(f"{describe(sel)} is disabled", "missing" if not w else "enabled", {})
    for item in exp.get("count", []):
        found, _ = find(widgets, item["of"])
        if len(found) != item["n"]:
            raise StepFailed(f"{item['n']} widgets match {describe(item['of'])}", f"{len(found)} match", {})
    for item in exp.get("calls", []):
        calls = [c for c in app.calls() if c.get("service") == item["service"]]
        if "contains" in item:
            calls = [c for c in calls if item["contains"] in json.dumps(c.get("args"), ensure_ascii=False)]
        want = item.get("count")
        if (want is None and not calls and "excludes" not in item) or (want is not None and len(calls) != want):
            raise StepFailed(f"{'≥1' if want is None else want} call(s) to {item['service']}"
                             + (f" with args containing \"{item['contains']}\"" if "contains" in item else ""),
                             f"{len(calls)} such call(s)", {"calls": app.calls()[-5:]})
        if "excludes" in item:
            leaked = [c for c in calls if item["excludes"] in json.dumps(c.get("args"), ensure_ascii=False)]
            if leaked:
                raise StepFailed(f"no call to {item['service']} sends \"{item['excludes']}\"",
                                 f"{len(leaked)} call(s) do", {"calls": leaked[-2:]})
    for item in exp.get("files", []):
        p = app.find_file(item["name"])
        if item.get("missing"):
            if p:
                raise StepFailed(f"no file {item['name']} in the jail", f"{p} exists", {})
            continue
        if not p:
            raise StepFailed(f"file {item['name']} in the jail", "missing", {})
        try:
            body = p.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            raise EvidenceError(f"cannot read {item['name']} in the app's jail: {e}") from None
        for c in item.get("contains", []):
            if c not in body:
                raise StepFailed(f"{item['name']} contains \"{c}\"", "it does not", {"head": body[:400]})


def wait_for(app, exp, view, timeout):
    deadline = time.time() + timeout
    while True:
        try:
            check_expectation(app, exp, view)
            return
        except StepFailed:
            if time.time() >= deadline:
                raise
            time.sleep(0.2)


def center(rect):
    x, y, w, h = rect
    return round(x + w / 2, 1), round(y + h / 2, 1)


def scroll_into_view(app, sel, on, view, attempts):
    """Scroll, as a person would, until the widget lies wholly inside the viewport.

    Works at every size without per-size distances. Fails when the widget is
    taller than the viewport or scrolling stops moving anything.
    """
    vx, vy, vw, vh = view
    ratio = 1.0          # measured content movement per unit of scroll
    before = None        # (target y, dy) of the previous attempt
    last_sig = None
    direction = 1        # while the widget is not listed: search down, then up
    for _ in range(attempts):
        widgets = app.snap()
        _, w = find(widgets, sel)
        cut = is_clipped(app, widgets, w, sel) if w else None
        if w and cut is None and inside(w["r"], view):
            return
        if w and w["r"][3] > vh + 0.5:
            raise StepFailed(f"{describe(sel)} fits inside the viewport {view}",
                             f"it is {w['r'][3]} points tall", {"rect": w["r"]})
        sig = json.dumps([x.get("r") for x in widgets])
        if sig == last_sig:
            if not w and direction == 1:
                direction = -1  # reached the end without seeing it: look above
            else:
                raise StepFailed(f"{describe(sel)} can be scrolled into the viewport {view}",
                                 "scrolling no longer moves anything" + ("" if w else "; the widget never appeared"),
                                 {"similar": nearest(widgets, sel)} if not w else {"rect": w["r"]})
        last_sig = sig
        if w:
            y, h = w["r"][1], w["r"][3]
            if before is not None and before[1]:
                moved = before[0] - y
                if moved and (moved / before[1]) > 0:
                    ratio = moved / before[1]
            if cut is not None:
                # Only its visible part is listed: move a third of a screen toward the cut edge.
                at_bottom = abs((y + h) - (cut["r"][1] + cut["r"][3])) < 0.5
                dy = (1 if at_bottom else -1) * vh * 0.33 / ratio
                before = None
            else:
                need = (y + h) - (vy + vh) + 12 if y + h > vy + vh else y - vy - 12
                dy = need / ratio
                before = (y, dy)
        else:
            dy = direction * vh * 0.6
            before = None
        if on:
            _, host_w = find(widgets, on)
            if not host_w:
                raise StepFailed(f"a widget {describe(on)} to scroll", "no such widget", {})
            px, py = center(host_w["r"])
        else:
            px, py = vx + vw / 2, vy + vh / 2
        app.get("/m", k="scroll", x=round(px, 1), y=round(py, 1), dy=round(dy, 1), wait=1)
    raise StepFailed(f"{describe(sel)} can be scrolled into the viewport {view}",
                     f"still outside after {attempts} scrolls", {})


def do_step(app, step, view):
    validate_step(step, "step")
    if "click" in step:
        sel = step["click"]
        widgets = app.snap()
        _, w = find(widgets, sel)
        if not w:
            raise StepFailed(f"a widget {describe(sel)} to click", "no such widget on screen",
                             {"similar": nearest(widgets, sel)})
        if not inside(w["r"], view):
            raise StepFailed(f"{describe(sel)} is inside the viewport so a person can click it",
                             f"its rect is {w['r']}, viewport {view}", {})
        x, y = center(w["r"])
        app.get("/click", x=x, y=y, wait=1)
    elif "type" in step:
        spec = step["type"]
        if "into" in spec:
            do_step(app, {"click": spec["into"]}, view)
            if spec.get("clear"):
                # The click leaves the caret wherever it landed: delete on both sides of it.
                _, w = find(app.snap(), spec["into"])
                n = len(str((w or {}).get("value") or (w or {}).get("t") or "")) + 2
                for key in ("Delete", "Backspace"):
                    for _ in range(n):
                        app.get("/k", k="down", c=key)
        app.get("/t", t=spec["text"], wait=1)
    elif "key" in step:
        app.get("/k", k="down", c=step["key"], wait=1)
        app.get("/k", k="up", c=step["key"], wait=1)
    elif "scroll" in step:
        spec = step["scroll"]
        _, w = find(app.snap(), spec["on"])
        if not w:
            raise StepFailed(f"a widget {describe(spec['on'])} to scroll", "no such widget", {})
        x, y = center(w["r"])
        app.get("/m", k="scroll", x=x, y=y, dy=spec.get("dy", 300), wait=1)
    elif "scroll_to" in step:
        targets = step["scroll_to"] if isinstance(step["scroll_to"], list) else [step["scroll_to"]]
        for sel in targets:
            scroll_into_view(app, sel, step.get("on"), view, int(step.get("max", 25)))
    elif "sleep" in step:
        time.sleep(float(step["sleep"]))
    elif "expect" in step:
        wait_for(app, step["expect"], view, float(step.get("timeout", 2.0)))
    elif "wait" in step:
        wait_for(app, step["wait"], view, float(step.get("timeout", 10.0)))
    else:
        raise ScenarioError(f"unknown step {step!r}")
    errors = app.new_runtime_errors()
    if errors and not step.get("allow_runtime_errors"):
        raise StepFailed("no runtime error in the log", errors[-1], {"log": errors[-5:]})
    if hasattr(app, "exited") and app.exited():
        raise StepFailed("the app keeps running", f"card-host exited with status {app.proc.returncode}", {})


# --------------------------------------------------------------- run and report
def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def feedback(result, bundle, card_host):
    s = result
    steps = "\n".join(f"  {i + 1}. {json.dumps(st, ensure_ascii=False)}" for i, st in enumerate(s["steps_run"]))
    detail = json.dumps(s["detail"], ensure_ascii=False, indent=2) if s["detail"] else "(none)"
    return f"""# Repair request: {s['scenario']} @ {s['size']}

Artifact: {bundle}/main.splash, sha256 {s['source_sha256']}.
Runtime: card-host {card_host}, window {s['size']}, viewport {s['viewport']}; host services are the scenario's fixtures.
Start state: a fresh launch of scenario "{s['scenario']}" ({s['file']}); storage seeded as the scenario says.

Steps (the last one failed):
{steps}

Expected: {s['expected']}
Actual: {s['actual']}
Details:
```json
{detail}
```
Evidence: {s['evidence'].get('snap')}, {s['evidence'].get('log')}{', ' + s['evidence']['png'] if s['evidence'].get('png') else ''}

Fix: change only what makes this step pass. Keep widget ids, button texts and the behavior other scenarios check.
Retest: run every scenario again (`uitest.py run <bundle> <scenarios>`); report what still fails. Do not score yourself.
"""


def app_files(jail):
    """The app's own files in its jail: regular files only (no links), not the host's."""
    jail = Path(jail)
    if not jail.is_dir() or jail.is_symlink():
        return []
    out = []
    for p in jail.rglob("*"):
        rel = p.relative_to(jail)
        if ".host" in rel.parts or p.is_symlink() or not p.is_file():
            continue
        if any((jail / Path(*rel.parts[:i])).is_symlink() for i in range(1, len(rel.parts))):
            continue
        out.append(p)
    return out


def copy_jail(jail, dest, limit=4 * 1024 * 1024):
    """Copy the app's own files if they are small enough."""
    files = app_files(jail)
    if not files or sum(p.stat().st_size for p in files) > limit:
        return False
    for p in files:
        target = dest / p.relative_to(jail)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(p, target)
    return True


def run_one(card_host, bundle, scenario_path, scenario, size, out_dir, display, run_id=None):
    view_cfg = scenario.get("viewport")
    w, h = (float(v) for v in size.lower().split("x"))
    view = view_cfg if view_cfg else [0, 0, w, h]
    tag = f"{scenario_path.stem}@{size}"
    work = Path(tempfile.mkdtemp(prefix="uitest-"))
    run_dir = out_dir / tag
    if run_dir.exists():
        shutil.rmtree(run_dir)
    run_dir.mkdir(parents=True)
    nonce = os.urandom(8).hex() if scenario.get("fake_host", True) else None
    result = {"scenario": scenario.get("name", scenario_path.stem), "file": str(scenario_path), "size": size,
              "viewport": view, "run_id": run_id, "scenario_sha256": scenario_digest(scenario),
              "host_profile": scenario.get("host_profile", "octosense") if scenario.get("fake_host", True) else None,
              "source_sha256": sha256(bundle / "main.splash"), "passed": False, "steps_run": [], "evidence": {}}
    app = None
    jail = work / "data"
    started = time.time()
    try:
        copy, shim_lines = prepare_copy(bundle, work, scenario, nonce or "0")
        data = work / "data"
        manifest = json.loads((copy / "manifest.json").read_text(encoding="utf-8"))
        jail = data / check_app_id(manifest.get("id"))
        jail.mkdir(parents=True, exist_ok=True)
        for name, body in (scenario.get("storage") or {}).items():
            target = jail_path(jail, name)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(body if isinstance(body, str) else json.dumps(body, ensure_ascii=False), encoding="utf-8")
        app = App(card_host, copy, data, size, run_dir / "card-host.log", display.env, jail=jail, nonce=nonce)
        app.line_offset = shim_lines
        app.wait_ready(float(scenario.get("startup_timeout", 60)))
        errors = app.new_runtime_errors()
        if errors and not scenario.get("allow_runtime_errors"):
            raise StepFailed("the app starts without a runtime error", errors[-1], {"log": errors[-5:]})
        for step in scenario.get("steps", []):
            result["steps_run"].append(step)
            do_step(app, step, view)
        result["passed"] = True
    except StepFailed as f:
        result.update(expected=f.expected, actual=f.actual, detail=f.detail)
    except ScenarioError:
        raise
    except Exception as e:  # environment or evidence trouble: report, do not blame the app
        result.update(expected="the runner reaches the step and reads its evidence",
                      actual=f"{type(e).__name__}: {e}", detail={}, environment_error=True)
    finally:
        result["seconds"] = round(time.time() - started, 2)
        # Each piece of evidence is collected on its own: one that fails is
        # recorded, and the host is still closed and the work directory removed.
        if app:
            try:
                if not result["passed"]:
                    try:
                        if not result.get("environment_error") and not [w for w in app.snap() if w.get("ty") not in HOST_WIDGETS]:
                            result.setdefault("detail", {})["hint"] = (
                                "the app shows no widget at all: its script stopped before drawing anything. "
                                "A parse error does this, and some runtimes write no log line for it; "
                                "check the source near your last edit")
                    except Exception:
                        pass
                    try:
                        (run_dir / "snap.json").write_text(json.dumps(app.get("/snap"), ensure_ascii=False, indent=1))
                        result["evidence"]["snap"] = str(run_dir / "snap.json")
                        png = app.get("/g", raw=1, timeout=20)
                        if isinstance(png, (bytes, bytearray)) and png[:4] == b"\x89PNG":
                            (run_dir / "screen.png").write_bytes(png)
                            result["evidence"]["png"] = str(run_dir / "screen.png")
                    except Exception as e:
                        result["evidence"]["snap_error"] = f"{type(e).__name__}: {e}"
                try:
                    result["peak_rss_mb"] = app.peak_rss_mb()
                except Exception:
                    pass
            finally:
                try:
                    app.close()
                except Exception as e:  # the host must not take the cleanup and the result with it
                    result["evidence"]["close_error"] = f"{type(e).__name__}: {e}"
                    result["environment_error"] = True
            result["evidence"]["log"] = str(run_dir / "card-host.log")
            if nonce:
                try:
                    calls = app.calls(final=True)
                    (run_dir / "calls.json").write_text(json.dumps(calls, ensure_ascii=False, indent=1))
                    result["evidence"]["calls"] = str(run_dir / "calls.json")
                    undeclared = sorted({c["service"] for c in calls if c.get("declared") is False})
                    if undeclared:
                        result["undeclared_services"] = undeclared
                except Exception as e:
                    result["evidence"]["calls_error"] = f"{type(e).__name__}: {e}"
                    if result["passed"]:
                        # Without readable call evidence the run did not show what the scenario
                        # describes (the fake host's replies): not a pass, not the app's fault.
                        result["passed"] = False
                        result.update(expected="the fake host's call evidence is complete",
                                      actual=result["evidence"]["calls_error"], detail={}, environment_error=True)
            # What the app left in its jail: evidence, and a seed for a restart scenario.
            try:
                if copy_jail(jail, run_dir / "jail"):
                    result["evidence"]["jail"] = str(run_dir / "jail")
            except Exception as e:
                result["evidence"]["jail_error"] = f"{type(e).__name__}: {e}"
        shutil.rmtree(work, ignore_errors=True)
    if not result["passed"]:
        try:
            (run_dir / "FEEDBACK.md").write_text(feedback(result, bundle, card_host), encoding="utf-8")
            result["feedback"] = str(run_dir / "FEEDBACK.md")
        except Exception as e:
            result["feedback"] = f"(not written: {type(e).__name__}: {e})"
    (run_dir / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def scenario_digest(scenario):
    """The scenario as it ran: after parts were merged and steps expanded."""
    return hashlib.sha256(json.dumps(scenario, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def tree_digest(root):
    """One digest over every file under root, with its relative path."""
    h = hashlib.sha256()
    root = Path(root)
    for p in sorted(x for x in root.rglob("*") if x.is_file()):
        h.update(str(p.relative_to(root)).encode("utf-8") + b"\0")
        h.update(p.read_bytes() + b"\0")
    return h.hexdigest()


def warnings_for(result):
    """Lines the summary prints under a run: true of the run, not failures of the app."""
    out = []
    if result.get("undeclared_services"):
        names = ", ".join(result["undeclared_services"])
        if result.get("host_profile") == "rinx":
            out.append(f"called without declaring: {names} (refused, as Rinx does)")
        else:
            out.append(f"called without declaring: {names} (answered, as an OctoSense host does, which lists "
                       "it as undisclosed; Rinx would refuse it: set \"host_profile\": \"rinx\" to test that)")
    if result.get("evidence", {}).get("calls_error"):
        out.append("call log: " + result["evidence"]["calls_error"])
    return out


SHARED_KEYS = ("sizes", "size", "viewport", "startup_timeout", "fake_host", "allow_runtime_errors", "host_profile")


def _unknown(keys, allowed, where, what):
    bad = sorted(set(keys) - set(allowed))
    if bad:
        raise ScenarioError(f"{where}: unknown {what} key(s) {bad}; allowed: {sorted(allowed)}")


def _num(v):
    """A finite number that is not a bool (JSON true would otherwise count as 1)."""
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _whole(v):
    return isinstance(v, int) and not isinstance(v, bool) and v >= 0


def _seconds(v, positive=False):
    """A wait the runner can make: a finite number from 0 (above 0 if positive) to MAX_SECONDS."""
    return _num(v) and (v > 0 if positive else v >= 0) and v <= MAX_SECONDS


def _short(v, limit=160):
    text = repr(v)
    return text if len(text) <= limit else text[:limit] + "…"


def _need(cond, where, message):
    if not cond:
        raise ScenarioError(f"{where}: {message}")


def _list(value, where, key, what):
    if not isinstance(value, list):
        raise ScenarioError(f"{where}: \"{key}\" is a list of {what}, got {_short(value)}")
    return value


def _list_of(value, kind, where, key):
    if not isinstance(value, list) or not all(isinstance(v, kind) for v in value):
        raise ScenarioError(f"{where}: \"{key}\" is a list of {'strings' if kind is str else 'selectors'}")


def validate_selector(sel, where, depth=0):
    if isinstance(sel, str):
        if not sel:
            raise ScenarioError(f"{where}: an empty selector")
        return
    if not isinstance(sel, dict) or not sel:
        raise ScenarioError(f"{where}: a selector is a text or an object, got {_short(sel)}")
    _unknown(sel, SELECTOR_KEYS, where, "selector")
    if not set(sel) - {"nth", "after"}:
        raise ScenarioError(f"{where}: a selector needs one of id, type, text or contains: {_short(sel)}")
    for key in ("id", "type", "text", "contains"):
        _need(key not in sel or isinstance(sel[key], str), where, f"selector \"{key}\" is a string")
    _need("nth" not in sel or _whole(sel["nth"]), where, "\"nth\" is a whole number from 0")
    if "after" in sel:
        _need(depth < MAX_AFTER, where, f"\"after\" chains more than {MAX_AFTER} selectors")
        validate_selector(sel["after"], where + " after", depth + 1)


def validate_expect(exp, where, fake_host=True):
    if not isinstance(exp, dict) or not exp:
        raise ScenarioError(f"{where}: an expectation is a non-empty object")
    _unknown(exp, EXPECT_KEYS, where, "expectation")
    if "text" in exp:
        _list_of(exp["text"], str, where, "text")
    if "absent" in exp:
        if not isinstance(exp["absent"], list):
            raise ScenarioError(f"{where}: \"absent\" is a list of texts or selectors")
        for t in exp["absent"]:
            if not isinstance(t, str):
                validate_selector(t, where + " absent")
    for key in ("in_view", "enabled", "disabled"):
        if key in exp:
            if not isinstance(exp[key], list):
                raise ScenarioError(f"{where}: \"{key}\" is a list of selectors")
            for sel in exp[key]:
                validate_selector(sel, f"{where} {key}")
    for item in _list(exp.get("count", []), where, "count", "{\"of\", \"n\"} objects"):
        if not isinstance(item, dict):
            raise ScenarioError(f"{where}: a count item is an object")
        _unknown(item, COUNT_KEYS, where, "count")
        if "of" not in item or not _whole(item.get("n")):
            raise ScenarioError(f"{where}: a count item has \"of\" and a whole number \"n\"")
        validate_selector(item["of"], where + " count")
    if exp.get("calls") and not fake_host:
        raise ScenarioError(f"{where}: \"calls\" needs the fake host, and this scenario sets \"fake_host\": false")
    for item in _list(exp.get("calls", []), where, "calls", "call checks"):
        if not isinstance(item, dict):
            raise ScenarioError(f"{where}: a calls item is an object")
        _unknown(item, CALL_KEYS, where, "calls")
        if not isinstance(item.get("service"), str):
            raise ScenarioError(f"{where}: a calls item names its \"service\"")
        if "count" in item and not _whole(item["count"]):
            raise ScenarioError(f"{where}: calls \"count\" is a whole number")
        for key in ("contains", "excludes"):
            if key in item and not isinstance(item[key], str):
                raise ScenarioError(f"{where}: calls \"{key}\" is a string")
    for item in _list(exp.get("files", []), where, "files", "file checks"):
        if not isinstance(item, dict):
            raise ScenarioError(f"{where}: a files item is an object")
        _unknown(item, FILE_KEYS, where, "files")
        check_jail_name(item.get("name"), where + " files")
        _need("missing" not in item or isinstance(item["missing"], bool), where, "files \"missing\" is true or false")
        if "contains" in item:
            _list_of(item["contains"], str, where, "contains")
        _need(not (item.get("missing") is True and item.get("contains")), where,
              "a files item cannot require a file to be missing and to contain text")


def validate_step(step, where, fake_host=True):
    actions = set(step) & STEP_ACTIONS
    if len(actions) != 1:
        raise ScenarioError(f"{where}: a step has exactly one of {sorted(STEP_ACTIONS)} or \"run\", got {step!r}")
    action = actions.pop()
    _unknown(set(step) - {action}, STEP_MODIFIERS[action], where, f"\"{action}\" step")
    _need("allow_runtime_errors" not in step or isinstance(step["allow_runtime_errors"], bool), where,
          "\"allow_runtime_errors\" is true or false")
    _need("note" not in step or isinstance(step["note"], str), where, "\"note\" is a string")
    value = step[action]
    if action == "click":
        validate_selector(value, where)
    elif action == "type":
        if not isinstance(value, dict) or not isinstance(value.get("text"), str):
            raise ScenarioError(f"{where}: \"type\" is an object with \"text\"")
        _unknown(value, TYPE_KEYS, where, "type")
        _need("clear" not in value or isinstance(value["clear"], bool), where, "\"clear\" is true or false")
        if "into" in value:
            validate_selector(value["into"], where + " into")
    elif action == "key":
        if not isinstance(value, str) or not value:
            raise ScenarioError(f"{where}: \"key\" names a key")
    elif action == "scroll":
        if not isinstance(value, dict) or "on" not in value:
            raise ScenarioError(f"{where}: \"scroll\" is an object with \"on\"")
        _unknown(value, SCROLL_KEYS, where, "scroll")
        _need("dy" not in value or _num(value["dy"]), where, "\"dy\" is a number")
        validate_selector(value["on"], where + " scroll")
    elif action == "scroll_to":
        for sel in (value if isinstance(value, list) else [value]):
            validate_selector(sel, where + " scroll_to")
        if "on" in step:
            validate_selector(step["on"], where + " on")
        _need("max" not in step or (_whole(step["max"]) and 0 < step["max"] <= MAX_SCROLLS), where,
              f"\"max\" is a whole number of scrolls from 1 to {MAX_SCROLLS}")
    elif action == "sleep":
        _need(_seconds(value), where, f"\"sleep\" is a number of seconds from 0 to {MAX_SECONDS}")
    else:
        validate_expect(value, where, fake_host)
    _need("timeout" not in step or _seconds(step["timeout"]), where,
          f"\"timeout\" is a number of seconds from 0 to {MAX_SECONDS}")


SIZE_RE = re.compile(r"[1-9][0-9]{1,4}x[1-9][0-9]{1,4}")


def validate_scenario(sc, where):
    """Types of the scenario's own fields, after its parts are merged."""
    for key in ("fake_host", "allow_runtime_errors"):
        _need(key not in sc or isinstance(sc[key], bool), where, f"\"{key}\" is true or false")
    for key in ("name", "description", "note"):
        _need(key not in sc or isinstance(sc[key], str), where, f"\"{key}\" is a string")
    _need(sc.get("host_profile", "octosense") in HOST_PROFILES, where,
          f"host_profile must be one of {list(HOST_PROFILES)}")
    _need("startup_timeout" not in sc or _seconds(sc["startup_timeout"], positive=True), where,
          f"\"startup_timeout\" is a number of seconds above 0, at most {MAX_SECONDS}")
    sizes = sc.get("sizes") if "sizes" in sc else ([sc["size"]] if "size" in sc else [])
    _need(isinstance(sizes, list) and all(isinstance(z, str) and SIZE_RE.fullmatch(z) for z in sizes), where,
          "\"sizes\" is a list of \"WxH\" strings such as \"412x892\"")
    if "viewport" in sc:
        v = sc["viewport"]
        _need(isinstance(v, list) and len(v) == 4 and all(_num(x) for x in v) and v[2] > 0 and v[3] > 0, where,
              "\"viewport\" is [x, y, w, h] in points")
    _need(isinstance(sc.get("host"), dict), where, "\"host\" is an object of replies by service")
    _need(isinstance(sc.get("storage"), dict), where, "\"storage\" is an object of files by name")


def _not_json_number(name):
    raise ValueError(f"{name} is not a JSON number")


def _check_text(s, where):
    try:
        s.encode("utf-8")
    except UnicodeEncodeError:
        raise ScenarioError(f"{where}: a text holds a lone surrogate escape such as \\ud800, which is not "
                            f"UTF-8: {_short(s, 60)}") from None


def check_document(doc, where):
    """Refuse what Python's JSON reader lets through but nothing after it can use:
    text that is not UTF-8 (a lone surrogate escape) and nesting deeper than
    MAX_DEPTH. Walked without recursion, so a deep file cannot crash the check."""
    stack = [(doc, 0)]
    while stack:
        o, depth = stack.pop()
        if depth > MAX_DEPTH:
            raise ScenarioError(f"{where}: nested more than {MAX_DEPTH} deep")
        if isinstance(o, dict):
            for k, v in o.items():
                _check_text(k, where)
                stack.append((v, depth + 1))
        elif isinstance(o, list):
            stack.extend((v, depth + 1) for v in o)
        elif isinstance(o, str):
            _check_text(o, where)


def read_json(f):
    """A scenario or part file as standard JSON: no NaN or Infinity, UTF-8 text, bounded nesting."""
    try:
        text = Path(f).read_text(encoding="utf-8")
    except OSError as e:
        raise ScenarioError(f"{f}: cannot read ({e})")
    except ValueError as e:
        raise ScenarioError(f"{f}: not UTF-8 ({e})")
    try:
        data = json.loads(text, parse_constant=_not_json_number)
    except RecursionError:
        raise ScenarioError(f"{f}: nested too deep to read") from None
    except ValueError as e:
        raise ScenarioError(f"{f}: not JSON ({e})")
    check_document(data, f)
    return data


def _part_file(base, name, where, key):
    if not isinstance(name, str) or not name.strip() or any(ord(ch) < 32 for ch in name):
        raise ScenarioError(f"{where}: \"{key}\" names a part file, got {_short(name)}")
    return base / name


def _object(value, where, key, what):
    if not isinstance(value, dict):
        raise ScenarioError(f"{where}: \"{key}\" is an object of {what}, got {_short(value)}")
    return value


def expand_steps(steps, base, f, depth=0):
    """Inline {"run": "_part.json"} steps: shared step sequences such as "load the room"."""
    if depth > 5:
        raise ScenarioError(f"{f}: \"run\" nests more than 5 deep")
    out = []
    for step in steps:
        if not isinstance(step, dict):
            raise ScenarioError(f"{f}: a step is an object, got {_short(step)}")
        if "run" in step:
            _unknown(step, {"run", "note"}, f, "\"run\" step")
            part = _part_file(base, step["run"], f, "run")
            data = read_json(part)
            if not isinstance(data, dict) or not isinstance(data.get("steps"), list):
                raise ScenarioError(f"{part}: a part used by \"run\" is an object with a \"steps\" list")
            _unknown(data, PART_KEYS, part, "part")
            out += expand_steps(data["steps"], part.parent, part, depth + 1)
            continue
        out.append(step)
    return out


def resolve_scenario(f, data):
    """Apply "use" (shared host replies, storage and sizes from _parts) and expand "run" steps."""
    base = Path(f).parent
    uses = data.get("use", [])
    uses = [uses] if isinstance(uses, str) else uses
    if not isinstance(uses, list):
        raise ScenarioError(f"{f}: \"use\" names a part file or a list of them, got {_short(uses)}")
    host, storage, shared = {}, {}, {}
    for name in uses:
        path = _part_file(base, name, f, "use")
        part = read_json(path)
        if not isinstance(part, dict):
            raise ScenarioError(f"{path}: a part is an object")
        _unknown(part, PART_KEYS, path, "part")
        host.update(_object(part.get("host", {}), path, "host", "replies by service"))
        storage.update(_object(part.get("storage", {}), path, "storage", "files by name"))
        shared.update({k: part[k] for k in SHARED_KEYS if k in part})
    out = dict(shared)
    out.update({k: v for k, v in data.items() if k != "use"})
    out["host"] = {**host, **_object(data.get("host", {}), f, "host", "replies by service")}
    out["storage"] = {**storage, **_object(data.get("storage", {}), f, "storage", "files by name")}
    out["steps"] = expand_steps(data["steps"], base, f)
    return out


def load_scenarios(target):
    """Every *.json in name order; files whose names start with "_" are parts, not scenarios."""
    target = Path(target)
    files = sorted(p for p in target.glob("*.json") if not p.name.startswith("_")) if target.is_dir() else [target]
    out = []
    for f in files:
        data = read_json(f)
        if not isinstance(data, dict) or not isinstance(data.get("steps"), list):
            raise ScenarioError(f"{f}: a scenario is an object with a \"steps\" list")
        _unknown(data, SCENARIO_KEYS, f, "scenario")
        scenario = resolve_scenario(f, data)
        try:
            normalise_replies(scenario["host"])  # report a bad fixture before anything starts
        except ScenarioError as e:
            raise ScenarioError(f"{f}: {e}") from None
        validate_scenario(scenario, str(f))
        for name in scenario["storage"]:
            check_jail_name(name, f"{f}: storage")
        for i, step in enumerate(scenario["steps"]):
            validate_step(step, f"{f}: step {i + 1}", scenario.get("fake_host", True))
        out.append((f, scenario))
    if not out:
        raise ScenarioError(f"no scenario files in {target}")
    return out


def write_summary(out_dir, summary):
    tmp = out_dir / "summary.json.tmp"
    tmp.write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    tmp.replace(out_dir / "summary.json")


def cmd_run(args):
    """Every invocation writes a new summary.json first, marked "running", so a
    summary from an earlier run can never stand for this one."""
    bundle = Path(args.bundle).resolve()
    out_dir = Path(args.out or (bundle.parent / "build" / "uitest")).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    run_id = time.strftime("%Y%m%dT%H%M%S") + "-" + os.urandom(3).hex()
    summary = {"run_id": run_id, "status": "running", "runner": RUNNER_VERSION, "bundle": str(bundle),
               "scenarios": str(Path(args.scenarios).resolve()), "started": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
               "passed": 0, "failed": 0, "results": []}
    write_summary(out_dir, summary)

    def abort(message):
        summary.update(status="aborted", error=message, finished=time.strftime("%Y-%m-%dT%H:%M:%S%z"))
        write_summary(out_dir, summary)
        print(f"uitest: {message}", file=sys.stderr)
        return 2

    card_host = find_card_host(args.card_host)
    if not card_host:
        return abort("card-host not found; pass --card-host or set OCTO_CARD_HOST (scripts/setup.sh records it)")
    summary.update(card_host=card_host, card_host_sha256=sha256(Path(card_host)))
    if not (bundle / "main.splash").is_file():
        return abort(f"{bundle} has no main.splash; uitest runs script apps")
    summary["bundle_sha256"] = tree_digest(bundle)
    try:
        scenarios = load_scenarios(args.scenarios)
    except ScenarioError as e:
        return abort(str(e))
    results = summary["results"]
    try:
        with Display() as display:
            for path, sc in scenarios:
                sizes = sc.get("sizes") or [sc.get("size") or DEFAULT_SIZE]
                for size in sizes:
                    try:
                        r = run_one(card_host, bundle, path, sc, size, out_dir, display, run_id)
                    except ScenarioError as e:
                        return abort(f"{path}: {e}")
                    results.append(r)
                    summary["passed"] = sum(x["passed"] for x in results)
                    summary["failed"] = sum(not x["passed"] for x in results)
                    write_summary(out_dir, summary)
                    mark = "PASS" if r["passed"] else ("ENV " if r.get("environment_error") else "FAIL")
                    mem = f", {r['peak_rss_mb']} MB" if r.get("peak_rss_mb") else ""
                    print(f"{mark} {r['scenario']} @ {r['size']} ({r['seconds']}s{mem})")
                    for line in warnings_for(r):
                        print(f"     note: {line}")
                    if not r["passed"]:
                        print(f"     expected: {r['expected']}\n     actual:   {r['actual']}\n     feedback: {r['feedback']}")
                        if not args.keep_going:
                            break
                if results and not results[-1]["passed"] and not args.keep_going:
                    break
    except Exception as e:  # the display, the host or the disk: the environment, never a pass
        summary.update(status="environment_error", error=f"{type(e).__name__}: {e}",
                       finished=time.strftime("%Y-%m-%dT%H:%M:%S%z"))
        write_summary(out_dir, summary)
        print(f"uitest: environment error: {type(e).__name__}: {e}", file=sys.stderr)
        return 2
    except BaseException:
        summary.update(status="aborted", error="interrupted", finished=time.strftime("%Y-%m-%dT%H:%M:%S%z"))
        write_summary(out_dir, summary)
        raise
    env_error = any(r.get("environment_error") for r in results)
    summary["status"] = "environment_error" if env_error else ("passed" if summary["failed"] == 0 else "failed")
    summary["finished"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    write_summary(out_dir, summary)
    print(f"{summary['passed']} passed, {summary['failed']} failed; run {run_id}; details in {out_dir}")
    if env_error:
        return 2
    return 0 if summary["failed"] == 0 else 1


def cmd_doctor(args):
    ok = True
    card_host, source = find_card_host(args.card_host, with_source=True)
    if card_host:
        print(f"[ok] card-host: {card_host} (from {source})")
    else:
        print("[fail] card-host: not found; looked at " + ", ".join(s for s, _ in card_host_candidates(args.card_host))
              + ". Run scripts/setup.sh, or pass --card-host")
    ok &= bool(card_host)
    if sys.platform.startswith("linux") and not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
        x = shutil.which("Xvfb")
        print(f"[{'ok' if x else 'fail'}] display: none; Xvfb {'found at ' + x if x else 'missing (apt install xvfb)'}")
        ok &= bool(x)
    else:
        print("[ok] display: available")
    print(f"[ok] python {sys.version.split()[0]}")
    return 0 if ok else 2


def main(argv=None):
    p = argparse.ArgumentParser(prog="uitest.py", description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="run scenarios against a bundle")
    r.add_argument("bundle")
    r.add_argument("scenarios", help="a scenario .json file or a directory of them")
    r.add_argument("--card-host")
    r.add_argument("--out", help="evidence directory (default <app>/build/uitest)")
    r.add_argument("--keep-going", action="store_true", help="run every scenario even after a failure")
    d = sub.add_parser("doctor", help="check that card-host and a display are available")
    d.add_argument("--card-host")
    args = p.parse_args(argv)
    return cmd_run(args) if args.cmd == "run" else cmd_doctor(args)


if __name__ == "__main__":
    sys.exit(main())
