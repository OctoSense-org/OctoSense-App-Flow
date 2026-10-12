"""All AppCards consume the runtime release published by Octoscript-Makepad."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import re
import subprocess

from core.native_paths import APPCARDS, WORKSPACE

RUNTIME_URL = "https://github.com/OctoSense-org/Octoscript-Makepad.git"


def git(path, *args, check=True):
    return subprocess.run(["git", "-C", str(path), *args], check=check,
                          capture_output=True, text=True, encoding="utf-8")


def runtime_lock():
    value = json.loads((APPCARDS / "native-runtime.lock.json").read_text(encoding="utf-8"))
    if value.get("schema_version") != 1 or value.get("url") != RUNTIME_URL:
        raise ValueError("AppCards must use the OctoSense-org/Octoscript-Makepad runtime")
    if not re.fullmatch(r"[0-9a-f]{40}", value.get("revision", "")):
        raise ValueError("The runtime must be pinned to a full Git commit")
    return value


def runtime_tool(root):
    path = Path(root) / "octoscript-makepad/tools/runtime.py"
    spec = importlib.util.spec_from_file_location("octoscript_runtime", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def prepare(root=WORKSPACE, *, update=False, cache=WORKSPACE):
    root = Path(root).resolve()
    cache = Path(cache).resolve()
    if root == APPCARDS or root.is_relative_to(APPCARDS):
        raise RuntimeError("Native repositories must stay outside AppCards")
    locked = runtime_lock()
    runtime = root / "octoscript-makepad"
    if (runtime / ".git").exists():
        if git(runtime, "status", "--porcelain", "--untracked-files=normal").stdout:
            raise RuntimeError(f"Preserving local runtime edits in {runtime}")
        current = git(runtime, "rev-parse", "--verify", "HEAD", check=False).stdout.strip()
        if current and current != locked["revision"] and not update:
            raise RuntimeError(f"{runtime} has another version; update the clean workspace or choose another runtime root")
    else:
        if runtime.exists() and any(runtime.iterdir()):
            raise RuntimeError(f"Preserving non-Git directory {runtime}")
        runtime.mkdir(parents=True, exist_ok=True)
        git(runtime, "init", "--quiet")
        git(runtime, "remote", "add", "origin", locked["url"])
    if git(runtime, "cat-file", "-e", locked["revision"] + "^{commit}", check=False).returncode:
        cached = Path(cache) / "octoscript-makepad"
        source = str(cached) if cached != runtime and (cached / ".git").exists() and not git(
            cached, "cat-file", "-e", locked["revision"] + "^{commit}", check=False).returncode else "origin"
        git(runtime, "fetch", "--quiet", "--no-tags", "--depth=1", source, locked["revision"])
    # Inspect the release manifest before checkout, preserving existing local dependencies.
    closure = json.loads(git(runtime, "show", locked["revision"] + ":runtime.json").stdout)
    for name in closure["repositories"]:
        path = root / name
        if (path / ".git").exists() and git(path, "status", "--porcelain", "--untracked-files=normal").stdout:
            raise RuntimeError(f"Preserving local dependency edits in {path}")
    git(runtime, "checkout", "--quiet", "--detach", locked["revision"])
    return runtime_tool(root).prepare(root, update=update, cache=cache)


def verify(root=WORKSPACE):
    root = Path(root).resolve()
    locked = runtime_lock()
    runtime = root / "octoscript-makepad"
    if not (runtime / ".git").exists() or git(runtime, "rev-parse", "HEAD").stdout.strip() != locked["revision"]:
        raise RuntimeError("Run the AppCards native setup command to prepare the locked Octoscript-Makepad release")
    if git(runtime, "status", "--porcelain", "--untracked-files=normal").stdout:
        raise RuntimeError("Octoscript-Makepad has unrecorded changes; commit the runtime before validating an app")
    tool = runtime_tool(root)
    result = tool.verify(root)
    tool.verify_consumer(root, APPCARDS)
    return result


def dependencies(root):
    return {name: Path(root) / name for name in ("makepad", "octoscript", "octoscript-makepad")}
