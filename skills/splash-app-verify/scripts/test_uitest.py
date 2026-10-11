"""uitest regressions that need no card-host: fixtures, the fake host source, selectors, checks, feedback."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import uitest  # noqa: E402

# Any executable file stands in for card-host where the host itself is faked;
# this one exists on every system the tests run on.
FAKE_CARD_HOST = sys.executable


def link_or_skip(test, link, target):
    """Make a symbolic link, or skip: Windows allows them only with a privilege."""
    try:
        link.symlink_to(target, target_is_directory=Path(target).is_dir())
    except (OSError, NotImplementedError) as e:
        test.skipTest(f"this system cannot make symbolic links here: {e}")

WIDGETS = [
    {"i": "title", "ty": "Label", "r": [16, 16, 380, 30], "t": "Titled Notes"},
    {"i": "entry", "ty": "TextInput", "r": [16, 60, 300, 40], "t": "", "value": "Call the plumber"},
    {"i": "keep_button", "ty": "ButtonFlat", "r": [320, 60, 76, 40], "t": "Keep", "enabled": True},
    {"i": "title_button", "ty": "ButtonFlat", "r": [16, 900, 160, 40], "t": "Suggest a title", "enabled": False},
    {"i": "", "ty": "Label", "r": [16, 120, 380, 20], "t": "No notes yet."},
]


class FakeApp:
    """A screen that never scrolls: probing a flush widget finds nothing moves."""

    def __init__(self, widgets, calls=(), files=None):
        self.widgets, self._calls, self.files = widgets, list(calls), files or {}

    def snap(self):
        return self.widgets

    def get(self, route, **params):
        assert route == "/m"

    def calls(self):
        return self._calls

    def find_file(self, name):
        return self.files.get(name)


class Fixtures(unittest.TestCase):
    def test_reply_forms(self):
        out = uitest.normalise_replies({
            "a.b": {"data": {"x": 1}},
            "c.d": [{"error": "nope", "delay": 1}, {"never": True}],
        })
        by = {e["service"]: e["replies"] for e in out}
        self.assertEqual(by["a.b"][0]["reply"], {"is_ok": True, "data": {"x": 1}, "error": ""})
        self.assertEqual(by["c.d"][0]["reply"]["is_ok"], False)
        self.assertEqual(by["c.d"][0]["delay"], 1.0)
        self.assertTrue(by["c.d"][1]["never"])

    def test_bad_reply_is_a_scenario_error(self):
        # A host answers each request once, so a streamed reply is not a fixture.
        for bad in ("yes", {"stream": [{"data": 1}]}, {"dta": 1}, []):
            with self.assertRaises(uitest.ScenarioError):
                uitest.normalise_replies({"a.b": bad})

    def test_shim_profiles(self):
        # OctoSense treats the manifest as a disclosure; Rinx refuses what it did not grant.
        src = uitest.shim_source({}, "octosense", ["storage"], "n0nce")
        head = src.split("fn uitest_answer")[0]
        self.assertIn('print("UITEST_READY_n0nce\\n")', head)       # ready before the app's first line
        self.assertIn('print("UITEST_CALL_n0nce " + {seq: uitest_seq, service: service', src)
        self.assertNotIn("fs.", src)                                  # the app's storage is left alone
        self.assertIn('\\"profile\\": \\"octosense\\"', src)
        rinx = uitest.shim_source({}, "rinx", ["matrix.read_messages"], "n0nce")
        self.assertIn('error: "Mini app was not granted " + service', rinx)
        self.assertIn('\\"declared\\": [\\"matrix.read_messages\\"]', rinx)
        self.assertIn("capabilities: fn(){ uitest_fx.declared }", rinx)
        with self.assertRaises(uitest.ScenarioError):
            uitest.shim_source({}, "android", [])

    def test_shim_embeds_fixtures_as_one_string(self):
        src = uitest.shim_source({"x.y": {"data": {"say": 'he said "hi"\\n'}}})
        self.assertTrue(src.startswith(uitest.SHIM_BEGIN))
        self.assertIn("let host = {request: fn(service, args, callback){", src)
        literal = src.split("let uitest_fx = ", 1)[1].split(".parse_json()", 1)[0]
        # Undo the Splash escapes and the JSON must round-trip.
        text, i, body = [], 0, literal[1:-1]
        while i < len(body):
            if body[i] == "\\":
                text.append({"n": "\n", "r": "\r", "t": "\t"}.get(body[i + 1], body[i + 1]))
                i += 2
            else:
                text.append(body[i])
                i += 1
        text = "".join(text)
        self.assertEqual(json.loads(text)["services"][0]["service"], "x.y")

    def test_splash_string_escapes(self):
        self.assertEqual(uitest.splash_string('a"b\\c\nd'), '"a\\"b\\\\c\\nd"')

    def test_prepare_copy_leaves_the_original(self):
        with tempfile.TemporaryDirectory() as t:
            bundle = Path(t) / "bundle"
            bundle.mkdir()
            (bundle / "main.splash").write_text("let x = 1\n", encoding="utf-8")
            (bundle / "manifest.json").write_text(json.dumps({"id": "a", "capabilities": ["model"],
                                                              "integrity": {"bundle_blake3": "", "signature": {"k": 1}}}), encoding="utf-8")
            work = Path(t) / "work"
            work.mkdir()
            copy, lines = uitest.prepare_copy(bundle, work, {"host": {}}, "n0nce")
            self.assertEqual((bundle / "main.splash").read_text(encoding="utf-8"), "let x = 1\n")
            self.assertTrue((copy / "main.splash").read_text(encoding="utf-8").endswith("let x = 1\n"))
            self.assertIn("UITEST_READY_n0nce", (copy / "main.splash").read_text(encoding="utf-8"))
            self.assertGreater(lines, 10)
            manifest = json.loads((copy / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["capabilities"], ["model"])     # nothing added: no storage for the runner
            self.assertNotIn("signature", manifest["integrity"])
            work2 = Path(t) / "w2"
            work2.mkdir()
            copy2, lines2 = uitest.prepare_copy(bundle, work2, {"fake_host": False})
            self.assertEqual(lines2, 0)
            self.assertEqual((copy2 / "main.splash").read_text(encoding="utf-8"), "let x = 1\n")
            (bundle / "manifest.json").write_text(json.dumps({"id": "../escape", "capabilities": []}), encoding="utf-8")
            with self.assertRaises(uitest.ScenarioError):
                uitest.prepare_copy(bundle, Path(t) / "w3", {})


class Checks(unittest.TestCase):
    view = [0, 0, 412, 892]

    def test_selectors(self):
        self.assertEqual(uitest.find(WIDGETS, "Keep")[1]["i"], "keep_button")
        self.assertEqual(uitest.find(WIDGETS, {"id": "entry"})[1]["ty"], "TextInput")
        self.assertEqual(uitest.find(WIDGETS, {"contains": "plumber"})[1]["i"], "entry")
        self.assertIsNone(uitest.find(WIDGETS, "Kee")[1])
        self.assertEqual(len(uitest.find(WIDGETS, {"type": "ButtonFlat"})[0]), 2)

    def test_after_picks_the_button_in_the_same_card(self):
        rows = [{"i": "", "ty": "Label", "r": [0, 0, 300, 20], "t": "Route A: noon"},
                {"i": "", "ty": "Button", "r": [0, 24, 80, 28], "t": "Use"},
                {"i": "", "ty": "Label", "r": [0, 60, 300, 20], "t": "Route B: evening"},
                {"i": "", "ty": "Button", "r": [0, 84, 80, 28], "t": "Use"}]
        _, w = uitest.find(rows, {"text": "Use", "after": {"contains": "Route B"}})
        self.assertEqual(w["r"][1], 84)
        self.assertIsNone(uitest.find(rows, {"text": "Use", "after": {"contains": "Route C"}})[1])

    def test_after_counts_from_the_anchor_itself_not_an_equal_widget(self):
        # Two cards with the same heading report equal widgets; "after" the second must start after the second.
        head = {"i": "", "ty": "Label", "r": [0, 0, 300, 20], "t": "Today"}
        rows = [head, {"i": "", "ty": "Button", "r": [0, 24, 80, 28], "t": "Use", "value": "x"},
                dict(head), {"i": "", "ty": "Button", "r": [0, 84, 80, 28], "t": "Use", "value": "y"}]
        _, w = uitest.find(rows, {"text": "Use", "after": {"text": "Today", "nth": 1}})
        self.assertEqual(w["value"], "y")

    class Pane:
        """A scroll view at y 50..440; /snap lists only the visible part of each child, as card-host does."""

        def __init__(self, items, content_bottom):
            self.items, self.offset = items, 0.0
            self.max_offset = max(0.0, content_bottom - 440)
            self.scrolls = 0

        def snap(self):
            out = [{"i": "app_scroll", "ty": "View", "r": [8, 50, 938, 390], "t": ""}]
            for i, t, (x, y, w, h) in self.items:
                top, bottom = max(y - self.offset, 50), min(y - self.offset + h, 440)
                if bottom > top:
                    out.append({"i": i, "ty": "Button", "r": [x, top, w, bottom - top], "t": t})
            return out

        def get(self, route, **params):
            assert route == "/m" and params["k"] == "scroll"
            self.scrolls += 1
            self.offset = min(self.max_offset, max(0.0, self.offset + float(params["dy"]) * 0.5))

    def test_a_widget_cut_off_by_a_scroll_view_is_not_in_view(self):
        pane = self.Pane([("go", "Go", (18, 342, 89, 28)), ("cue_draft", "draft", (67, 433, 869, 70))], 560)
        widgets = pane.snap()
        cut = uitest.find(widgets, {"id": "cue_draft"})[1]
        self.assertEqual(cut["r"][3], 7)  # only 7 points of it show
        uitest.check_expectation(pane, {"in_view": ["Go"]}, [0, 0, 954, 448])
        with self.assertRaises(uitest.StepFailed) as e:
            uitest.check_expectation(pane, {"in_view": [{"id": "cue_draft"}]}, [0, 0, 954, 448])
        self.assertIn("cuts it off", e.exception.actual)
        self.assertEqual(pane.offset, 0.0)  # the probe scrolled back

    def test_a_whole_widget_flush_with_the_edge_is_in_view(self):
        # Content ends exactly at the scroll view's edge: nothing scrolls, so nothing is hidden.
        end = self.Pane([("send", "Send", (18, 412, 89, 28))], 440)
        uitest.check_expectation(end, {"in_view": ["Send"]}, [0, 0, 954, 448])
        # More content below, but this widget is whole: scrolling moves it without growing it.
        more = self.Pane([("send", "Send", (18, 412, 89, 28)), ("next", "Next", (18, 460, 89, 28))], 520)
        uitest.check_expectation(more, {"in_view": ["Send"]}, [0, 0, 954, 448])
        self.assertEqual(more.offset, 0.0)

    def test_calls_excludes(self):
        app = FakeApp(WIDGETS, calls=[{"service": "model.complete", "args": {"text": "[[1, \"noon\"]]"}}])
        uitest.check_expectation(app, {"calls": [{"service": "model.complete", "excludes": "ann"}]}, self.view)
        with self.assertRaises(uitest.StepFailed):
            uitest.check_expectation(app, {"calls": [{"service": "model.complete", "excludes": "noon"}]}, self.view)

    def test_text_is_never_matched_across_two_widgets(self):
        app = FakeApp([{"i": "", "ty": "Label", "r": [0, 0, 100, 20], "t": "first"},
                       {"i": "", "ty": "Label", "r": [0, 30, 100, 20], "t": "second"}])
        with self.assertRaises(uitest.StepFailed):
            uitest.check_expectation(app, {"text": ["first\nsecond"]}, self.view)
        uitest.check_expectation(app, {"absent": ["first\nsecond"]}, self.view)

    def test_absent_takes_a_selector(self):
        app = FakeApp(WIDGETS + [{"i": "", "ty": "Label", "r": [16, 150, 380, 20], "t": "Keep a note to see more"}])
        uitest.check_expectation(app, {"absent": [{"type": "Label", "text": "Keep"}]}, self.view)
        with self.assertRaises(uitest.StepFailed):
            uitest.check_expectation(app, {"absent": [{"type": "ButtonFlat", "text": "Keep"}]}, self.view)

    def test_a_whole_widget_flush_with_a_still_root_is_in_view(self):
        root = {"i": "root", "ty": "SolidView", "r": [0, 0, 412, 892], "t": ""}
        button = {"i": "go", "ty": "Button", "r": [16, 0, 80, 40], "t": "Go"}
        uitest.check_expectation(FakeApp([root, button]), {"in_view": ["Go"]}, root["r"])

    def test_text_and_absent(self):
        app = FakeApp(WIDGETS)
        uitest.check_expectation(app, {"text": ["No notes yet.", "plumber"], "absent": ["Kept."]}, self.view)
        with self.assertRaises(uitest.StepFailed) as e:
            uitest.check_expectation(app, {"text": ["Kept."]}, self.view)
        self.assertIn("not on screen", e.exception.actual)

    def test_in_view_reports_the_overflow(self):
        app = FakeApp(WIDGETS)
        uitest.check_expectation(app, {"in_view": ["Keep"]}, self.view)
        with self.assertRaises(uitest.StepFailed) as e:
            uitest.check_expectation(app, {"in_view": ["Suggest a title"]}, self.view)
        self.assertIn("bottom by 48", e.exception.actual)

    def test_enabled_count_calls_files(self):
        with tempfile.TemporaryDirectory() as t:
            f = Path(t) / "notes.json"
            f.write_text('{"notes":["a"]}', encoding="utf-8")
            app = FakeApp(WIDGETS, calls=[{"service": "model.complete", "args": {"input": {"note": "a"}}}],
                          files={"notes.json": f})
            uitest.check_expectation(app, {"enabled": ["Keep"], "disabled": ["Suggest a title"],
                                           "count": [{"of": {"type": "ButtonFlat"}, "n": 2}],
                                           "calls": [{"service": "model.complete", "count": 1, "contains": "note"}],
                                           "files": [{"name": "notes.json", "contains": ["notes"]},
                                                     {"name": "other.json", "missing": True}]}, self.view)
            for bad in ({"enabled": ["Suggest a title"]}, {"calls": [{"service": "mail.send"}]},
                        {"files": [{"name": "notes.json", "missing": True}]},
                        {"count": [{"of": {"type": "ButtonFlat"}, "n": 3}]}):
                with self.assertRaises(uitest.StepFailed):
                    uitest.check_expectation(app, bad, self.view)

    def test_feedback_has_the_template_parts(self):
        text = uitest.feedback({"scenario": "keep", "size": "412x892", "viewport": self.view,
                                "source_sha256": "abc", "file": "tests/02-keep.json",
                                "steps_run": [{"click": "Keep"}], "expected": 'text "Kept." is shown',
                                "actual": "not on screen", "detail": {"similar": []},
                                "evidence": {"snap": "snap.json", "log": "card-host.log"}}, "/app/bundle", "/bin/card-host")
        for part in ("Artifact:", "Runtime:", "Start state:", "Steps", "Expected:", "Actual:", "Evidence:", "Fix:", "Retest:"):
            self.assertIn(part, text)


class Scenarios(unittest.TestCase):
    def test_examples_are_valid(self):
        root = Path(__file__).resolve().parent.parent / "examples"
        files = sorted(root.glob("*/tests/*.json"))
        self.assertTrue(files)
        for f in files:
            for _, sc in uitest.load_scenarios(f):
                uitest.normalise_replies(sc.get("host"))
                for step in sc["steps"]:
                    self.assertTrue(set(step) & {"click", "type", "key", "scroll", "sleep", "expect", "wait"}, f)

    def test_broken_scenario_is_reported(self):
        for body in ('{"name": "no steps"}', '{"steps": [{"clik": "Keep"}]}', '{"steps": [{"run": "_missing.json"}]}'):
            with tempfile.TemporaryDirectory() as t:
                (Path(t) / "x.json").write_text(body, encoding="utf-8")
                with self.assertRaises(uitest.ScenarioError):
                    uitest.load_scenarios(t)

    def test_parts_share_fixtures_and_steps(self):
        with tempfile.TemporaryDirectory() as t:
            d = Path(t)
            (d / "_room.json").write_text(json.dumps({
                "sizes": ["412x892", "954x448"],
                "host": {"a.read": {"data": {"rows": [1]}}, "a.info": {"data": {"id": "r"}}},
                "storage": {"s.json": "{}"},
                "steps": [{"click": "Load"}, {"wait": {"text": ["1 row"]}}]}), encoding="utf-8")
            (d / "02-x.json").write_text(json.dumps({
                "use": "_room.json",
                "host": {"a.read": {"error": "expired"}},
                "steps": [{"run": "_room.json"}, {"expect": {"text": ["expired"]}, "note": "why"}]}), encoding="utf-8")
            (d / "01-plain.json").write_text('{"steps": [{"sleep": 0}]}', encoding="utf-8")
            scenarios = uitest.load_scenarios(d)
            self.assertEqual([f.name for f, _ in scenarios], ["01-plain.json", "02-x.json"])
            sc = scenarios[1][1]
            self.assertEqual(sc["sizes"], ["412x892", "954x448"])
            self.assertEqual(sc["host"]["a.read"], {"error": "expired"})   # the scenario wins
            self.assertEqual(sc["host"]["a.info"], {"data": {"id": "r"}})  # the part fills in
            self.assertEqual(sc["storage"], {"s.json": "{}"})
            self.assertEqual([list(s)[0] for s in sc["steps"]], ["click", "wait", "expect"])


class Scrolling(unittest.TestCase):
    class Scroller:
        """A column of widgets under a 400-point viewport; /m scroll moves them by dy * 0.5."""

        def __init__(self, target_y):
            self.offset, self.target_y, self.scrolls = 0.0, target_y, 0

        def snap(self):
            return [{"i": "top", "ty": "Label", "r": [0, 10 - self.offset, 100, 20], "t": "Top"},
                    {"i": "go", "ty": "ButtonFlat", "r": [0, self.target_y - self.offset, 80, 28], "t": "Send"}]

        def get(self, route, **params):
            assert route == "/m" and params["k"] == "scroll"
            self.scrolls += 1
            self.offset = max(0.0, self.offset + float(params["dy"]) * 0.5)

    def test_scrolls_until_in_view_whatever_the_scroll_unit(self):
        s = self.Scroller(target_y=1300)
        uitest.scroll_into_view(s, "Send", None, [0, 0, 400, 400], 10)
        y = s.target_y - s.offset
        self.assertTrue(0 <= y and y + 28 <= 400, y)
        self.assertLessEqual(s.scrolls, 4)

    def test_reports_when_scrolling_stops(self):
        s = self.Scroller(target_y=1300)
        s.get = lambda route, **p: None   # nothing moves
        with self.assertRaises(uitest.StepFailed) as e:
            uitest.scroll_into_view(s, "Send", None, [0, 0, 400, 400], 10)
        self.assertIn("no longer moves", e.exception.actual)


class Safety(unittest.TestCase):
    """Scenario files come from the repository under test: they must not reach outside the run."""

    def test_storage_names_cannot_leave_the_jail(self):
        with tempfile.TemporaryDirectory() as t:
            jail = Path(t) / "data" / "app"
            jail.mkdir(parents=True)
            self.assertEqual(uitest.jail_path(jail, "notes.json"), (jail / "notes.json").resolve())
            self.assertEqual(uitest.jail_path(jail, "sub/notes.json"), (jail / "sub/notes.json").resolve())
            for bad in ("../escape.txt", "a/../../escape.txt", "/tmp/escape.txt", "C:\\x", "a\\b", "*.json", "", None):
                with self.assertRaises(uitest.ScenarioError, msg=repr(bad)):
                    uitest.jail_path(jail, bad)
            self.assertFalse((Path(t) / "data" / "escape.txt").exists())
            # Refused when the scenario loads, before anything is written.
            d = Path(t) / "tests"
            d.mkdir()
            (d / "01.json").write_text(json.dumps({"storage": {"../../x": "1"}, "steps": [{"sleep": 0}]}), encoding="utf-8")
            with self.assertRaises(uitest.ScenarioError):
                uitest.load_scenarios(d)
            (d / "01.json").write_text(json.dumps({"steps": [{"wait": {"files": [{"name": "/etc/passwd"}]}}]}), encoding="utf-8")
            with self.assertRaises(uitest.ScenarioError):
                uitest.load_scenarios(d)

    def test_a_link_in_the_bundle_is_refused_before_anything_is_written(self):
        with tempfile.TemporaryDirectory() as t:
            outside = Path(t) / "outside-source.splash"
            outside.write_text("let x = 1\n", encoding="utf-8")
            bundle = Path(t) / "bundle"
            bundle.mkdir()
            link_or_skip(self, bundle / "main.splash", outside)
            (bundle / "manifest.json").write_text(json.dumps({"id": "a", "capabilities": []}), encoding="utf-8")
            with self.assertRaises(uitest.ScenarioError):
                uitest.prepare_copy(bundle, Path(t) / "work", {"host": {}}, "n0nce")
            self.assertEqual(outside.read_text(encoding="utf-8"), "let x = 1\n")        # untouched
            (bundle / "main.splash").unlink()
            (bundle / "main.splash").write_text("let x = 1\n", encoding="utf-8")
            (bundle / "assets").mkdir()
            link_or_skip(self, bundle / "assets" / "up", Path(t))       # a directory link counts too
            with self.assertRaises(uitest.ScenarioError):
                uitest.prepare_copy(bundle, Path(t) / "work2", {"host": {}}, "n0nce")

    def test_values_of_the_wrong_type_are_refused(self):
        bad = [
            {"allow_runtime_errors": "false", "steps": [{"sleep": 0}]},
            {"fake_host": "false", "steps": [{"sleep": 0}]},
            {"sizes": ["412*892"], "steps": [{"sleep": 0}]},
            {"viewport": [0, 0, 412], "steps": [{"sleep": 0}]},
            {"startup_timeout": True, "steps": [{"sleep": 0}]},
            {"steps": [{"click": "Keep", "allow_runtime_errors": "false"}]},
            {"steps": [{"wait": {"files": [{"name": "a.json", "missing": "false", "contains": ["x"]}]}}]},
            {"steps": [{"wait": {"files": [{"name": "a.json", "missing": True, "contains": ["x"]}]}}]},
            {"steps": [{"wait": {"count": [{"of": "Keep", "n": True}]}}]},
            {"steps": [{"wait": {"calls": [{"service": "a.b", "count": False}]}}]},
            {"steps": [{"click": {"text": "Use", "nth": True}}]},
            {"steps": [{"click": {"id": 3}}]},
            {"steps": [{"type": {"into": "entry", "text": "x", "clear": "yes"}}]},
            {"steps": [{"sleep": float("inf")}]},
            {"steps": [{"wait": {"text": ["x"]}, "timeout": "5"}]},
        ]
        for body in bad:
            with tempfile.TemporaryDirectory() as t:
                (Path(t) / "x.json").write_text(json.dumps(body), encoding="utf-8")
                with self.assertRaises(uitest.ScenarioError, msg=json.dumps(body)):
                    uitest.load_scenarios(t)

    def test_unknown_keys_are_refused_not_ignored(self):
        bad_steps = [
            {"expect": {"texts": ["Kept."]}},                       # a typo would have passed silently
            {"expect": {"text": "Kept."}},                          # a string, not a list
            {"expect": {"calls": [{"servce": "model.complete", "count": 0}]}},
            {"expect": {"calls": [{"service": "model.complete", "cont": "x"}]}},
            {"expect": {"count": [{"of": {"type": "Button"}, "n": "2"}]}},
            {"expect": {"files": [{"name": "a.json", "contain": ["x"]}]}},
            {"click": {"contain": "Keep"}},
            {"click": "Keep", "expect": {"text": ["Kept."]}},       # two actions in one step
            {"wait": {"text": ["x"]}, "timeot": 3},
            {"type": {"into": "entry", "txt": "hi"}},
            {"scroll_to": "Send", "on": {"idd": "list"}},
        ]
        for step in bad_steps:
            with tempfile.TemporaryDirectory() as t:
                (Path(t) / "x.json").write_text(json.dumps({"steps": [step]}), encoding="utf-8")
                with self.assertRaises(uitest.ScenarioError, msg=json.dumps(step)):
                    uitest.load_scenarios(t)
        with tempfile.TemporaryDirectory() as t:
            (Path(t) / "x.json").write_text(json.dumps({"storge": {}, "steps": [{"sleep": 0}]}), encoding="utf-8")
            with self.assertRaises(uitest.ScenarioError):
                uitest.load_scenarios(t)
            (Path(t) / "x.json").write_text(json.dumps({"fake_host": False,
                                                        "steps": [{"expect": {"calls": [{"service": "a.b"}]}}]}), encoding="utf-8")
            with self.assertRaises(uitest.ScenarioError):
                uitest.load_scenarios(t)
            (Path(t) / "x.json").write_text(json.dumps({"host_profile": "rinx", "steps": [
                {"click": {"text": "Use", "after": {"contains": "B"}, "nth": 0}, "note": "why"},
                {"wait": {"calls": [{"service": "a.b", "count": 0, "excludes": "x"}]}, "timeout": 3}]}), encoding="utf-8")
            self.assertEqual(uitest.load_scenarios(t)[0][1]["host_profile"], "rinx")

    def test_malformed_files_are_scenario_errors_never_crashes(self):
        # Found by mutating the shipped scenarios at random: each of these used to
        # raise TypeError, ValueError or UnicodeEncodeError instead of a clear
        # scenario error (exit status 2), or to be accepted.
        ok = '[{"sleep": 0}]'
        deep_after = {"text": "x"}
        for _ in range(12):
            deep_after = {"text": "x", "after": deep_after}
        cases = [
            # host and storage of the wrong kind, in the scenario or in a part
            '{"host": "x", "steps": %s}' % ok,
            '{"host": [1], "steps": %s}' % ok,
            '{"host": null, "steps": %s}' % ok,
            '{"storage": "0x0", "steps": %s}' % ok,
            '{"use": "_bad_host.json", "steps": %s}' % ok,
            '{"use": "_bad_storage.json", "steps": %s}' % ok,
            # "use" that is not a part name or a list of them
            '{"use": 5, "steps": %s}' % ok,
            '{"use": [{"a": 1}], "steps": %s}' % ok,
            '{"use": [""], "steps": %s}' % ok,
            # a typo in a part, however it is used; a part does not take other parts
            '{"use": "_typo.json", "steps": %s}' % ok,
            '{"steps": [{"run": "_typo.json"}]}',
            '{"use": "_nested.json", "steps": %s}' % ok,
            '{"steps": [{"run": "_nested.json"}]}',
            '{"steps": [{"run": ""}]}',
            # replies
            '{"host": {"a.b": {"data": 1, "delay": "soon"}}, "steps": %s}' % ok,
            '{"host": {"a.b": {"data": 1, "delay": -1}}, "steps": %s}' % ok,
            '{"host": {"a.b": {"data": 1, "delay": 3000}}, "steps": %s}' % ok,
            '{"host": {"a.b": {"data": 1, "delay": true}}, "steps": %s}' % ok,
            '{"host": {"a.b": {"never": false}}, "steps": %s}' % ok,
            '{"host": {"a.b": {"data": 1, "error": "x"}}, "steps": %s}' % ok,
            '{"host": {"a.b": {"error": 5}}, "steps": %s}' % ok,
            '{"host": {"a.b": {"data": 1, "dealy": 2}}, "steps": %s}' % ok,
            '{"host": {"": {"data": 1}}, "steps": %s}' % ok,
            # text that is not UTF-8 (a lone surrogate escape), as a value or a key
            '{"name": "\\ud800", "steps": %s}' % ok,
            '{"host": {"a.b": {"data": {"\\udcff": 1}}}, "steps": %s}' % ok,
            '{"steps": [{"click": "\\udcff"}]}',
            # numbers JSON does not have, and nesting no scenario needs
            '{"steps": [{"sleep": NaN}]}',
            '{"host": {"a.b": {"data": Infinity}}, "steps": %s}' % ok,
            "[" * 100000,
            json.dumps({"steps": [{"click": deep_after}]}),
            # times: seconds, and never so large that a wait overflows or never ends
            '{"steps": [{"sleep": 601}]}',
            '{"steps": [{"sleep": 1e300}]}',
            '{"steps": [{"wait": {"text": ["x"]}, "timeout": 1e300}]}',
            '{"startup_timeout": 1e12, "steps": %s}' % ok,
            '{"steps": [{"scroll_to": "x", "max": 1000000000}]}',
            # check lists that are not lists
            '{"steps": [{"wait": {"count": 5}}]}',
            '{"steps": [{"wait": {"calls": 5}}]}',
            '{"steps": [{"wait": {"files": {"name": "a"}}}]}',
            # storage and file names that name no file, or hold a control character
            '{"storage": {".": "x"}, "steps": %s}' % ok,
            '{"storage": {"a/": "x"}, "steps": %s}' % ok,
            '{"storage": {"a\\u0000b": "x"}, "steps": %s}' % ok,
            '{"steps": [{"wait": {"files": [{"name": "a\\nb"}]}}]}',
            # names the filesystem cannot hold fail at load, not once the app runs
            '{"steps": [{"wait": {"files": [{"name": "%s"}]}}]}' % ("x" * 256),
            '{"storage": {"%s": "x"}, "steps": %s}' % ("/".join(["d" * 200] * 6), ok),
        ]
        parts = {"_bad_host.json": '{"host": [1]}', "_bad_storage.json": '{"storage": "x"}',
                 "_typo.json": '{"hots": {}, "steps": [{"sleep": 0}]}',
                 "_nested.json": '{"use": "_bad_host.json", "steps": [{"sleep": 0}]}'}
        for text in cases:
            with tempfile.TemporaryDirectory() as t:
                for name, body in parts.items():
                    (Path(t) / name).write_text(body, encoding="utf-8")
                (Path(t) / "x.json").write_text(text, encoding="utf-8")
                with self.assertRaises(uitest.ScenarioError, msg=text[:120]):
                    uitest.load_scenarios(Path(t) / "x.json")

    def test_a_jail_the_runner_cannot_read_is_an_evidence_error(self):
        with tempfile.TemporaryDirectory() as t:
            jail = Path(t) / "jail"
            jail.mkdir()
            app = type("A", (), {"jail": jail, "find_file": uitest.App.find_file})()
            real = Path.is_symlink
            def denied(self):
                raise PermissionError(13, "Permission denied", str(self))
            Path.is_symlink = denied
            try:
                with self.assertRaises(uitest.EvidenceError):
                    app.find_file("notes/a.json")
            finally:
                Path.is_symlink = real

    def test_strict_loading_keeps_every_documented_form(self):
        with tempfile.TemporaryDirectory() as t:
            (Path(t) / "_room.json").write_text(json.dumps({
                "host_profile": "rinx", "sizes": ["412x892"], "note": "shared",
                "host": {"a.b": [{"data": None}, {"error": "", "delay": 0}, {"never": True, "delay": 600}],
                         "*": {"error": "down", "note": "everything else"}},
                "storage": {"notes/a.json": {"x": 1}}}), encoding="utf-8")
            (Path(t) / "_load.json").write_text(json.dumps({"description": "load", "steps": [{"sleep": 0}]}), encoding="utf-8")
            (Path(t) / "x.json").write_text(json.dumps({
                "use": ["_room.json"], "startup_timeout": 600,
                "steps": [{"run": "_load.json", "note": "load"}, {"sleep": 600, "allow_runtime_errors": True},
                          {"wait": {"text": ["x"]}, "timeout": 0},
                          {"scroll_to": "x", "max": 1000}]}), encoding="utf-8")
            sc = uitest.load_scenarios(Path(t) / "x.json")[0][1]
        self.assertEqual(sc["host_profile"], "rinx")
        self.assertEqual(len(sc["steps"]), 4)
        by = {e["service"]: e["replies"] for e in uitest.normalise_replies(sc["host"])}
        self.assertEqual([r["never"] for r in by["a.b"]], [False, False, True])
        self.assertEqual(by["a.b"][1]["reply"], {"is_ok": False, "data": None, "error": ""})

    def test_an_unreadable_call_log_is_not_zero_calls(self):
        log = {"text": ""}

        class Logged:
            nonce = "n0nce"

            def log_text(self):
                return log["text"]

        calls = lambda: uitest.App.calls(Logged())
        with self.assertRaises(uitest.EvidenceError):
            calls()                                        # no ready line: the fake host never ran
        log["text"] = "UITEST_READY_n0nce\n"
        self.assertEqual(calls(), [])                      # ready and no calls: really no calls
        log["text"] += 'UITEST_CALL_n0nce {"seq":1,"service":"a.b","args":{},"declared":true}\n'
        log["text"] += 'UITEST_CALL_guess {"seq":9,"service":"forged"}\n'      # the app cannot guess the nonce
        self.assertEqual([c["service"] for c in calls()], ["a.b"])
        log["text"] += 'UITEST_CALL_n0nce {"seq":2,"service":"octos.turn.start","args":{"text":"sec'   # being written
        with self.assertRaises(uitest.PendingEvidence):    # while the host runs: wait, do not count
            calls()
        with self.assertRaises(uitest.EvidenceError):      # after it closed: incomplete evidence
            uitest.App.calls(Logged(), final=True)
        # A "count 0" or "excludes" check cannot pass on a record that is still being written.
        app = FakeApp(WIDGETS)
        app.calls = lambda: uitest.App.calls(Logged())
        with self.assertRaises(uitest.StepFailed):
            uitest.check_expectation(app, {"calls": [{"service": "octos.turn.start", "excludes": "secret"}]}, [0, 0, 412, 892])
        log["text"] += 'ret"}}\nUITEST_CALL_n0nce {"seq":4,"service":"x"}\n'
        with self.assertRaises(uitest.EvidenceError):      # seq 3 is missing
            calls()
        log["text"] = 'UITEST_READY_n0nce\nUITEST_CALL_n0nce {broken\n'
        with self.assertRaises(uitest.EvidenceError):
            calls()

        class Broken(FakeApp):
            def calls(self):
                raise uitest.EvidenceError("unreadable")
        # A "count 0" or "excludes" check must not pass on evidence it cannot read.
        for exp in ({"calls": [{"service": "matrix.send_message", "count": 0}]},
                    {"calls": [{"service": "octos.turn.start", "excludes": "secret"}]}):
            with self.assertRaises(uitest.EvidenceError):
                uitest.check_expectation(Broken(WIDGETS), exp, [0, 0, 412, 892])

    def test_a_file_check_reads_exactly_the_named_path(self):
        with tempfile.TemporaryDirectory() as t:
            jail = Path(t) / "data" / "app"
            (jail / "backup" / "state").mkdir(parents=True)
            (jail / "backup" / "state" / "notes.json").write_text("kept", encoding="utf-8")
            app = uitest.App.__new__(uitest.App)
            app.jail = jail
            app.snap = lambda: []
            self.assertIsNone(app.find_file("state/notes.json"))  # a backup of the same name does not count
            with self.assertRaises(uitest.StepFailed):
                uitest.check_expectation(app, {"files": [{"name": "state/notes.json", "contains": ["kept"]}]},
                                         [0, 0, 412, 892])
            (jail / "state").mkdir()
            (jail / "state" / "notes.json").write_text("kept", encoding="utf-8")
            self.assertEqual(app.find_file("state/notes.json"), jail / "state" / "notes.json")
            outside = Path(t) / "outside.txt"
            outside.write_text("secret", encoding="utf-8")
            link_or_skip(self, jail / "link.txt", outside)
            self.assertIsNone(app.find_file("link.txt"))           # a link is not the app's own file
            self.assertNotIn(jail / "link.txt", uitest.app_files(jail))

    def test_runtime_errors_include_budget_stops_and_parse_errors(self):
        for line in ("splash: probe is stopped: its instruction budget is spent",
                     "splash: an app spent its instruction budget evaluating its body and is stopped",
                     "splash host: an app spent its instruction budget in a callback and is stopped",
                     "splash: splash:35135094784:0:0: expected expression",
                     "[E] splash: boom"):
            self.assertTrue(uitest.is_runtime_error(line), line)
        self.assertFalse(uitest.is_runtime_error("UITEST_CALL_x {}"))


class Housekeeping(unittest.TestCase):
    def test_a_failing_evidence_step_still_closes_the_host(self):
        closed = []

        class Host:
            def __init__(self, card_host, bundle, data_dir, size, log_path, env, jail=None, nonce=None):
                Path(log_path).write_text("", encoding="utf-8")
                self.line_offset = 0

            def wait_ready(self, timeout):
                pass

            def new_runtime_errors(self):
                return []

            def calls(self, final=False):
                raise uitest.EvidenceError("the call log is unreadable")

            def peak_rss_mb(self):
                raise OSError("no /proc")

            def close(self):
                closed.append(True)

        with tempfile.TemporaryDirectory() as t:
            bundle = Path(t) / "bundle"
            bundle.mkdir()
            (bundle / "main.splash").write_text("let x = 1\n", encoding="utf-8")
            (bundle / "manifest.json").write_text(json.dumps({"id": "a", "capabilities": []}), encoding="utf-8")
            real, uitest.App = uitest.App, Host
            before = set(Path(tempfile.gettempdir()).glob("uitest-*"))
            try:
                r = uitest.run_one(FAKE_CARD_HOST, bundle, Path(t) / "01.json", {"steps": [], "storage": {"n.json": "{}"}},
                                   "412x892", Path(t) / "out", type("D", (), {"env": {}})())
            finally:
                uitest.App = real
            self.assertEqual(closed, [True])
            self.assertFalse(r["passed"])                       # unreadable evidence is not a pass
            self.assertTrue(r["environment_error"])
            self.assertIn("unreadable", r["evidence"]["calls_error"])
            self.assertTrue((Path(t) / "out" / "01@412x892" / "result.json").is_file())
            self.assertEqual(set(Path(tempfile.gettempdir()).glob("uitest-*")) - before, set())
            self.assertTrue(any("call log" in n for n in uitest.warnings_for(r)))

    def test_a_failed_rerun_never_leaves_the_last_green_summary(self):
        with tempfile.TemporaryDirectory() as t:
            bundle = Path(t) / "bundle"
            bundle.mkdir()
            (bundle / "main.splash").write_text("let x = 1\n", encoding="utf-8")
            (bundle / "manifest.json").write_text(json.dumps({"id": "a", "capabilities": []}), encoding="utf-8")
            scenario = Path(t) / "case.json"
            scenario.write_text('{"steps": [{"sleep": 0}]}', encoding="utf-8")
            out = Path(t) / "out"

            class Host:
                def __init__(self, *a, **k):
                    Path(a[4]).write_text("", encoding="utf-8")
                    self.line_offset = 0
                    self.proc = None

                def wait_ready(self, timeout): pass
                def new_runtime_errors(self): return []
                def calls(self, final=False): return []
                def peak_rss_mb(self): return None
                def close(self): pass

            class NoDisplay:
                env = {}
                def __enter__(self): return self
                def __exit__(self, *a): pass

            real = (uitest.App, uitest.Display, uitest.find_card_host)
            uitest.App, uitest.Display, uitest.find_card_host = Host, NoDisplay, lambda *a, **k: FAKE_CARD_HOST
            try:
                argv = ["run", str(bundle), str(scenario), "--out", str(out)]
                self.assertEqual(uitest.main(argv), 0)
                first = json.loads((out / "summary.json").read_text(encoding="utf-8"))
                self.assertEqual((first["status"], first["passed"]), ("passed", 1))
                scenario.write_text('{"host": {"a.b": {"dta": 1}}, "steps": []}', encoding="utf-8")
                self.assertEqual(uitest.main(argv), 2)
            finally:
                uitest.App, uitest.Display, uitest.find_card_host = real
            second = json.loads((out / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(second["status"], "aborted")
            self.assertNotEqual(second["run_id"], first["run_id"])
            self.assertEqual(second["passed"], 0)
            self.assertIn("dta", second["error"])
            self.assertEqual(len(first["bundle_sha256"]), 64)

    def test_a_host_that_fails_to_close_still_leaves_a_result(self):
        class Host:
            def __init__(self, *a, **k):
                Path(a[4]).write_text("", encoding="utf-8")
                self.line_offset = 0

            def wait_ready(self, timeout): pass
            def new_runtime_errors(self): return []
            def calls(self, final=False): return []
            def peak_rss_mb(self): return None

            def close(self):
                raise OSError("the process vanished while it was being stopped")

        with tempfile.TemporaryDirectory() as t:
            bundle = Path(t) / "bundle"
            bundle.mkdir()
            (bundle / "main.splash").write_text("let x = 1\n", encoding="utf-8")
            (bundle / "manifest.json").write_text(json.dumps({"id": "a", "capabilities": []}), encoding="utf-8")
            real, uitest.App = uitest.App, Host
            before = set(Path(tempfile.gettempdir()).glob("uitest-*"))
            try:
                r = uitest.run_one(FAKE_CARD_HOST, bundle, Path(t) / "01.json", {"steps": []}, "412x892",
                                   Path(t) / "out", type("D", (), {"env": {}})())
            finally:
                uitest.App = real
            self.assertTrue(r["environment_error"])
            self.assertIn("vanished", r["evidence"]["close_error"])
            self.assertTrue((Path(t) / "out" / "01@412x892" / "result.json").is_file())
            self.assertEqual(set(Path(tempfile.gettempdir()).glob("uitest-*")) - before, set())

    def test_no_display_ends_the_summary_as_an_environment_error(self):
        with tempfile.TemporaryDirectory() as t:
            bundle = Path(t) / "bundle"
            bundle.mkdir()
            (bundle / "main.splash").write_text("let x = 1\n", encoding="utf-8")
            (bundle / "manifest.json").write_text(json.dumps({"id": "a", "capabilities": []}), encoding="utf-8")
            (Path(t) / "case.json").write_text('{"steps": [{"sleep": 0}]}', encoding="utf-8")

            class NoDisplay:
                def __enter__(self):
                    raise RuntimeError("no display and no Xvfb")
                def __exit__(self, *a): pass

            real = (uitest.Display, uitest.find_card_host)
            uitest.Display, uitest.find_card_host = NoDisplay, lambda *a, **k: FAKE_CARD_HOST
            try:
                code = uitest.main(["run", str(bundle), str(Path(t) / "case.json"), "--out", str(Path(t) / "out")])
            finally:
                uitest.Display, uitest.find_card_host = real
            summary = json.loads((Path(t) / "out" / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(code, 2)
            self.assertEqual(summary["status"], "environment_error")
            self.assertIn("finished", summary)

    def test_every_text_file_the_runner_touches_names_its_encoding(self):
        # Windows reads and writes text as cp1252 unless told otherwise, and the
        # results carry the scenarios' own (often Chinese) names.
        import ast
        tree = ast.parse((Path(__file__).resolve().parent / "uitest.py").read_text(encoding="utf-8"))
        unnamed = [n.lineno for n in ast.walk(tree)
                   if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                   and n.func.attr in ("read_text", "write_text")
                   and not any(k.arg == "encoding" for k in n.keywords)]
        self.assertEqual(unnamed, [], "uitest.py lines that read or write text in the platform's encoding")

    def test_results_are_utf8_and_a_narrow_console_does_not_stop_the_run(self):
        import io
        with tempfile.TemporaryDirectory() as t:
            bundle = Path(t) / "bundle"
            bundle.mkdir()
            (bundle / "main.splash").write_text("let x = 1\n", encoding="utf-8")
            (bundle / "manifest.json").write_text(json.dumps({"id": "a", "capabilities": []}), encoding="utf-8")
            scenario = Path(t) / "case.json"
            scenario.write_text(json.dumps({"name": "首屏：载入群聊", "steps": [{"sleep": 0}]}), encoding="utf-8")
            out = Path(t) / "out"

            class Host:
                def __init__(self, *a, **k):
                    Path(a[4]).write_text("", encoding="utf-8")
                    self.line_offset = 0
                def wait_ready(self, timeout): pass
                def new_runtime_errors(self): return []
                def calls(self, final=False): return [{"seq": 1, "service": "a.b", "args": {"text": "你好"}}]
                def peak_rss_mb(self): return None
                def close(self): pass

            class NoDisplay:
                env = {}
                def __enter__(self): return self
                def __exit__(self, *a): pass

            console = io.TextIOWrapper(io.BytesIO(), encoding="cp1252")   # a Windows console's code page
            real = (uitest.App, uitest.Display, uitest.find_card_host, sys.stdout)
            uitest.App, uitest.Display, uitest.find_card_host = Host, NoDisplay, lambda *a, **k: FAKE_CARD_HOST
            sys.stdout = console
            try:
                code = uitest.main(["run", str(bundle), str(scenario), "--out", str(out)])
            finally:
                uitest.App, uitest.Display, uitest.find_card_host, sys.stdout = real
            self.assertEqual(code, 0)
            summary = json.loads((out / "summary.json").read_bytes().decode("utf-8"))
            self.assertEqual(summary["results"][0]["scenario"], "首屏：载入群聊")
            console.flush()
            self.assertIn(b"\\u9996", console.buffer.getvalue())   # shown escaped, not a crash

    def test_an_unreadable_card_host_still_ends_the_summary(self):
        with tempfile.TemporaryDirectory() as t:
            bundle = Path(t) / "bundle"
            bundle.mkdir()
            (bundle / "main.splash").write_text("let x = 1\n", encoding="utf-8")
            (Path(t) / "case.json").write_text('{"steps": [{"sleep": 0}]}', encoding="utf-8")
            real = uitest.find_card_host
            uitest.find_card_host = lambda *a, **k: t      # a directory: hashing it fails
            try:
                code = uitest.main(["run", str(bundle), str(Path(t) / "case.json"), "--out", str(Path(t) / "out")])
            finally:
                uitest.find_card_host = real
            summary = json.loads((Path(t) / "out" / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual((code, summary["status"]), (2, "aborted"))
            self.assertIn("finished", summary)

    def test_card_host_is_found_by_its_windows_name(self):
        with tempfile.TemporaryDirectory() as t:
            exe = Path(t) / "target" / "release" / "card-host.exe"
            exe.parent.mkdir(parents=True)
            exe.write_text("", encoding="utf-8")
            exe.chmod(0o755)
            old_names, old_env = uitest.CARD_HOST_NAMES, dict(uitest.os.environ)
            try:
                uitest.CARD_HOST_NAMES = ("card-host.exe", "card-host")
                uitest.os.environ.update(OCTOSENSE_APP_HUB=t, XDG_CONFIG_HOME=t, PATH=str(Path(t) / "none"))
                uitest.os.environ.pop("OCTO_CARD_HOST", None)
                uitest.os.environ.pop("CARGO_TARGET_DIR", None)
                self.assertEqual(uitest.find_card_host(None), str(exe.resolve()))
            finally:
                uitest.CARD_HOST_NAMES = old_names
                uitest.os.environ.clear()
                uitest.os.environ.update(old_env)

    def test_setup_records_card_host_for_later_shells(self):
        with tempfile.TemporaryDirectory() as t:
            exe = Path(t) / "card-host"
            exe.write_text("#!/bin/sh\n", encoding="utf-8")
            exe.chmod(0o755)
            old = {k: uitest.os.environ.get(k) for k in ("XDG_CONFIG_HOME", "OCTO_CARD_HOST", "OCTOSENSE_APP_HUB",
                                                       "CARGO_TARGET_DIR", "PATH")}
            try:
                uitest.os.environ["XDG_CONFIG_HOME"] = t
                uitest.os.environ["PATH"] = "/nonexistent"
                for k in ("OCTO_CARD_HOST", "OCTOSENSE_APP_HUB", "CARGO_TARGET_DIR"):
                    uitest.os.environ.pop(k, None)
                self.assertEqual(uitest.find_card_host(None), None)
                uitest.config_file().parent.mkdir(parents=True)
                uitest.config_file().write_text(str(exe) + "\n", encoding="utf-8")
                found, source = uitest.find_card_host(None, with_source=True)
                self.assertEqual(found, str(exe.resolve()))
                self.assertIn("setup.sh", source)
            finally:
                for k, v in old.items():
                    if v is None:
                        uitest.os.environ.pop(k, None)
                    else:
                        uitest.os.environ[k] = v
        setup = (Path(__file__).resolve().parent / "setup.sh").read_text(encoding="utf-8")
        self.assertIn("splash-app-verify/card-host", setup)


if __name__ == "__main__":
    unittest.main()
