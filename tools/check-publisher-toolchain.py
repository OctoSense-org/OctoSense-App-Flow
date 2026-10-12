#!/usr/bin/env python3
"""Build and exercise the pinned publisher; no network calls by guests or publication.

Prepare the Hub checkout and its runtime siblings first (see CI). The SDK's
real HTTP, socket, host-service and filesystem components are built from this checkout.
The one-pixel image is structural test data, never an app screenshot or UX proof.
"""
import argparse
import base64
import json
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def run(*args, cwd=None, success=True):
    result = subprocess.run([str(arg) for arg in args], cwd=cwd,
                            capture_output=True, text=True, timeout=120)
    if (result.returncode == 0) != success:
        raise AssertionError(f"{args[0]} {args[1]}: unexpected exit {result.returncode}\n"
                             + result.stdout + result.stderr)
    return result.stdout + result.stderr


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')


def bundle_at(root, wasm):
    bundle = root / 'bundle'
    (bundle / 'fns').mkdir(parents=True)
    (bundle / 'fns/probe.wasm').write_bytes(wasm)
    (bundle / 'main.splash').write_text('Label{text: "Publisher fixture"}\n')
    (bundle / 'icon.svg').write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64">'
        '<rect width="64" height="64" fill="#146"/></svg>')
    (bundle / 'structural-fixture.png').write_bytes(base64.b64decode(
        'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+ip1sAAAAASUVORK5CYII='))
    write_json(bundle / 'listing.json', {
        'schema': 1, 'description': 'Structural publisher regression fixture; not a submitted app.',
        'category': 'utilities', 'screenshots': ['structural-fixture.png'],
        'icon': 'icon.svg', 'platforms': ['macos'], 'age_rating': 'all',
        'publisher': {'name': 'Example', 'support': 'https://example.test/support',
                      'privacy_policy_url': 'https://example.test/privacy'},
    })
    # Deliberately omit all usage declarations. ABI, proof and structural
    # validation must remain active; declaration omission is not a refusal.
    write_json(bundle / 'manifest.json', {
        'schema': 1, 'id': 'dev.example.publisher-probe', 'name': 'Publisher fixture',
        'version': '0.1.0', 'requires': ['wasm-components-v1'],
        'integrity': {'bundle_blake3': ''},
    })
    return bundle


