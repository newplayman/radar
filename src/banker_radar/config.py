from __future__ import annotations

from pathlib import Path

try:
    import yaml
except Exception:  # pragma: no cover
    yaml = None


def load_config(path: str | Path = "configs/radar.yaml") -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    text = p.read_text(encoding="utf-8")
    if yaml is None:
        return {}
    return yaml.safe_load(text) or {}
