"""Bundle text keeps its UTF-8 bytes on non-UTF-8 Windows installations."""
import argparse
import contextlib
import importlib.machinery
import importlib.util
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
loader = importlib.machinery.SourceFileLoader('encoding_octo', str(HERE / 'octo'))
spec = importlib.util.spec_from_loader(loader.name, loader)
octo = importlib.util.module_from_spec(spec)
loader.exec_module(octo)


@contextlib.contextmanager
def legacy_windows_text():
    """Use real file I/O with CP936 and CRLF only when no format is specified."""
    original_open = io.open

    def open_file(file, mode='r', buffering=-1, encoding=None, errors=None,
                  newline=None, closefd=True, opener=None):
        if 'b' not in mode:
            encoding = encoding or 'cp936'
            if newline is None and any(flag in mode for flag in ('w', 'a', '+')):
                newline = '\r\n'
        return original_open(file, mode, buffering, encoding, errors, newline,
                             closefd, opener)

    with patch.object(io, 'text_encoding', create=True, side_effect=lambda encoding, stacklevel=2: encoding or 'cp936'), \
            patch.object(io, 'open', side_effect=open_file):
        yield


class BundleEncoding(unittest.TestCase):
    def app(self, root):
        app = Path(root) / 'app'
        (app / 'bundle').mkdir(parents=True)
        (app / 'bundle/manifest.json').write_bytes(json.dumps({
            'id': 'dev.example.brief', 'name': '晨报📰…', 'version': '0.1.0',
            'integrity': {'signature': 'signed-fixture'},
        }, ensure_ascii=False).encode('utf-8'))
        return app

    def test_new_preserves_unicode_source_and_lf_bytes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            template = root / 'template'
            shutil.copytree(octo.TEMPLATE, template)
            source = 'Label{text: "晨报📰…"}\n'
            (template / 'bundle/main.splash').write_bytes(source.encode('utf-8'))
            dest = root / 'brief'
            args = argparse.Namespace(dir=str(dest), id='dev.example.brief',
                                      name='Brief', platform=['windows'], system=False)
            with patch.object(octo, 'TEMPLATE', template), \
                    patch.object(octo, 'find_binary', return_value=(None, None, [])), \
                    legacy_windows_text(), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(octo.cmd_new(args), 0)
            self.assertEqual((dest / 'bundle/main.splash').read_bytes(), source.encode('utf-8'))
            for name in ('manifest.json', 'listing.json'):
                raw = (dest / 'bundle' / name).read_bytes()
                json.loads(raw.decode('utf-8'))
                self.assertNotIn(b'\r\n', raw)

    def test_publish_reads_unicode_manifest_and_installs_only_once(self):
        with tempfile.TemporaryDirectory() as temp:
            app = self.app(temp)
            manifest = app / 'bundle/manifest.json'
            value = json.loads(manifest.read_bytes())
            value['integrity'] = {'bundle_blake3': 'development'}
            manifest.write_bytes(json.dumps(value, ensure_ascii=False).encode('utf-8'))
            original = manifest.read_bytes()
            workflow_text = '# 晨报📰…\nname: fixture\n'
            args = argparse.Namespace(dir=str(app), replace=False)
            with patch.object(octo, 'publisher_workflow', return_value=workflow_text), \
                    legacy_windows_text(), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(octo.cmd_publish_github(args), 0)
                workflow = app / '.github/workflows/publish-app.yml'
                before = workflow.stat().st_mtime_ns
                self.assertEqual(octo.cmd_publish_github(args), 0)
                self.assertEqual(workflow.stat().st_mtime_ns, before)
            self.assertEqual(workflow.read_bytes(), workflow_text.encode('utf-8'))
            self.assertEqual(manifest.read_bytes(), original)

    def test_check_reads_unicode_listing_without_restamping_signed_bytes(self):
        with tempfile.TemporaryDirectory() as temp:
            app = self.app(temp)
            bundle = app / 'bundle'
            (bundle / 'listing.json').write_bytes('{"description":"晨报📰"}'.encode('utf-8'))
            original = (bundle / 'manifest.json').read_bytes()
            args = argparse.Namespace(bundle=str(bundle), catalog=None, publisher_key=[])
            with patch.object(octo, 'need', return_value=Path('/fixture/hub')), \
                    patch.object(octo.subprocess, 'run') as run, \
                    legacy_windows_text(), contextlib.redirect_stdout(io.StringIO()):
                run.return_value.returncode = 0
                run.return_value.stdout = run.return_value.stderr = ''
                self.assertEqual(octo.cmd_check(args, []), 0)
                self.assertEqual(run.call_count, 1)
            self.assertEqual((bundle / 'manifest.json').read_bytes(), original)

    def test_run_still_refuses_unicode_signed_manifest_before_startup(self):
        with tempfile.TemporaryDirectory() as temp:
            app = self.app(temp)
            args = argparse.Namespace(bundle=str(app / 'bundle'))
            error = io.StringIO()
            with patch.object(octo, 'need') as binary, legacy_windows_text(), \
                    contextlib.redirect_stderr(error), self.assertRaises(SystemExit):
                octo.cmd_run(args)
            self.assertIn('cannot run a sealed release', error.getvalue())
            binary.assert_not_called()


if __name__ == '__main__':
    unittest.main()