def check(hub, bundle, success=True):
    run(hub, 'stamp', bundle)
    output = run(hub, 'check', bundle, '--allow-unsigned', '--json', success=success)
    # Refusals append a diagnostic to stderr after the JSON report.
    report, _ = json.JSONDecoder().raw_decode(output)
    assert report['passed'] is success, output
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--hub-source', type=Path, required=True)
    parser.add_argument('--target-dir', type=Path,
                        help='Optional existing Cargo cache for the pinned Hub build')
    parser.add_argument('--component-target-dir', type=Path,
                        default=ROOT / 'sdk/rust/target/e2e-wasm')
    args = parser.parse_args()
    source = args.hub_source.resolve()
    pin = json.loads((ROOT / 'tools/publisher-toolchain.json').read_text())
    head = run('git', 'rev-parse', 'HEAD', cwd=source).strip()
    assert head == pin['revision'], f'Hub checkout {head} differs from publisher pin {pin["revision"]}'
    assert not run('git', 'status', '--porcelain', '--untracked-files=no', cwd=source).strip(), \
        'Hub tracked source must be clean'
    target = (args.target_dir or source / 'target').resolve()
    # Always build: accepting an arbitrary pre-existing executable would not
    # prove the JSON-selected publisher revision is the tool being tested.
    subprocess.run(['cargo', 'build', '--locked', '-p', 'octosense-app-hub',
                    '--target-dir', str(target)], cwd=source, check=True)
    hub = target / 'debug' / ('hub.exe' if os.name == 'nt' else 'hub')
    components = args.component_target_dir.resolve()
    subprocess.run(['cargo', 'build', '--locked', '--release', '--target', 'wasm32-wasip2',
                    '--target-dir', str(components), '-p', 'http-client', '-p', 'host-services',
                    '-p', 'markdown-tools', '-p', 'socket-client'], cwd=ROOT / 'sdk/rust', check=True)
    checks = []
    with tempfile.TemporaryDirectory(prefix='publisher-toolchain-') as temp:
        for name, package in [('http_client', 'wasi:http/'),
                              ('host_services', 'octosense:host/'),
                              ('markdown_tools', 'wasi:filesystem/'),
                              ('socket_client', 'wasi:sockets/')]:
            root = Path(temp) / name
            wasm = components / 'wasm32-wasip2/release' / (name + '.wasm')
            info = json.loads(run(hub, 'component-info', wasm))
            assert info['kind'] == 'component' and any(
                value.startswith(package) for value in info['imports']), info
            bundle = bundle_at(root, wasm.read_bytes())
            if name == 'socket_client':
                denied = check(hub, bundle, success=False)
                assert any('wasm.sockets@1' in f['detail'] for f in denied['findings']), denied
                manifest_file = bundle / 'manifest.json'
                manifest = json.loads(manifest_file.read_text())
                manifest['requires'].append('host-api-v1')
                manifest['host_api'] = {'required': {'wasm.sockets': 1}}
                write_json(manifest_file, manifest)
                checks.append('socket_client: missing socket host ABI refused')
            report = check(hub, bundle)
            assert any(f['check'] == 'functions' for f in report['findings']), report
            checks.append(name + ': bundled imports accepted without declarations')

            draft = root / 'component-draft.json'
            write_json(draft, {
                'component': {'schema': 1, 'id': 'dev.example.' + name.replace('_', '-'),
                              'version': '0.1.0', 'name': 'Publisher probe', 'license': 'Apache-2.0',
                              'publisher': {'name': 'Example', 'support': 'https://example.test/support',
                                            'privacy_policy_url': 'https://example.test/privacy'}},
                'listing': {'subtitle': 'Publisher probe', 'description': 'Structural regression fixture'},
            })
            release = root / 'release.json'
            run(hub, 'component-prepare', wasm, '--draft', draft, '--out', release)
            shared = json.loads(run(hub, 'component-check', release, '--wasm', wasm,
                                    '--allow-unsigned', '--json'))
            assert shared['passed'], shared
            denied = run(hub, 'component-check', release, '--wasm', wasm, success=False)
            assert 'GitHub-attested' in denied, denied
            checks.append(name + ': shared component accepted; missing publisher proof refused')

            manifest_file = bundle / 'manifest.json'
            manifest = json.loads(manifest_file.read_text())
            manifest['requires'] = ['host-api-v1'] if name == 'socket_client' else []
            write_json(manifest_file, manifest)
            denied = check(hub, bundle, success=False)
            assert any('must require wasm-components-v1' in f['detail'] for f in denied['findings']), denied
            component = json.loads(release.read_text())['component']
            manifest['components'] = [{'as': 'shared_probe', 'id': component['id'],
                                       'version': component['version'], 'blake3': component['wasm_blake3']}]
            manifest['requires'] = ['wasm-components-v1', 'wasm-shared-components-v1']
            if name == 'socket_client':
                manifest['requires'].append('host-api-v1')
            write_json(manifest_file, manifest)
            shared_app = check(hub, bundle)
            assert any(f['check'] == 'components' and 'not resolved' in f['detail']
                       for f in shared_app['findings']), shared_app
            subject = root / 'octosense-app-manifest.json'
            prepared = json.loads(run(hub, 'publisher-prepare', bundle, '--repository', 'example/publisher-probe',
                                     '--repository-id', '123', '--owner-id', '456', '--workflow',
                                     '.github/workflows/publish-app.yml', '--tag', 'v0.1.0',
                                     '--commit', 'a' * 40, '--out', subject))
            assert prepared['status'] == 'awaiting-github-attestation', prepared
            sealed = json.loads(subject.read_text())
            assert set(manifest['requires']) <= set(sealed['requires']), sealed
            assert sealed['components'] == manifest['components'], sealed
            if name == 'socket_client':
                assert sealed['host_api']['required'] == {'wasm.sockets': 1}, sealed
            denied = run(hub, 'publisher-verify', bundle, success=False)
            assert 'attestation' in denied.lower() or 'proof' in denied.lower(), denied
            pack = root / 'app.bundle.pack.json'
            run(hub, 'publisher-pack', bundle, '--out', pack, success=False)
            assert not pack.exists(), 'an unattested app must not produce a release pack'
            checks.append(name + ': ABI required; shared pins preserved; unattested pack refused')

        # The genuine socket fixture must also require the host API. Admitting
        # its import package must not admit an incompatible manifest or
        # malformed component bytes.
        socket = source / 'crates/app-hub/tests/fixtures/netprobe.component.wasm'
        bundle = bundle_at(Path(temp) / 'sockets', socket.read_bytes())
        denied = check(hub, bundle, success=False)
        assert any('wasm.sockets@1' in f['detail'] for f in denied['findings']), denied
        (bundle / 'fns/probe.wasm').write_bytes(b'\0asm\x0d\x00\x01\x00\xff')
        denied = check(hub, bundle, success=False)
        assert any(f['check'] == 'functions' for f in denied['findings']), denied
        checks.append('socket imports without required host ABI and malformed components refused')
    print(json.dumps({'publisher_revision': head, 'checks': checks, 'passed': len(checks),
                      'scope': 'structural admission and preparation; no catalog resolution, attestation, publication or guest execution'},
                     indent=2))


if __name__ == '__main__':
    main()
