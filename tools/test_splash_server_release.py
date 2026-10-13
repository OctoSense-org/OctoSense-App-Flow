"""The Splash language server release: naming, the version record, and what is missing.

The seam under test is the recorded release — `tools/splash-server-toolchain.json`
— read through `tools/splash_server_release.py`, which is the one place the
release workflow and the extension's downloader both read. No network, no cargo,
no binary: the record is checked against the naming convention it was published
under, so a hand-edited asset name cannot drift away from what the release
actually holds.
"""
import importlib.machinery
import importlib.util
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
WORKFLOW = HERE.parent / '.github' / 'workflows' / 'release-splash-lsp.yml'
loader = importlib.machinery.SourceFileLoader(
    'splash_server_release', str(HERE / 'splash_server_release.py'))
spec = importlib.util.spec_from_loader(loader.name, loader)
release = importlib.util.module_from_spec(spec)
loader.exec_module(release)


def workflow_targets():
    """The Rust targets the release workflow's matrix builds.

    Read out of the file rather than restated here: the record and the workflow
    are two files that must agree, and a test that restated either would only
    prove the restatement.
    """
    text = WORKFLOW.read_text(encoding='utf-8')
    return set(re.findall(r'^\s*target:\s*(\S+)\s*$', text, re.M))


class Naming(unittest.TestCase):
    def test_an_asset_name_carries_the_version_and_the_target(self):
        self.assertEqual(
            release.asset_name('splash-lsp', '2.0.0', 'x86_64-pc-windows-msvc'),
            'splash-lsp-2.0.0-x86_64-pc-windows-msvc.zip')

    def test_the_tag_is_namespaced_per_server(self):
        self.assertEqual(release.release_tag('splash-lsp', '2.0.0'), 'splash-lsp-v2.0.0')

    def test_the_download_url_points_at_the_recorded_release(self):
        self.assertEqual(
            release.download_url('octo/flow', 'splash-lsp-v2.0.0', 'splash-lsp-2.0.0-x86_64-pc-windows-msvc.zip'),
            'https://github.com/octo/flow/releases/download/'
            'splash-lsp-v2.0.0/splash-lsp-2.0.0-x86_64-pc-windows-msvc.zip')


class RecordedRelease(unittest.TestCase):
    def setUp(self):
        self.pin = release.read_pin()

    def test_the_recorded_version_is_a_release_triple(self):
        self.assertRegex(self.pin['server']['version'], r'^\d+\.\d+\.\d+$')

    def test_the_source_is_a_pinned_commit_rather_than_a_branch(self):
        self.assertRegex(self.pin['server']['source']['revision'], r'^[0-9a-f]{40}$')

    def test_the_tag_is_derived_from_the_server_and_its_version(self):
        self.assertEqual(
            self.pin['server']['release']['tag'],
            release.release_tag(self.pin['server']['name'], self.pin['server']['version']))

    def test_every_published_asset_follows_the_naming_convention(self):
        for platform in release.published(self.pin):
            self.assertEqual(
                platform['asset'],
                release.asset_name(self.pin['server']['name'],
                                   self.pin['server']['version'], platform['target']))

    def test_a_published_platform_resolves_to_the_url_it_was_published_at(self):
        for platform in release.published(self.pin):
            self.assertEqual(
                release.download(self.pin, platform['platform']),
                release.download_url(self.pin['server']['release']['repository'],
                                     self.pin['server']['release']['tag'], platform['asset']))

    def test_a_platform_nothing_was_published_for_has_no_url(self):
        for platform in release.unpublished(self.pin):
            self.assertIsNone(release.download(self.pin, platform['platform']))
            self.assertNotIn('asset', platform)

    def test_every_published_platform_names_a_real_rust_target(self):
        for platform in release.published(self.pin):
            self.assertRegex(platform['target'],
                             r'^[a-z0-9_.]+(?:-[a-z0-9_]+){2,3}$')

    def test_the_first_platform_binary_is_published(self):
        self.assertTrue(release.published(self.pin), 'the release holds no asset at all')

    def test_every_platform_the_extension_runs_on_is_declared(self):
        self.assertEqual(
            {platform['platform'] for platform in self.pin['platforms']},
            {'win32', 'darwin', 'linux'})

    def test_the_sibling_the_build_needs_is_pinned_by_this_repository(self):
        # makepad patches octoscript-node to a path outside its own tree, so a
        # build with no sibling beside it does not build at all.
        locked = release.runtime_lock(self.pin)
        self.assertEqual(locked['repository'], 'OctoSense-org/Octoscript-Makepad')
        self.assertRegex(locked['revision'], r'^[0-9a-f]{40}$')
        self.assertEqual(self.pin['runtime']['sibling'], 'octoscript-makepad')

    def test_the_workflow_builds_exactly_the_platforms_the_record_publishes(self):
        # Both directions matter. A platform the record publishes but nothing
        # builds is a download URL that 404s; a platform the workflow builds but
        # the record does not name is an asset nobody can pin.
        self.assertEqual(workflow_targets(),
                         {platform['target'] for platform in release.published(self.pin)})


