#!/usr/bin/env python3
"""Prepare the one Octoscript-Makepad release shared by all AppCards."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

# Windows decodes every read_text() below (and inside the runtime tools this
# script loads in-process) with the ANSI code page, e.g. GBK, while the
# sources are UTF-8. Restart once in UTF-8 mode (PEP 540) instead of
# pinning an encoding at every call site across repositories.
if os.name == "nt" and not sys.flags.utf8_mode:
    os.environ["PYTHONUTF8"] = "1"
    sys.exit(subprocess.run([sys.executable, *sys.argv]).returncode)

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "flows"))
from core.native_paths import WORKSPACE
from core.native_runtime import prepare, verify, runtime_tool


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=WORKSPACE)
    parser.add_argument("--cache", type=Path, default=WORKSPACE)
    parser.add_argument("--update", action="store_true", help="Update clean source checkouts to the locked release")
    parser.add_argument("--check", action="store_true", help="Verify prepared sources without changing them")
    parser.add_argument("--cargo-manifest", type=Path)
    args = parser.parse_args()
    result = verify(args.root) if args.check else prepare(args.root, update=args.update, cache=args.cache)
    runtime_tool(args.root).verify_consumer(args.root, Path(__file__).resolve().parents[1])
    if args.cargo_manifest:
        result["cargo_sources"] = runtime_tool(args.root).verify_cargo(args.root, args.cargo_manifest)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
