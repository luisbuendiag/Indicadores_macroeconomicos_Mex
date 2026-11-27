from datetime import date

from sources import inegi_bulletin as source
from sources.bulletin_archive import BulletinArchive, digest

URL = "https://www.inegi.org.mx/contenidos/saladeprensa/boletines/2026/ioae/ioae2026_01.pdf"


def test_cache_expiry_revalidates_correction_at_same_official_url(tmp_path, monkeypatch):
    used = []
    current = {"pdf": b"original", "value": 1.0}
    monkeypatch.setattr(source, "_available_issues", lambda *a, **k: [(2026, 1, URL)])

    def fetch(url):
        used.append(url)
        return current["pdf"]

    monkeypatch.setattr(source, "_req", fetch)
    monkeypatch.setattr(source, "_pdf_text_first_page", lambda pdf: ("20 de enero de 2026", []))
    monkeypatch.setattr(source, "_parse_ioae", lambda *a: {
        "igae_anual": [{"period": "Dic 25", "ym": "2025-12", "value": current["value"]}],
    })

    def run(on):
        archive = BulletinArchive(tmp_path, "IOAE", "qa", today=on)
        result = source._fetch_kind("IOAE", 2020, archive=archive)
        return result[0]["api_total"][0]["value"], archive

    original, _ = run(date(2026, 11, 20))
    current.update(pdf=b"corregido", value=2.0)
    warm, _ = run(date(2026, 11, 26))
    revised, archive = run(date(2026, 11, 27))
    assert (original, warm, revised) == (1.0, 1.0, 2.0)
    assert used == [URL, URL]
    assert archive.records()[URL]["pdf_sha256"] == digest(b"corregido")


def test_recent_corrupt_and_incompatible_entries_return_to_network(tmp_path):
    now = date(2026, 11, 27)
    archive = BulletinArchive(tmp_path, "EOPIBT", "versión 1", today=now)
    archive.store(URL, b"PDF", "Texto", (2026, 10, 30), {"PIB": [1]})
    assert archive.records() == {}

    archive.store(URL, b"PDF", "Texto", (2026, 1, 30), {"PIB": [1]})
    wrong_signature = BulletinArchive(tmp_path, "EOPIBT", "versión 2", today=now)
    assert wrong_signature.records() == {}
    next(archive.path.glob("*.json")).write_text('{"record": {}, "sha256": "inválido"}')
    assert archive.records() == {}


def test_discovery_uses_validated_archive_and_checks_uncached_months(monkeypatch):
    urls = []
    sleeps = []
    monkeypatch.setattr(source.time, "sleep", sleeps.append)

    def check(url):
        urls.append(url)
        return True

    monkeypatch.setattr(source, "_head_ok", check)
    issues = source._available_issues("IOAE", 2026, 2026, months=(1, 2), cached_urls={URL})
    assert issues[-1] == (2026, 1, URL)
    assert len(urls) == len(sleeps) == 1
    assert urls[0].endswith("ioae2026_02.pdf")
