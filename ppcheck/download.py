"""Download the two Bundesnetzagentur files into data/raw/ and record where they came from."""

from __future__ import annotations

import hashlib
import json
import urllib.request
from datetime import date
from pathlib import Path

BASE = (
    "https://www.bundesnetzagentur.de/DE/Fachthemen/ElektrizitaetundGas/Versorgungssicherheit/"
    "Erzeugungskapazitaeten/Kraftwerksliste/_DL/"
)
FILES = {
    "kraftwerksliste.csv": BASE + "Kraftwerksliste_CSV.csv?__blob=publicationFile",
    "zu_und_rueckbau.xlsx": BASE + "ZuUndRueckbau.xlsx?__blob=publicationFile",
}


def download(raw_dir: str | Path = "data/raw", force: bool = False) -> dict:
    raw = Path(raw_dir)
    raw.mkdir(parents=True, exist_ok=True)
    meta = {}
    for name, url in FILES.items():
        path = raw / name
        if force or not path.exists():
            req = urllib.request.Request(url, headers={"User-Agent": "ppcheck"})
            with urllib.request.urlopen(req, timeout=60) as r:
                path.write_bytes(r.read())
        meta[name] = {
            "url": url,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "downloaded": date.fromtimestamp(path.stat().st_mtime).isoformat(),
        }
    (raw / "SOURCE.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return meta
