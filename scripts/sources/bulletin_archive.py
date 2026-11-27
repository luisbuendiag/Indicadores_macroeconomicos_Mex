"""Archivo temporal de lecturas históricas de boletines oficiales."""

from datetime import date, timedelta
import hashlib
import json
from pathlib import Path
from tempfile import NamedTemporaryFile

HISTORICAL_AGE = timedelta(days=180)
MAX_AGE = timedelta(days=7)
KINDS = ("IOAE", "EOPIBT")


def digest(content):
    return hashlib.sha256(content).hexdigest()


def encode(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"),
                      allow_nan=False).encode()


class BulletinArchive:
    def __init__(self, root, kind, signature, *, today=None):
        if kind not in KINDS:
            raise ValueError("Indicador sin archivo histórico habilitado")
        self.path = Path(root) / digest(encode([kind, signature]))
        self.today = today or date.today()

    def _historical(self, published):
        return self.today - date(*published) >= HISTORICAL_AGE

    def records(self):
        entries = {}
        for path in self.path.glob("*.json"):
            try:
                wrapped = json.loads(path.read_bytes())
                record = wrapped["record"]
                if wrapped["sha256"] != digest(encode(record)):
                    continue
                checked = date.fromisoformat(record["checked"])
                url = record["url"]
                if (
                    path.stem == digest(url.encode())
                    and timedelta() <= self.today - checked < MAX_AGE
                    and self._historical(record["published"])
                    and isinstance(record["parsed"], dict)
                    and record["parsed"]
                    and isinstance(record["text"], str)
                ):
                    entries[url] = record
            except (OSError, KeyError, TypeError, ValueError, AttributeError, OverflowError):
                continue
        return entries

    def store(self, url, pdf, text, published, parsed):
        try:
            if not parsed or not self._historical(published):
                return
        except (TypeError, ValueError, OverflowError):
            return
        record = {
            "url": url, "pdf_sha256": digest(pdf), "text": text, "published": list(published),
            "parsed": parsed, "checked": self.today.isoformat(),
        }
        temporary = None
        try:
            contents = encode({"record": record, "sha256": digest(encode(record))})
            self.path.mkdir(parents=True, exist_ok=True)
            with NamedTemporaryFile(dir=self.path, delete=False) as handle:
                temporary = Path(handle.name)
                handle.write(contents)
            temporary.replace(self.path / (digest(url.encode()) + ".json"))
        except (OSError, ValueError):
            pass  # Si el archivo local falla, el boletín consultado sigue vigente.
        finally:
            if temporary is not None and temporary.exists():
                try:
                    temporary.unlink()
                except OSError:
                    pass
