"""Shared native repositories live outside AppCards, in the organization workspace."""
from pathlib import Path
import os

APPCARDS = Path(__file__).resolve().parents[2]
WORKSPACE = Path(os.environ.get(
    "OCTOSENSE_WORKSPACE",
    APPCARDS.parent,
)).resolve()
DIRECTORIES = {"makepad": "makepad", "splash": "octoscript", "splash-makepad": "octoscript-makepad"}


def repository(name, workspace=None):
    return Path(workspace or os.environ.get("OCTOS_APPCARD_NATIVE_ROOT", WORKSPACE)) / DIRECTORIES.get(name, name)


def adapt_cargo_paths(repo):
    """Adapt the pinned upstream sibling directory name; leave Rust crate names intact."""
    import subprocess
    names = subprocess.check_output(["git", "-C", str(repo), "ls-files", "--", "*Cargo.toml"], text=True, encoding="utf-8").splitlines()
    for name in names:
        path = Path(repo) / name
        source = path.read_text(encoding="utf-8")
        updated = cargo_paths(source)
        if updated != source:
            path.write_text(updated, encoding="utf-8")


def cargo_paths(source):
    return source.replace("../../../splash/crates/", "../../../octoscript/crates/")
