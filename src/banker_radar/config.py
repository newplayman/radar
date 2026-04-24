from __future__ import annotations

import os
from pathlib import Path

try:
    import yaml
except Exception:  # pragma: no cover
    yaml = None


def load_dotenv_file(path: str | Path) -> int:
    """Load KEY=VALUE pairs from a .env file without overriding existing env vars."""
    p = Path(path)
    if not p.exists():
        return 0

    loaded = 0
    for raw_line in p.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key or key in os.environ:
            continue
        if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
            value = value[1:-1]
        os.environ[key] = value
        loaded += 1
    return loaded


def _load_project_env(config_path: Path) -> None:
    candidates = [Path.cwd() / ".env"]
    if config_path.parent.name == "configs":
        candidates.append(config_path.parent.parent / ".env")
    else:
        candidates.append(config_path.parent / ".env")

    seen: set[Path] = set()
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        load_dotenv_file(resolved)


def load_config(path: str | Path = "configs/radar.yaml") -> dict:
    p = Path(path)
    _load_project_env(p)
    if not p.exists():
        return {}
    text = p.read_text(encoding="utf-8")
    if yaml is None:
        return {}
    return yaml.safe_load(text) or {}