class RecordedReleaseAsACLI(unittest.TestCase):
    def build_plan(self, *args):
        return subprocess.run([sys.executable, str(HERE / 'splash_server_release.py'), *args],
                              capture_output=True, text=True)

    def test_printing_the_record_shows_the_url_a_downloader_uses(self):
        printed = json.loads(self.build_plan().stdout)
        pin = release.read_pin()
        self.assertEqual(printed['tag'], pin['server']['release']['tag'])
        self.assertEqual(printed['assets'],
                         [release.download(pin, platform['platform'])
                          for platform in release.published(pin)])

    def test_a_build_plan_names_the_asset_and_the_source_to_build_it_from(self):
        plan = dict(line.split('=', 1) for line in
                    self.build_plan('--build-plan', 'x86_64-pc-windows-msvc').stdout.splitlines())
        pin = release.read_pin()
        locked = release.runtime_lock(pin)
        self.assertEqual(plan['asset'],
                         release.asset_name(pin['server']['name'], pin['server']['version'],
                                            'x86_64-pc-windows-msvc'))
        self.assertEqual(plan['source-revision'], pin['server']['source']['revision'])
        self.assertEqual(plan['source-features'], 'maps')
        self.assertEqual(plan['runtime-revision'], locked['revision'])
        self.assertEqual(plan['runtime-sibling'], 'octoscript-makepad')

    def test_a_build_plan_refuses_a_target_nothing_was_published_for(self):
        done = self.build_plan('--build-plan', 'aarch64-apple-darwin')
        self.assertEqual(done.returncode, 1)
        self.assertIn('no published asset', done.stderr)


class ReleaseNotes(unittest.TestCase):
    """The release page the publish job writes, which is where a digest belongs."""

    def setUp(self):
        self.pin = release.read_pin()
        self.assets = Path(tempfile.mkdtemp()) / 'assets'
        self.assets.mkdir()
        for entry in release.published(self.pin):
            (self.assets / entry['asset']).write_bytes(b'a stand-in for the built binary')

    def notes(self):
        return release.release_notes(self.pin, self.assets)

    def test_the_notes_name_the_uploaded_asset_and_its_digest(self):
        # The digest has to be computed from the bytes, not asserted equal to a
        # constant, or the note would describe a build that never happened.
        expected = hashlib.sha256(b'a stand-in for the built binary').hexdigest()
        notes = self.notes()
        for entry in release.published(self.pin):
            self.assertIn(entry['asset'], notes)
            self.assertIn(expected, notes)

    def test_the_notes_name_the_revision_the_binary_was_built_from(self):
        revision = self.pin['server']['source']['revision']
        self.assertIn(revision[:12], self.notes())
        self.assertIn(revision, self.notes())

    def test_the_notes_say_which_platforms_have_no_asset(self):
        notes = self.notes()
        for entry in release.unpublished(self.pin):
            self.assertIn(entry['platform'], notes)
        self.assertIn('no asset yet', notes)

    def test_a_missing_uploaded_asset_is_an_error_not_a_quiet_gap(self):
        for entry in release.published(self.pin):
            (self.assets / entry['asset']).unlink()
        with self.assertRaises(FileNotFoundError):
            self.notes()
