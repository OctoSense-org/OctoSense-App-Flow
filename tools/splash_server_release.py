#!/usr/bin/env python3
"""The Splash language server's release: one naming convention, one version record.

The `splash-lsp` binary is built from a makepad checkout, and the makepad fork
has no CI of its own — so the release is produced here, from the revision this
file pins, under a name that says which server and which platform it is. A
version nobody records is a version nobody can pin: the extension's download
(the server arrives with the plugin) reads this record rather than carrying its
own copy of the number.

Run it with no arguments to print the release as it is recorded, or with
`--build-plan <target>` to emit the shell assignments one build needs — which is
also the guard: a target nothing was published for exits non-zero, so a runner
cannot quietly produce an asset the record does not name.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
PIN = HERE / 'splash-server-toolchain.json'


def asset_name(name, version, target):
    """The release asset for one server build.

    Version and target both belong in the name: a downloader that fetches
    `splash-lsp.zip` has no way to tell which of two servers it just got, and a
    human reading a release page cannot tell which platform one is for.
    """
    return f'{name}-{version}-{target}.zip'


def release_tag(name, version):
    """The tag the whole server release lives under, namespaced per server."""
    return f'{name}-v{version}'


def download_url(repository, tag, asset):
    """Where a release asset is fetched from, for a repository that holds it."""
    return f'https://github.com/{repository}/releases/download/{tag}/{asset}'


def repository_of(url):
    """The `owner/name` a git URL names, which is what a checkout action takes."""
    return url.removeprefix('https://github.com/').removesuffix('.git')


def runtime_lock(pin):
    """The sibling checkout a build needs, and the lock that pins it.

    makepad patches `octoscript-node` to a path outside its own tree, so the
    build is only reproducible with that sibling beside it at a known revision.
    This repository already locks the shared runtime for its flows, and CI runs
    `tools/setup-native.py --check` over that lock, so its shape is guarded
    elsewhere: this reads it rather than validating it a second time.
    """
    path = HERE.parent / pin['runtime']['lock']
    locked = json.loads(path.read_text(encoding='utf-8'))
    return {'repository': repository_of(locked['url']), 'revision': locked['revision']}


def read_pin(path=PIN):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def published(pin):
    """The platforms that have an asset. Everything else is a promise."""
    return [platform for platform in pin['platforms'] if 'asset' in platform]


def unpublished(pin):
    return [platform for platform in pin['platforms'] if 'asset' not in platform]


def download(pin, platform):
    """The URL for a platform, or None when nothing was published for it.

    None is the honest answer: a URL that 404s is worse than an absent one,
    because a downloader cannot tell "not built yet" from "the network is down".
    """
    server = pin['server']
    for entry in published(pin):
        if entry['platform'] == platform:
            return download_url(server['release']['repository'], server['release']['tag'], entry['asset'])
    return None


def build_plan(pin, target):
    """Everything one build of one target needs, as shell assignments.

    Every value is a slug, a version, a revision or a name — nothing that could
    carry a newline or a `=` — so the caller can append this straight to
    `$GITHUB_OUTPUT`. A target nothing was published for returns None: the
    release path must not be able to produce an asset the record does not name.
    """
    for entry in published(pin):
        if entry['target'] == target:
            server, source = pin['server'], pin['server']['source']
            locked = runtime_lock(pin)
            return {
                'name': server['name'],
                'version': server['version'],
                'tag': server['release']['tag'],
                'release-repository': server['release']['repository'],
                'source-repository': source['repository'],
                'source-revision': source['revision'],
                'source-package': source['package'],
                'source-bin': source['bin'],
                'source-features': ','.join(source['features']),
                'runtime-repository': locked['repository'],
                'runtime-revision': locked['revision'],
                'runtime-sibling': pin['runtime']['sibling'],
                'target': target,
                'asset': entry['asset'],
            }
    return None


def describe(pin):
    """The record as a downloader or a release page reads it."""
    server = pin['server']
    return {
        'name': server['name'],
        'version': server['version'],
        'source-revision': server['source']['revision'],
        'tag': server['release']['tag'],
        'assets': [download(pin, entry['platform']) for entry in published(pin)],
        'missing': [entry['platform'] for entry in unpublished(pin)],
    }


def release_notes(pin, assets):
    """The release page for the assets actually uploaded, as Markdown.

    The digests are computed here rather than recorded in advance: a rebuilt
    binary is a different binary, so a digest committed ahead of the build would
    only be a promise the next build breaks. Written at publish time, the digest
    describes the bytes that were uploaded.
    """
    assets = Path(assets)
    server, source = pin['server'], pin['server']['source']
    revision = source['revision']
    lines = [
        f"The `{server['name']}` language server, version {server['version']}.",
        '',
        'Built from '
        f"[{revision[:12]}](https://github.com/{source['repository']}/commit/{revision})"
        f" -- package `{source['package']}`, features `{', '.join(source['features'])}`.",
        '',
        '| Platform | Asset | SHA-256 |',
        '| --- | --- | --- |',
    ]
    for entry in published(pin):
        asset = assets / entry['asset']
        if not asset.is_file():
            raise FileNotFoundError(f'no {entry["asset"]} in {assets}')
        digest = hashlib.sha256(asset.read_bytes()).hexdigest()
        lines.append(f"| `{entry['platform']}` ({entry['target']}) | `{asset.name}` | `{digest}` |")
    missing = ', '.join(entry['platform'] for entry in unpublished(pin))
    lines += [
        '',
        'Recorded in `tools/splash-server-toolchain.json`, which also names the'
        f' platforms with no asset yet: {missing}.',
        '',
    ]
    return '\n'.join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--pin', default=str(PIN), help='the version record to read')
    parser.add_argument('--build-plan', metavar='TARGET',
                        help='print the shell assignments one build of this Rust target needs')
    args = parser.parse_args(argv)
    pin = read_pin(args.pin)
    if args.build_plan:
        plan = build_plan(pin, args.build_plan)
        if plan is None:
            print(f"{pin['server']['name']}: no published asset for {args.build_plan}; "
                  f"publish it and record it in {args.pin} first", file=sys.stderr)
            return 1
        for key, value in plan.items():
            print(f'{key}={value}')
        return 0
    json.dump(describe(pin), sys.stdout, indent=2)
    sys.stdout.write('\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
