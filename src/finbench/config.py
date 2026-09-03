"""Config loading. Real environment variables beat .env; .env beats nothing.

That precedence matters: CI injects secrets as real env vars, and a .env file
left on disk must never silently override them.
"""
from __future__ import annotations

import functools
import hashlib
import os
import pathlib

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[2]
CONFIG_DIR = ROOT / "config"
DATA_DIR = ROOT / "data"


def load_dotenv(path: pathlib.Path | None = None) -> None:
    path = pathlib.Path(path) if path else ROOT / ".env"
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


@functools.cache
def _yaml(name: str) -> dict:
    return yaml.safe_load((CONFIG_DIR / name).read_text())


def companies() -> dict:
    return _yaml("companies.yaml")


def grading() -> dict:
    return _yaml("grading.yaml")


def models() -> dict:
    return _yaml("models.yaml")


def config_hash(directory: pathlib.Path | None = None) -> str:
    """Hash every config file, so a run can prove which config produced it."""
    directory = pathlib.Path(directory) if directory else CONFIG_DIR
    digest = hashlib.sha256()
    for path in sorted(directory.glob("*.yaml")):
        digest.update(path.name.encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()[:16]
