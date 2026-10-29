"""Reusable fixture builders."""
from pathlib import Path


def populate(root, docs="connects to usb devices", source="pass", name="app.py"):
    root = Path(root)
    (root / "README.md").write_text(docs)
    if source is not None:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source)
    return root
