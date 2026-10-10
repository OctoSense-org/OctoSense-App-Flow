"""Onboarding regressions; no model, native window or external credentials."""
import argparse
import contextlib
import importlib.machinery
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
loader = importlib.machinery.SourceFileLoader('octo_cli', str(HERE / 'octo'))
spec = importlib.util.spec_from_loader(loader.name, loader)
octo = importlib.util.module_from_spec(spec)
loader.exec_module(octo)


class Onboarding(unittest.TestCase):
    def create(self, dest, app_id='com.example.quicknotes', platforms=('macos',), system=False):
        args = argparse.Namespace(dir=str(dest), id=app_id, name='Test Notes', platform=platforms, system=system)
        with patch.object(octo, 'find_binary', return_value=(None, None, [])), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return octo.cmd_new(args)

    def test_platform_must_be_explicit_and_known(self):
        for args in (['new', '/unused'], ['new', '/unused', '--platform', 'madeup']):
            with patch('sys.argv', ['octo'] + args), contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
                octo.main()
            self.assertEqual(error.exception.code, 2)

    def test_platforms_replace_template_and_deduplicate(self):
        with tempfile.TemporaryDirectory() as temp:
            dest = Path(temp) / 'new-app'
            self.create(dest, platforms=('windows', 'linux', 'windows'))
            listing = json.loads((dest / 'bundle/listing.json').read_text())
            self.assertEqual(listing['platforms'], ['windows', 'linux'])
            self.assertNotIn('android', listing['platforms'])
            self.assertEqual((dest/'.gitattributes').read_text(),'bundle/** -text\n')
            self.assertEqual(json.loads((dest / 'bundle/manifest.json').read_text())['id'], 'com.example.quicknotes')

    def test_check_exposes_and_forwards_catalog_and_publisher_keys(self):
        with tempfile.TemporaryDirectory() as temp:
            bundle=Path(temp)
            hub=bundle/'fixture-tools'/'hub'
            (bundle/'manifest.json').write_text(json.dumps({'integrity':{'signature':'signed fixture'}}))
            argv=['octo','check',str(bundle),'--catalog','catalog.json','--publisher-key','one=key','--publisher-key','two=key','--offline']
            with patch('sys.argv',argv), patch.object(octo,'need',return_value=hub), patch.object(octo.subprocess,'run') as run, contextlib.redirect_stdout(io.StringIO()), self.assertRaises(SystemExit) as done:
                run.return_value.returncode=0
                octo.main()
            self.assertEqual(done.exception.code,0)
            self.assertEqual(run.call_args.args[0],[str(hub),'check',str(bundle.resolve()),'--catalog','catalog.json','--publisher-key','one=key','--publisher-key','two=key','--offline'])

    def test_check_says_how_to_capture_a_screenshot_the_listing_names(self):
        with tempfile.TemporaryDirectory() as temp:
            bundle=Path(temp)
            hub=bundle/'fixture-tools'/'hub'
            (bundle/'manifest.json').write_text(json.dumps({'integrity':{'signature':'signed fixture'}}))
            refusal=('dev.example.texttools 0.1.0 — REFUSED\n'
                     '  [refused] listing: screenshots/01-main.png is named by the listing but is not in the bundle\n'
                     'hub: the bundle was refused\n')
            out=io.StringIO()
            with patch('sys.argv',['octo','check',str(bundle)]), patch.object(octo,'need',return_value=hub), patch.object(octo.subprocess,'run') as run, contextlib.redirect_stdout(out), self.assertRaises(SystemExit) as done:
                run.return_value.returncode=1
                run.return_value.stdout=refusal
                run.return_value.stderr=''
                octo.main()
            self.assertEqual(done.exception.code,1)
            text=out.getvalue()
            self.assertIn(refusal,text)
            self.assertIn('octo: hint: capture the screenshots the listing names',text)
            self.assertIn(f"tools/octo shot 8141 {bundle.resolve()/'screenshots'/'01-main.png'}",text)
            # A refusal for another reason gets no screenshot hint.
            out=io.StringIO()
            with patch('sys.argv',['octo','check',str(bundle)]), patch.object(octo,'need',return_value=hub), patch.object(octo.subprocess,'run') as run, contextlib.redirect_stdout(out), self.assertRaises(SystemExit):
                run.return_value.returncode=1
                run.return_value.stdout='  [refused] contents-invalid (fns/x.wasm): not a WebAssembly core module\n'
                run.return_value.stderr=''
                octo.main()
            self.assertNotIn('octo: hint:',out.getvalue())

    def test_wasm_call_runs_octosenses_example_on_the_built_component(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            app=root/'app'
            (app/'bundle'/'fns').mkdir(parents=True)
            wasm=app/'bundle'/'fns'/'text-tools.wasm'
            wasm.write_bytes(b'\0asm\x0d\0\x01\0')
            repo=root/'OctoSense'
            (repo/'crates'/'wasm-host'/'examples').mkdir(parents=True)
            (repo/'.sources').mkdir()
            argv=['octo','wasm','call','wasm.count','{"text":"a b"}','--app',str(app)]
            # Without OctoSense #455's example, it says what it needs.
            with patch.dict('os.environ',{'OCTOSENSE_REPO':str(repo)}), patch('sys.argv',argv), patch.object(octo.subprocess,'run') as run, contextlib.redirect_stderr(io.StringIO()) as err, self.assertRaises(SystemExit) as done:
                octo.main()
            self.assertEqual(done.exception.code,1)
            self.assertIn('OctoSense #455',err.getvalue())
            run.assert_not_called()
            (repo/'crates'/'wasm-host'/'examples'/'wasm_call.rs').write_text('fn main() {}\n')
            with patch.dict('os.environ',{'OCTOSENSE_REPO':str(repo)}), patch('sys.argv',argv), patch.object(octo.subprocess,'run') as run, contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as done:
                run.return_value.returncode=0
                octo.main()
            self.assertEqual(done.exception.code,0)
            self.assertEqual(run.call_args.args[0],['cargo','run','-q','-p','octosense-wasm-host','--example','wasm_call','--',str(wasm.resolve()),'count','{"text":"a b"}'])
            self.assertEqual(run.call_args.kwargs['cwd'],str(repo.resolve()))
            # Two function files: name one.
            (app/'bundle'/'fns'/'other.wasm').write_bytes(b'\0asm\x0d\0\x01\0')
            with patch.dict('os.environ',{'OCTOSENSE_REPO':str(repo)}), patch('sys.argv',argv), patch.object(octo.subprocess,'run') as run, contextlib.redirect_stderr(io.StringIO()) as err, self.assertRaises(SystemExit) as done:
                octo.main()
            self.assertEqual(done.exception.code,1)
            self.assertIn('--file',err.getvalue())
            run.assert_not_called()

    def test_reserved_ids_and_namespaces_leave_no_partial_project(self):
        names = ('agents apphub appcard browser calculator card clock dev notes octos octoscode os '
                 'reference reminders rinx sheets shell system task terminal toolbox weather workflow').split()
        with tempfile.TemporaryDirectory() as temp:
            for name in names:
                for app_id in (name, 'com.example.' + name):
                    for system in (False, True):
                        dest = Path(temp) / app_id
                        with self.subTest(app_id=app_id, system=system), self.assertRaises(SystemExit):
                            self.create(dest, app_id, system=system)
                        self.assertFalse(dest.exists())

    def test_system_prefix_needs_explicit_escape(self):
        with tempfile.TemporaryDirectory() as temp:
            dest = Path(temp) / 'new-app'
            with self.assertRaises(SystemExit): self.create(dest, 'os.example')
            self.assertFalse(dest.exists())
            self.create(dest, 'os.example', system=True)
            self.assertTrue((dest / 'bundle/main.splash').is_file())

    def test_windows_executables_found_in_candidate_directory_before_path(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            for name in ('hub', 'card-host'):
                exe = target / (name + '.exe')
                exe.touch(); exe.chmod(0o700)
                with patch.dict(os.environ, {}, clear=True), patch.object(octo.sys, 'platform', 'win32'), patch.object(octo, 'candidate_dirs', return_value=[target]), patch.object(octo, 'is_octosense_hub', return_value=True), patch.object(octo.shutil, 'which') as which:
                    found, where, searched = octo.find_binary(name, 'OCTO_' + name)
                    self.assertEqual(found, exe)
                    self.assertEqual(where, str(target))
                    which.assert_not_called()

    def test_windows_rejects_wrong_hub_before_path_fallback(self):
        with tempfile.TemporaryDirectory() as temp:
            exe = Path(temp) / 'hub.exe'; exe.touch(); exe.chmod(0o700)
            fallback = Path(temp) / 'known' / 'hub.exe'
            with patch.dict(os.environ, {}, clear=True), patch.object(octo.sys, 'platform', 'win32'), patch.object(octo, 'candidate_dirs', return_value=[Path(temp)]), patch.object(octo, 'is_octosense_hub', side_effect=lambda p: Path(p) == fallback), patch.object(octo.shutil, 'which', return_value=str(fallback)):
                found, where, searched = octo.find_binary('hub', 'OCTO_HUB')
                self.assertEqual(found, fallback)
                self.assertEqual(where, 'PATH')

    def test_reserved_names_match_available_hub_contract(self):
        repo = octo.hub_repo()
        if repo is None: self.skipTest('Set OCTOSENSE_APP_HUB to check contract parity')
        source = repo / 'crates/app-contract/src/manifest.rs'
        if not source.is_file(): self.skipTest('Hub contract source unavailable')
        declaration = re.search(r'pub const RESERVED_NAMES:.*?= &\[(.*?)\];', source.read_text(), re.S).group(1)
        self.assertEqual(octo.RESERVED_NAMES, set(re.findall(r'"([a-z]+)"', declaration)))


# ---------------------------------------------------------------------- wasm
wasm_component = octo.wasm_component
SDK_WASM = [HERE.parent / 'sdk/rust/target' / d / 'wasm32-wasip2/release' for d in ('e2e-wasm', '.')]


def leb(n):
    out = bytearray()
    while True:
        byte, n = n & 0x7f, n >> 7
        out.append(byte | (0x80 if n else 0))
        if not n:
            return bytes(out)


def text(value):
    raw = value.encode()
    return leb(len(raw)) + raw


def section(sid, *entries):
    body = leb(len(entries)) + b''.join(entries)
    return bytes([sid]) + leb(len(body)) + body


def component(*imports):
    """A component's skeleton, laid out the way wit-component lays one out
    (it is not valid: no core code backs its functions). It imports each
    interface as an instance, and a record type as `(type (eq …))`, which
    reaches nothing; it exports `count-words: func(text: string) -> stats`
    and `ping: func()`, the latter with an ascribed type."""
    instance, record = b'\x42\x00', b'\x72\x01' + text('words') + b'\x79'
    count_words = b'\x40\x01' + text('text') + b'\x73' + b'\x00\x02'   # -> type 2, the import of type 1
    ping = b'\x40\x00\x01\x00'
    return (wasm_component.COMPONENT_PREAMBLE
            + section(7, instance, record)
            + section(10, *[b'\x00' + text(name) + b'\x05\x00' for name in imports], b'\x00' + text('stats') + b'\x03\x00\x01')
            + section(7, count_words, ping)
            + section(8, b'\x00\x00\x00\x00\x03', b'\x00\x00\x01\x00\x04')     # lift: functions 0 and 1
            + section(11, b'\x00' + text('count-words') + b'\x01\x00\x00')
            + section(11, b'\x00' + text('ping') + b'\x01\x01\x01\x01\x04'))


# (module (import "octo" "log" (func (param i32 i32)))
#   (func (export "add") (param i32 i32) (result i32) local.get 0 local.get 1 i32.add))
CORE_MODULE = (b'\0asm\x01\0\0\0\x01\x0c\x02\x60\x02\x7f\x7f\x01\x7f\x60\x02\x7f\x7f\x00'
               b'\x02\x0c\x01\x04octo\x03log\x00\x01\x03\x02\x01\x00\x07\x07\x01\x03add\x00\x01'
               b'\x0a\x09\x01\x07\x00\x20\x00\x20\x01\x6a\x0b')

ENV, FILES, TCP = 'wasi:cli/environment@0.2.9', 'wasi:filesystem/types@0.2.9', 'wasi:sockets/tcp@0.2.9'
CLOCK, RANDOM = 'wasi:clocks/wall-clock@0.2.9', 'wasi:random/random@0.2.9'
HTTP, HTTP_TYPES = 'wasi:http/outgoing-handler@0.2.9', 'wasi:http/types@0.2.9'
HOST_SERVICES = 'octosense:host/services@0.1.0'
CRATES_IO_INDEX = 'registry+https://github.com/rust-lang/crates.io-index'


def custom(name, payload):
    """A custom section: id 0, its size, then its name and payload."""
    body = text(name) + payload
    return b'\x00' + leb(len(body)) + body


def release_step_script():
    """The Python of the release workflow's step that builds components/."""
    text = (HERE / 'publish-app.template.yml').read_text()
    block = text[text.index("      - name: Build the app's Rust components"):]
    body = block[block.index("python3 - <<'PY'\n") + len("python3 - <<'PY'\n"):block.index('\n          PY\n')]
    return '\n'.join(line[10:] if line.startswith(' ' * 10) else line for line in body.splitlines()) + '\n'


def release_step():
    """The step's functions (crates, with_crates, …), defined without running it."""
    functions = {'__name__': 'release_step'}
    exec(compile(release_step_script(), 'publish-app.template.yml', 'exec'), functions)
    return functions


def anchor(heading):
    """GitHub's anchor for a Markdown heading."""
    return re.sub(r'[^\w\- ]', '', heading.strip().lower()).replace(' ', '-')


def toolchain():
    """cargo, when it and the wasm32-wasip2 target are installed."""
    cargo = octo.cargo_path()
    found = octo.rust_toolchain(cargo) if cargo else None
    return cargo if found and found['target'] and (found['release'] or (0, 0)) >= octo.MIN_RUST else None


def git(repo, *args):
    subprocess.run(['git', '-C', str(repo), '-c', 'user.name=Test', '-c', 'user.email=test@example.com',
                    '-c', 'commit.gpgsign=false', *args], check=True, capture_output=True)


class WasmReader(unittest.TestCase):
    def test_a_component_s_imports_and_typed_exports(self):
        info = wasm_component.describe(component(ENV, TCP))
        self.assertEqual(info, {
            'kind': 'component',
            'imports': [ENV, TCP],
            'exports': [
                {'name': 'count-words', 'params': [['text', 'string']], 'result': 'record { words: u32 }'},
                {'name': 'ping', 'params': [], 'result': None},
            ],
        })
        self.assertEqual(wasm_component.refused_imports(info['imports']), [TCP])
        # A package name is matched whole, as App Hub's gate matches it.
        self.assertEqual(wasm_component.refused_imports(['wasi:clocksmith/x', 'my:pkg/host']), ['wasi:clocksmith/x', 'my:pkg/host'])

    def test_phase_3_admits_http_and_host_services_and_nothing_else(self):
        imports = ['wasi:io/poll@0.2.9', 'wasi:sockets/network@0.2.9', HTTP_TYPES, 'my:pkg/host',
                   HOST_SERVICES, 'octosense:hostile/x']
        self.assertEqual(wasm_component.refused_imports(imports),
                         ['wasi:sockets/network@0.2.9', 'my:pkg/host', 'octosense:hostile/x'])
        self.assertTrue(wasm_component.uses_http(imports))
        self.assertTrue(wasm_component.uses_host_services(imports))
        self.assertFalse(wasm_component.uses_http([ENV, FILES, 'wasi:httpx/x']))
        self.assertFalse(wasm_component.uses_host_services([ENV, 'octosense:hostile/x']))

    def test_the_reach_line_is_app_hub_s(self):
        # App Hub's `ComponentInfo::reach` tests, word for word.
        reach = wasm_component.reach
        self.assertEqual(reach([ENV]), 'nothing but its input')
        self.assertEqual(reach([CLOCK, RANDOM]), 'the clock and random numbers, but no files, network or other app')
        self.assertEqual(reach([FILES]), 'files in its app folder, but no network or other app')
        self.assertEqual(reach([CLOCK, FILES]), 'the clock and files in its app folder, but no network or other app')
        self.assertEqual(reach([HTTP, CLOCK]), 'the clock and the network, but no files or other app')
        self.assertEqual(reach([HTTP, FILES]), 'files in its app folder and the network, but no other app')
        self.assertEqual(reach([HOST_SERVICES]), "its app's host services, but no files, network or other app")
        self.assertEqual(reach([CLOCK, HOST_SERVICES]), "the clock and its app's host services, but no files, network or other app")
        self.assertEqual(reach([CLOCK, RANDOM, FILES, HTTP, HOST_SERVICES]),
                         "the clock, random numbers, files in its app folder, the network and "
                         "its app's host services, but no other app")
        # Any wasi:http interface is the network, even types alone.
        self.assertEqual(reach([HTTP_TYPES]), 'the network, but no files or other app')

    def test_a_core_module_s_imports_and_exports(self):
        self.assertEqual(wasm_component.describe(CORE_MODULE), {
            'kind': 'module',
            'imports': ['octo.log'],
            'exports': [{'name': 'add', 'params': [['p0', 'i32'], ['p1', 'i32']], 'result': 'i32'}],
        })

    def test_anything_else_is_refused_by_name(self):
        for data in (b'#!/bin/sh\n', component(ENV)[:-3], wasm_component.COMPONENT_PREAMBLE + b'\x0a\x05\x01\x07'):
            with self.subTest(data=data[:12]), self.assertRaises(wasm_component.ReadError):
                wasm_component.describe(data)

    def test_built_components_read_as_hub_component_info_reads_them(self):
        # The SDK's examples, once `cargo test` in sdk/rust has built them.
        found = [d / 'markdown_tools.wasm' for d in SDK_WASM if (d / 'markdown_tools.wasm').is_file()]
        if not found: self.skipTest('build sdk/rust first: cargo test --locked --workspace')
        info = wasm_component.describe(found[0].read_bytes())
        self.assertEqual([(e['name'], e['params'], e['result']) for e in info['exports']], [
            ('analyze', [['markdown', 'string']], 'record { words: u32, lines: u32, headings: list<string> }'),
            ('measure', [['markdown', 'string']], 'enum { short, medium, long }'),
            ('now-ms', [], 'u64'),
            ('save-html', [['markdown', 'string'], ['path', 'string']], 'result<u64, string>'),
            ('to-html', [['markdown', 'string']], 'string'),
        ])
        self.assertTrue(wasm_component.uses_files(info['imports']))
        self.assertEqual(wasm_component.refused_imports(info['imports']), [])

    def test_built_phase_3_examples_import_only_what_they_call(self):
        found = {name: [d / name for d in SDK_WASM if (d / name).is_file()]
                 for name in ('http_client.wasm', 'host_services.wasm')}
        if not all(found.values()): self.skipTest('build sdk/rust first: cargo test --locked --workspace')
        client = wasm_component.describe(found['http_client.wasm'][0].read_bytes())
        services = wasm_component.describe(found['host_services.wasm'][0].read_bytes())
        for info in (client, services):
            self.assertEqual(wasm_component.refused_imports(info['imports']), [])
        self.assertTrue(wasm_component.uses_http(client['imports']))
        self.assertFalse(wasm_component.uses_host_services(client['imports']))
        self.assertIn(HOST_SERVICES, services['imports'])
        self.assertFalse(wasm_component.uses_http(services['imports']))
        self.assertEqual(wasm_component.reach(client['imports']),
                         'the clock and the network, but no files or other app')
        self.assertEqual(wasm_component.reach(services['imports']),
                         "the clock and its app's host services, but no files, network or other app")
        self.assertEqual([(e['name'], e['params'], e['result']) for e in services['exports']], [
            ('call', [['service', 'string'], ['args', 'string']], 'result<string, string>'),
            ('host-apis', [], 'result<string, string>'),
        ])


class WasmCommands(unittest.TestCase):
    def app(self, temp, capabilities=('storage',), hosts=None):
        app = Path(temp) / 'texttools'
        Onboarding.create(self, app, 'dev.example.texttools')
        manifest = app / 'bundle/manifest.json'
        fields = dict(json.loads(manifest.read_text()), capabilities=list(capabilities))
        if hosts is not None:
            fields['network'] = {'hosts': list(hosts)}
        manifest.write_text(json.dumps(fields, indent=2) + '\n')
        return app

    def octo(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with patch('sys.argv', ['octo', *argv]), patch.object(octo, 'find_binary', return_value=(None, None, [])), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err), self.assertRaises(SystemExit) as done:
            octo.main()
        return done.exception.code, out.getvalue(), err.getvalue()

    BINDGEN = {'name': 'wit-bindgen', 'version': '0.62.0', 'source': 'crates.io', 'checksum': 'b1' * 32}

    def fake_cargo(self, crate, wasm, name='text-tools'):
        """subprocess.run as cargo answers for a crate whose build makes `wasm`
        and whose one dependency is wit-bindgen, from crates.io."""
        package = {'name': name, 'version': '0.1.0', 'id': f'path+file://{crate}#0.1.0', 'source': None,
                   'manifest_path': str(crate / 'Cargo.toml'), 'targets': [{'kind': ['cdylib', 'rlib']}]}
        bindgen = {'name': 'wit-bindgen', 'version': '0.62.0', 'id': f'{CRATES_IO_INDEX}#wit-bindgen@0.62.0',
                   'source': CRATES_IO_INDEX, 'manifest_path': '/registry/wit-bindgen/Cargo.toml',
                   'targets': [{'kind': ['lib']}]}
        normal = [{'kind': None, 'target': None}]
        metadata = {'packages': [package, bindgen], 'workspace_root': str(crate), 'resolve': {'root': package['id'], 'nodes': [
            {'id': package['id'], 'deps': [{'name': 'wit_bindgen', 'pkg': bindgen['id'], 'dep_kinds': normal}]},
            {'id': bindgen['id'], 'deps': []}]}}

        def run(cmd, **kwargs):
            if 'metadata' in cmd:
                return subprocess.CompletedProcess(cmd, 0, stdout=json.dumps(metadata), stderr='')
            if 'build' in cmd:
                artifact = {'reason': 'compiler-artifact', 'package_id': package['id'], 'filenames': [str(wasm)]}
                return subprocess.CompletedProcess(cmd, 0, stdout='\n'.join([json.dumps(artifact), '{"reason":"build-finished","success":true}']))
            raise AssertionError(cmd)
        return run

    def build(self, app, data):
        crate = app / 'components/text-tools'
        (crate / 'src').mkdir(parents=True)
        (crate / 'Cargo.toml').write_text('[package]\nname = "text-tools"\n')
        (crate / 'Cargo.lock').write_text('version = 4\n\n[[package]]\nname = "wit-bindgen"\nversion = "0.62.0"\n'
                                          f'source = "{CRATES_IO_INDEX}"\nchecksum = "{"b1" * 32}"\n')
        wasm = Path(app) / 'built.wasm'
        wasm.write_bytes(data)
        with patch.object(octo, 'cargo_path', return_value='cargo'), \
                patch.object(octo, 'rust_toolchain', return_value={'version': 'rustc 1.97.1', 'release': (1, 97), 'target': True}), \
                patch.object(octo.subprocess, 'run', side_effect=self.fake_cargo(crate, wasm)):
            return self.octo('wasm', 'build', '--app', str(app))

    def test_new_writes_the_template_with_the_sdk_by_path_or_commit(self):
        with tempfile.TemporaryDirectory() as temp:
            app = self.app(temp)
            code, out, _ = self.octo('wasm', 'new', 'text-tools', '--app', str(app), '--sdk', 'path')
            self.assertEqual(code, 0, out)
            crate = app / 'components/text-tools'
            cargo = (crate / 'Cargo.toml').read_text()
            self.assertIn('name = "text-tools"', cargo)
            self.assertIn('crate-type = ["cdylib", "rlib"]', cargo)
            self.assertIn('because you chose --sdk path', cargo)
            path = re.search(r'^octosense-component = \{ path = "(.+)" \}$', cargo, re.M).group(1)
            self.assertEqual((crate / path).resolve(), (HERE.parent / 'sdk/rust/octosense-component').resolve())
            self.assertEqual((crate / 'src/lib.rs').read_text(), (HERE.parent / 'templates/rust-component/src/lib.rs').read_text())
            self.assertEqual((crate / '.gitignore').read_text(), '/target/\n')
            # Pinned to a commit on App Flow's main when there is one.
            with patch.object(octo, 'sdk_revision', return_value=('a' * 40, None)):
                code, out, _ = self.octo('wasm', 'new', 'other', '--app', str(app))
            self.assertEqual(code, 0, out)
            self.assertIn('octosense-component = { git = "https://github.com/OctoSense-org/OctoSense-App-Flow", rev = "' + 'a' * 40 + '" }',
                          (app / 'components/other/Cargo.toml').read_text())
            with patch.object(octo, 'sdk_revision', return_value=(None, 'no reason')):
                code, _, err = self.octo('wasm', 'new', 'third', '--app', str(app), '--sdk', 'git')
            self.assertEqual(code, 1)
            self.assertIn('no App Flow commit to pin the SDK to: no reason', err)
            self.assertFalse((app / 'components/third').exists())

    def test_new_refuses_names_that_cannot_be_a_crate_and_a_file(self):
        with tempfile.TemporaryDirectory() as temp:
            app = self.app(temp)
            (app / 'bundle/fns').mkdir()
            (app / 'bundle/fns/taken.wasm').write_bytes(CORE_MODULE)
            for name in ('Text', '2d', 'fn', 'test', 'a' * 65, 'my.tools', 'taken'):
                with self.subTest(name=name):
                    code, _, err = self.octo('wasm', 'new', name, '--app', str(app), '--sdk', 'path')
                    self.assertEqual(code, 1, err)
                    self.assertFalse((app / 'components' / name).exists())
            self.assertEqual(self.octo('wasm', 'new', 'x', '--app', temp)[0], 1)  # no bundle/ there

    def test_sdk_commit_is_on_app_flow_s_main_and_has_the_sdk(self):
        if not shutil.which('git'): self.skipTest('needs git')
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp)
            git(repo, 'init', '-q')
            git(repo, 'remote', 'add', 'origin', 'https://github.com/OctoSense-org/OctoScript-App-Design-Flow.git')
            (repo / 'README.md').write_text('App Flow\n')
            git(repo, 'add', '.')
            git(repo, 'commit', '-qm', 'before the SDK')
            git(repo, 'update-ref', 'refs/remotes/origin/main', 'HEAD')
            with patch.object(octo, 'REPO', repo):
                rev, why = octo.sdk_revision()
                self.assertIsNone(rev)
                self.assertIn('does not have the SDK yet', why)
                (repo / 'sdk/rust/octosense-component').mkdir(parents=True)
                (repo / 'sdk/rust/octosense-component/Cargo.toml').write_text('[package]\n')
                git(repo, 'add', '.')
                git(repo, 'commit', '-qm', 'the SDK')
                git(repo, 'update-ref', 'refs/remotes/origin/main', 'HEAD')
                main = subprocess.run(['git', '-C', str(repo), 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip()
                git(repo, 'commit', '-q', '--allow-empty', '-m', 'local work, not on main')
                self.assertEqual(octo.sdk_revision(), (main, None))
                git(repo, 'remote', 'set-url', 'origin', 'https://github.com/someone/fork.git')
                self.assertIsNone(octo.sdk_revision()[0])

    def test_build_copies_the_component_and_declares_what_it_needs(self):
        with tempfile.TemporaryDirectory() as temp:
            app = self.app(temp, capabilities=())
            code, out, err = self.build(app, component(ENV, FILES))
            self.assertEqual(code, 0, out + err)
            # The component as cargo built it, with the crates it is built from.
            crates = {'schema': 1, 'crates': [self.BINDGEN]}
            self.assertEqual((app / 'bundle/fns/text-tools.wasm').read_bytes(),
                             wasm_component.with_crates(component(ENV, FILES), crates))
            self.assertIn('  built from 1 crate (tools/octo wasm info lists them)', out)
            manifest = json.loads((app / 'bundle/manifest.json').read_text())
            self.assertEqual(manifest['capabilities'], ['wasm', 'storage'])
            self.assertEqual(manifest['requires'], ['wasm-components-v1'])
            self.assertIn('wasm.count_words(text: string) -> record { words: u32 }', out)
            self.assertIn('imports wasi:filesystem', out)
            # Building again changes nothing.
            code, out, _ = self.build_again(app, component(ENV, FILES))
            self.assertEqual(code, 0)
            self.assertIn('unchanged bundle/fns/text-tools.wasm', out)
            self.assertNotIn('bundle/manifest.json:', out)

    def build_again(self, app, data):
        crate = app / 'components/text-tools'
        wasm = Path(app) / 'built.wasm'
        wasm.write_bytes(data)
        with patch.object(octo, 'cargo_path', return_value='cargo'), \
                patch.object(octo, 'rust_toolchain', return_value={'version': 'rustc 1.97.1', 'release': (1, 97), 'target': True}), \
                patch.object(octo.subprocess, 'run', side_effect=self.fake_cargo(crate, wasm)):
            return self.octo('wasm', 'build', '--app', str(app))

    def test_build_refuses_imports_no_host_gives_and_leaves_the_bundle_alone(self):
        with tempfile.TemporaryDirectory() as temp:
            app = self.app(temp)
            before = (app / 'bundle/manifest.json').read_text()
            code, _, err = self.build(app, component(ENV, TCP))
            self.assertEqual(code, 1)
            self.assertIn(TCP, err)
            self.assertIn('a component has none. It reaches the network over HTTP through wasi:http, '
                          'with octosense_component::http, once the manifest has `net`.', err)
            self.assertNotIn('network.hosts', err)
            self.assertFalse((app / 'bundle/fns').exists())
            self.assertEqual((app / 'bundle/manifest.json').read_text(), before)
        with tempfile.TemporaryDirectory() as temp:
            app = self.app(temp)
            code, _, err = self.build(app, component(ENV, 'octosense:hostile/x'))
            self.assertEqual(code, 1)
            self.assertIn('octosense:hostile/x:\n    not an interface any host gives a component', err)

    def test_build_adds_net_for_http_and_never_a_host(self):
        # network.hosts is a declaration shown at install, not a limit
        # (OctoSense's ruling of 8 October 2026): a component that imports
        # wasi:http needs `net`, hosts listed or not, and octo neither adds a
        # host nor asks for one.
        for capabilities, hosts in (((), None), ((), ['api.example.com']), (('net',), None)):
            with self.subTest(capabilities=capabilities, hosts=hosts), tempfile.TemporaryDirectory() as temp:
                app = self.app(temp, capabilities=capabilities, hosts=hosts)
                code, out, err = self.build(app, component(CLOCK, HTTP, HTTP_TYPES))
                self.assertEqual(code, 0, out + err)
                manifest = json.loads((app / 'bundle/manifest.json').read_text())
                self.assertEqual(manifest['capabilities'], ['net', 'wasm'] if capabilities else ['wasm', 'net'])
                self.assertEqual(manifest.get('network'), None if hosts is None else {'hosts': hosts})
                self.assertIn('a component that reaches the clock and the network, but no files or other app', out)
                added = 'added "net" to capabilities: text-tools imports wasi:http, the network'
                (self.assertNotIn if capabilities else self.assertIn)(added, out)
                self.assertNotIn('warning', out + err)
                self.assertNotIn('network.hosts', out + err)

    def test_build_takes_host_services_with_no_grant_of_their_own(self):
        with tempfile.TemporaryDirectory() as temp:
            app = self.app(temp, capabilities=())
            code, out, err = self.build(app, component(CLOCK, HOST_SERVICES))
            self.assertEqual(code, 0, out + err)
            manifest = json.loads((app / 'bundle/manifest.json').read_text())
            self.assertEqual((manifest['capabilities'], manifest['requires']), (['wasm'], ['wasm-components-v1']))
            self.assertIn("a component that reaches the clock and its app's host services, but no files, network or other app", out)

    def test_build_refuses_a_core_module(self):
        with tempfile.TemporaryDirectory() as temp:
            app = self.app(temp)
            code, _, err = self.build(app, CORE_MODULE)
            self.assertEqual(code, 1)
            self.assertIn('is not a WebAssembly component', err)

    def test_doctor_names_dependencies_that_do_not_build_or_run(self):
        crate = Path('/apps/texttools/components/text-tools')
        package = lambda id, name, **extra: dict({'id': id, 'name': name, 'version': '1.0.0', 'dependencies': []}, **extra)
        build_cc = [{'name': 'cc', 'pkg': 'cc', 'dep_kinds': [{'kind': 'build', 'target': None}]}]
        uses = lambda *ids, kind=None: [{'name': i, 'pkg': i, 'dep_kinds': [{'kind': kind, 'target': None}]} for i in ids]
        metadata = {
            'packages': [
                package('root', 'text-tools', manifest_path=str(crate / 'Cargo.toml'),
                        targets=[{'kind': ['cdylib', 'rlib'], 'crate_types': ['cdylib', 'rlib']}],
                        dependencies=[{'name': 'octosense-component'}]),
                package('ssl', 'openssl-sys'), package('ray', 'rayon'), package('tok', 'tokio'),
                package('zstd', 'zstd-sys'), package('cc', 'cc'), package('md', 'pulldown-cmark'),
                package('wt', 'wasmtime'), package('rq', 'reqwest'), package('feed', 'feed-rs'),
                package('ai', 'async-openai'),
            ],
            # The component links md, ssl, ray, tok and, through md, zstd and
            # feed; a test (wt, ai) and a build script (rq) need the others, on
            # this machine.
            'resolve': {'root': 'root', 'nodes': [
                {'id': 'root', 'deps': uses('md', 'ssl', 'ray', 'tok') + uses('wt', 'ai', kind='dev') + uses('rq', kind='build')},
                {'id': 'ssl', 'deps': build_cc}, {'id': 'ray', 'deps': []},
                {'id': 'tok', 'deps': [], 'features': ['rt', 'net', 'macros']}, {'id': 'zstd', 'deps': build_cc},
                {'id': 'cc', 'deps': []}, {'id': 'md', 'deps': uses('zstd', 'feed')}, {'id': 'wt', 'deps': uses('tok')},
                {'id': 'rq', 'deps': []}, {'id': 'feed', 'deps': []}, {'id': 'ai', 'deps': []},
            ]},
        }
        done = subprocess.CompletedProcess([], 0, stdout=json.dumps(metadata), stderr='')
        with patch.object(octo.subprocess, 'run', return_value=done) as run:
            findings = octo.dependency_findings('cargo', crate)
        self.assertIn('--filter-platform', run.call_args.args[0])
        self.assertEqual([level for level, _ in findings], ['ok', 'ok', 'fail', 'warn', 'warn', 'warn', 'info'])
        self.assertTrue(findings[2][1].startswith('openssl-sys 1.0.0 links OpenSSL'))
        # What OctoSense already provides: for a direct dependency the
        # component links (md), not for one of its dependencies' (feed) or a
        # test's (ai).
        self.assertEqual(findings[-1][1], 'pulldown-cmark 1.0.0: OctoSense renders Markdown itself: Splash\'s Markdown '
                         'widget shows it, tables included. Ship the crate only to produce HTML or to read Markdown as '
                         'data. (docs/SCRIPT-API.md#widgets-available-to-an-app)')
        text = '\n'.join(t for _, t in findings)
        for expected in ('rayon 1.0.0 starts threads', 'tokio 1.0.0 with net', 'zstd-sys 1.0.0 compiles C code'):
            self.assertIn(expected, text)
        self.assertNotIn('openssl-sys 1.0.0 compiles C code', text)
        self.assertNotIn('wasmtime', text)
        self.assertNotIn('reqwest', text)
        self.assertNotIn('feed-rs', text)
        self.assertNotIn('async-openai', text)

    def test_what_octosense_provides_cites_a_doc_section_store_apps_may_use(self):
        named = [name for names, _, _ in octo.OCTOSENSE_PROVIDES for name in names]
        self.assertEqual(len(named), len(set(named)))
        self.assertEqual(set(named), set(octo.PROVIDED_CRATES))
        self.assertFalse(set(named) & (set(octo.BLOCKING_CRATES) | set(octo.THREAD_CRATES)))
        for names, hint, doc in octo.OCTOSENSE_PROVIDES:
            with self.subTest(crates=names):
                path, _, heading = doc.partition('#')
                source = (HERE.parent / path).read_text(encoding='utf-8')
                self.assertIn(heading, [anchor(h) for h in re.findall(r'^#+ (.+)$', source, re.M)])
                # System apps' engine services are not a store app's.
                self.assertNotRegex(hint, r'\b(photo|pdf|word|llm)\.')

    def test_info_reads_a_file_without_a_hub(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'tools.wasm'
            path.write_bytes(component(ENV, TCP))
            with patch.object(octo, 'component_info_hub', return_value=None):
                code, out, _ = self.octo('wasm', 'info', str(path))
                self.assertEqual(code, 0)
                self.assertIn("read by octo's own reader", out)
                self.assertIn('wasm.count_words(text: string) -> record { words: u32 }', out)
                self.assertIn(f'{TCP}   (refused)', out)
                self.assertIn('crates: not recorded;', out)
                code, out, _ = self.octo('wasm', 'info', str(path), '--json')
                self.assertEqual(json.loads(out), dict(wasm_component.describe(component(ENV, TCP)), crates=None))
                # What a phase 3 component needs, without the app's manifest.
                path.write_bytes(component(CLOCK, FILES, HTTP, HOST_SERVICES))
                code, out, _ = self.octo('wasm', 'info', str(path))
                self.assertEqual(code, 0)
                self.assertIn("reaches: the clock, files in its app folder, the network and its app's host "
                              "services, but no other app", out)
                self.assertIn('"storage" in capabilities (it imports wasi:filesystem), "net" in capabilities '
                              '(it imports wasi:http), the capability of each host service it calls (it imports '
                              'octosense:host', out)
                self.assertNotIn('network.hosts', out)
                # The crates it is built from, as `wasm build` records them.
                path.write_bytes(wasm_component.with_crates(component(ENV), CrateList.INVENTORY))
                code, out, _ = self.octo('wasm', 'info', str(path))
                self.assertEqual(code, 0)
                self.assertIn('built from 2 crates, as its octosense-crates section lists them:\n'
                              '  bitflags 2.13.2, crates.io\n  octosense-component 0.1.0, path\n', out)
                code, out, _ = self.octo('wasm', 'info', str(path), '--json')
                self.assertEqual(json.loads(out)['crates'], CrateList.INVENTORY['crates'])

    @unittest.skipUnless(toolchain(), 'needs cargo and the wasm32-wasip2 target (rustup target add wasm32-wasip2)')
    def test_new_then_build_with_cargo_makes_a_working_bundle(self):
        with tempfile.TemporaryDirectory() as temp:
            app = self.app(temp, capabilities=())
            self.assertEqual(self.octo('wasm', 'new', 'text-tools', '--app', str(app), '--sdk', 'path')[0], 0)
            code, out, err = self.octo('wasm', 'build', '--app', str(app))
            self.assertEqual(code, 0, out + err)
            info = wasm_component.describe((app / 'bundle/fns/text-tools.wasm').read_bytes())
            self.assertEqual([(e['name'], e['params'], e['result']) for e in info['exports']], [
                ('count', [['text', 'string']], 'record { words: u32, lines: u32 }'),
                ('greet', [['name', 'string']], 'string'),
                ('parse-number', [['text', 'string']], 'result<f64, string>'),
            ])
            self.assertEqual(wasm_component.refused_imports(info['imports']), [])
            manifest = json.loads((app / 'bundle/manifest.json').read_text())
            self.assertEqual((manifest['capabilities'], manifest['requires']), (['wasm'], ['wasm-components-v1']))
            # It records the crates it links, and not the proc macros (the
            # SDK's, wit-bindgen's) or what only they use (syn, wit-parser, …),
            # which run in the compiler.
            built = (app / 'bundle/fns/text-tools.wasm').read_bytes()
            crates = wasm_component.recorded_crates(built)['crates']
            self.assertIn({'name': 'octosense-component', 'version': '0.1.0', 'source': 'path'}, crates)
            self.assertIn('wit-bindgen', [c['name'] for c in crates])
            self.assertTrue(all('checksum' in c for c in crates if c['source'] == 'crates.io'))
            self.assertFalse({'syn', 'quote', 'proc-macro2', 'wit-parser', 'octosense-component-macros',
                              'wit-bindgen-rust-macro'} & {c['name'] for c in crates})
            self.assertIn(f'  built from {len(crates)} crates (tools/octo wasm info lists them)', out)
            # The release workflow's step, on the component cargo built,
            # writes the same bytes.
            section = next(s for s in wasm_component.custom_sections(built) if s[2] == b'octosense-crates')
            step = release_step()
            with patch.dict(os.environ, {'PATH': os.pathsep.join([str(Path(octo.cargo_path()).parent), os.environ.get('PATH', '')])}):
                self.assertEqual(step['with_crates'](built[:section[0]], step['crates'](app / 'components/text-tools/Cargo.toml')), built)


class ReleaseBuildsComponents(unittest.TestCase):
    """The release workflow's step that builds components/ from the tagged
    commit (tools/publish-app.template.yml): its refusals, which need no
    compiler. tools/ tests build a real component elsewhere."""

    def run_step(self, sdk_line, lock=False):
        with tempfile.TemporaryDirectory() as tmp:
            crate = Path(tmp) / 'app' / 'components' / 'text-tools'
            (crate / 'src').mkdir(parents=True)
            (crate / 'src' / 'lib.rs').write_text('')
            (crate / 'Cargo.toml').write_text(
                '[package]\nname = "text-tools"\nversion = "0.1.0"\nedition = "2024"\n\n'
                '[lib]\ncrate-type = ["cdylib", "rlib"]\n\n[dependencies]\n' + sdk_line + '\n\n[workspace]\n')
            if lock:
                (crate / 'Cargo.lock').write_text('version = 4\n')
            (Path(tmp) / 'step.py').write_text(release_step_script())
            return subprocess.run(['python3', 'step.py'], cwd=tmp, capture_output=True, text=True)

    def test_a_local_sdk_path_stops_the_release(self):
        run = self.run_step('octosense-component = { path = "/somewhere/on/my/mac/sdk/rust/octosense-component" }')
        self.assertNotEqual(run.returncode, 0)
        self.assertIn('takes the SDK from a local path', run.stdout + run.stderr)

    @unittest.skipUnless(shutil.which('cargo'), 'needs cargo')
    def test_a_crate_without_its_lockfile_stops_the_release(self):
        run = self.run_step('octosense-component = { git = "https://github.com/OctoSense-org/OctoSense-App-Flow", rev = "' + '0' * 40 + '" }')
        self.assertNotEqual(run.returncode, 0)
        self.assertIn('has no Cargo.lock', run.stdout + run.stderr)

    @unittest.skipUnless(toolchain() and shutil.which('cargo'), 'needs cargo and the wasm32-wasip2 target, on PATH')
    def test_the_release_records_the_crates_octo_records(self):
        # A crate `tools/octo wasm new` writes, with the SDK by path: the
        # step's own refusal of a path is skipped by calling its functions.
        with tempfile.TemporaryDirectory() as temp:
            app = WasmCommands.app(self, temp, capabilities=())
            self.assertEqual(WasmCommands.octo(self, 'wasm', 'new', 'text-tools', '--app', str(app), '--sdk', 'path')[0], 0)
            crate = app / 'components/text-tools'
            ours = wasm_component.crate_inventory(shutil.which('cargo'), crate)  # cargo writes Cargo.lock
            step = release_step()
            theirs = step['crates'](crate / 'Cargo.toml')  # cargo metadata --locked
            self.assertEqual(theirs, ours)
            self.assertIn({'name': 'octosense-component', 'version': '0.1.0', 'source': 'path'}, ours['crates'])
            self.assertFalse({'syn', 'quote', 'wit-parser', 'octosense-component-macros'} & {c['name'] for c in ours['crates']})
            # The same bytes, replacing a stale list.
            stale = wasm_component.with_crates(component(ENV), {'schema': 1, 'crates': []})
            self.assertEqual(step['with_crates'](stale, theirs), wasm_component.with_crates(stale, ours))
            self.assertEqual(wasm_component.recorded_crates(step['with_crates'](stale, theirs)), ours)


class CrateList(unittest.TestCase):
    """The crates a component is built from, in its octosense-crates section:
    octo's tools/wasm_component.py and the release step write the same bytes."""
    INVENTORY = {'schema': 1, 'crates': [
        {'name': 'bitflags', 'version': '2.13.2', 'source': 'crates.io', 'checksum': '3d' * 32},
        {'name': 'octosense-component', 'version': '0.1.0', 'source': 'path'},
    ]}

    def test_the_list_is_one_custom_section_at_the_very_end(self):
        bare = component(ENV)
        payload = ('{"crates":[{"checksum":"' + '3d' * 32 + '","name":"bitflags","source":"crates.io","version":"2.13.2"},'
                   '{"name":"octosense-component","source":"path","version":"0.1.0"}],"schema":1}').encode()
        section = custom('octosense-crates', payload)
        self.assertEqual(wasm_component.with_crates(bare, self.INVENTORY), bare + section)
        self.assertEqual(wasm_component.recorded_crates(bare + section), self.INVENTORY)
        self.assertIsNone(wasm_component.recorded_crates(bare))
        self.assertEqual(wasm_component.describe(bare + section), wasm_component.describe(bare))
        # One already there is replaced, wherever it is; other custom
        # sections stay where they are.
        producers = custom('producers', b'\x00')
        stale = custom('octosense-crates', b'{"crates":[],"schema":1}')
        old = bare[:8] + stale + bare[8:] + producers + stale
        self.assertEqual(wasm_component.with_crates(old, self.INVENTORY), bare + producers + section)
        step = release_step()
        for data in (bare, old, bare + section, wasm_component.MODULE_PREAMBLE + producers):
            with self.subTest(data=data[-12:]):
                self.assertEqual(step['with_crates'](data, self.INVENTORY), wasm_component.with_crates(data, self.INVENTORY))
        # A size past 127 takes two bytes.
        many = {'schema': 1, 'crates': [dict(self.INVENTORY['crates'][1], name=f'crate-{i}') for i in range(9)]}
        self.assertEqual(step['with_crates'](bare, many), wasm_component.with_crates(bare, many))
        self.assertEqual(wasm_component.recorded_crates(wasm_component.with_crates(bare, many)), many)
        # What a reader refuses.
        for bad in (bare + stale + producers + stale, bare + custom('octosense-crates', b'{nope'),
                    bare + custom('octosense-crates', b'{"schema":2,"crates":[]}')):
            with self.subTest(bad=bad[-12:]), self.assertRaises(wasm_component.ReadError):
                wasm_component.recorded_crates(bad)

    def test_the_list_follows_normal_dependencies_and_never_enters_a_proc_macro(self):
        sdk = 'git+https://github.com/OctoSense-org/OctoSense-App-Flow?rev=e8f15dd9#e8f15dd9' + '0' * 32
        flags = 'git+https://github.com/example/bitflags?branch=main#' + 'a' * 40
        other = 'registry+https://registry.example.com/index'
        sparse = 'sparse+https://index.crates.io/'
        normal, dev, build = [{'kind': None, 'target': None}], [{'kind': 'dev', 'target': None}], [{'kind': 'build', 'target': None}]
        with tempfile.TemporaryDirectory() as temp:
            crate = Path(temp)
            (crate / 'Cargo.toml').write_text('[package]\n')
            packages, nodes = [], []

            def add(id, name, version, source, deps=(), kinds=('lib',)):
                packages.append({'id': id, 'name': name, 'version': version, 'source': source,
                                 'manifest_path': str(crate / 'Cargo.toml') if id == 'root' else f'/x/{id}/Cargo.toml',
                                 'targets': [{'kind': [kind]} for kind in kinds]})
                nodes.append({'id': id, 'deps': [{'name': d.replace('-', '_'), 'pkg': d, 'dep_kinds': k} for d, k in deps]})

            add('root', 'text-tools', '0.1.0', None, [('bindgen', normal), ('sdk', normal), ('mine', normal),
                                                       ('macros', normal), ('serde', normal), ('private', normal),
                                                       ('syn1', normal), ('wasmtime', dev), ('cc', build)], ('cdylib', 'rlib'))
            add('bindgen', 'wit-bindgen', '0.62.0', CRATES_IO_INDEX)
            add('sdk', 'octosense-component', '0.1.0', sdk, [('flags', normal)])
            add('flags', 'bitflags', '2.0.0', flags)
            add('mine', 'my-lib', '0.1.0', None)
            # A proc macro with a build script; what only it uses stays out.
            add('macros', 'my-macros', '0.1.0', CRATES_IO_INDEX, [('syn2', normal), ('itoa', normal)], ('proc-macro', 'custom-build'))
            add('syn2', 'syn', '2.0.1', CRATES_IO_INDEX, [('ident', normal)])
            add('ident', 'unicode-ident', '1.0.0', CRATES_IO_INDEX)
            add('serde', 'serde', '1.0.0', sparse, [('itoa', normal)])
            add('itoa', 'itoa', '1.0.0', CRATES_IO_INDEX)
            add('private', 'private', '1.0.0', other)
            add('syn1', 'syn', '1.0.109', CRATES_IO_INDEX)
            add('wasmtime', 'wasmtime', '49.0.2', CRATES_IO_INDEX)
            add('cc', 'cc', '1.0.0', CRATES_IO_INDEX)
            lock = ['version = 4']
            for name, version, source, checksum in (
                    ('itoa', '1.0.0', CRATES_IO_INDEX, '11'), ('serde', '1.0.0', CRATES_IO_INDEX, '22'),
                    ('syn', '1.0.109', CRATES_IO_INDEX, '33'), ('syn', '2.0.1', CRATES_IO_INDEX, '44'),
                    ('wit-bindgen', '0.62.0', CRATES_IO_INDEX, '55'), ('private', '1.0.0', other, '66'),
                    ('octosense-component', '0.1.0', sdk, None), ('bitflags', '2.0.0', flags, None),
                    ('my-lib', '0.1.0', None, None), ('text-tools', '0.1.0', None, None)):
                lock += ['', '[[package]]', f'name = "{name}"', f'version = "{version}"']
                lock += [f'source = "{source}"'] if source else []
                lock += [f'checksum = "{checksum * 32}"'] if checksum else []
                lock += ['dependencies = [', ' "x",', ']']
            lock += ['', '[[patch.unused]]', 'name = "itoa"', 'version = "9.9.9"', 'checksum = "' + '99' * 32 + '"']
            (crate / 'Cargo.lock').write_text('\n'.join(lock) + '\n')
            meta = {'packages': packages, 'workspace_root': str(crate), 'resolve': {'root': 'root', 'nodes': nodes}}
            done = subprocess.CompletedProcess([], 0, stdout=json.dumps(meta), stderr='')
            with patch.object(subprocess, 'run', return_value=done) as run:
                ours = wasm_component.crate_inventory('cargo', crate)
                theirs = release_step()['crates'](crate / 'Cargo.toml')
        self.assertIn('--filter-platform', run.call_args_list[0].args[0])
        self.assertEqual(theirs, ours)
        self.assertEqual(ours, {'schema': 1, 'crates': [
            {'name': 'bitflags', 'version': '2.0.0', 'source': 'git+https://github.com/example/bitflags#' + 'a' * 40},
            {'name': 'itoa', 'version': '1.0.0', 'source': 'crates.io', 'checksum': '11' * 32},
            {'name': 'my-lib', 'version': '0.1.0', 'source': 'path'},
            {'name': 'octosense-component', 'version': '0.1.0',
             'source': 'git+https://github.com/OctoSense-org/OctoSense-App-Flow#e8f15dd9' + '0' * 32},
            {'name': 'private', 'version': '1.0.0', 'source': other, 'checksum': '66' * 32},
            {'name': 'serde', 'version': '1.0.0', 'source': 'crates.io', 'checksum': '22' * 32},
            {'name': 'syn', 'version': '1.0.109', 'source': 'crates.io', 'checksum': '33' * 32},
            {'name': 'wit-bindgen', 'version': '0.62.0', 'source': 'crates.io', 'checksum': '55' * 32},
        ]})


if __name__ == '__main__':
    unittest.main()
