from contextlib import nullcontext
from datetime import datetime
from io import BytesIO
import json

import pytest

from sources import imoam


def test_archivo_abarca_17_meses_y_cada_periodo_apunta_a_su_boletin():
    archive = json.loads(imoam.HISTORY_FILE.read_text(encoding="utf-8"))["observaciones"]
    expected = [f"{i // 12:04d}-{i % 12 + 1:02d}" for i in range(2023 * 12 + 6, 2024 * 12 + 11)]
    assert list(archive) == expected
    rows = imoam._archived_rows()
    assert [r["value"] for r in rows["2023-07"]] == [105.2, 102.2, 108.4, 0.002, -0.027, 0.032]
    assert [r["value"] for r in rows["2024-06"]] == [106.0, 102.9, 109.1, -0.016, -0.044, 0.013]
    assert rows["2024-11"][0]["pub_date"] == "2024-12-20"
    for ym, entry in archive.items():
        assert ym < entry["publicado"][:7]
        assert entry["boletin"].startswith("https://www.inegi.org.mx/contenidos/saladeprensa/boletines/")
        assert entry["boletin"].endswith(".pdf")
        idx, idx_low, idx_high, annual, annual_low, annual_high = entry["values"]
        assert 0 < idx_low <= idx <= idx_high
        assert -1 < annual_low <= annual <= annual_high < 1


@pytest.fixture
def today(monkeypatch):
    class November2026(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 11, 23, tzinfo=tz)

    monkeypatch.setattr(imoam, "datetime", November2026)
    monkeypatch.setattr(imoam.B, "pdfplumber", object())
    monkeypatch.setattr(imoam, "load_release_calendar", lambda: {"items": []})


def test_consulta_agrega_archivo_y_conserva_metadatos_del_boletin_vigente(monkeypatch, today):
    url = "https://www.inegi.org.mx/contenidos/saladeprensa/boletines/2026/imoam/imoam2026_11.pdf"
    latest = [
        {"ym": "2026-10", "period": "Oct 26", "pub_date": "2026-11-23", "caracter": "estimado", "value": value}
        for value in (108.0, 105.0, 111.0, 0.019, -0.012, 0.05)
    ]

    def response(request, timeout):
        assert request.full_url == url
        return nullcontext(BytesIO(b"boletin de prueba"))

    monkeypatch.setattr(imoam.urllib.request, "urlopen", response)
    monkeypatch.setattr(imoam, "parse_pdf", lambda pdf: (latest, "", (2026, 11, 23)))
    result = imoam.fetch(max_bulletins=1)
    assert result.ok
    assert len(result.data["IMOAM"]) == 6
    for col, item in enumerate(result.data["IMOAM"]):
        rows = item["api_total"]
        assert len(rows) == 18
        assert rows[0]["ym"] == "2023-07"
        assert rows[-1] == latest[col]
        assert item["url_boletin_oficial"] == url
        assert item["periodo_boletin"] == "Oct 26"


def test_archivo_no_convierte_falla_de_red_en_consulta_vigente(monkeypatch, today):
    def unavailable(*args, **kwargs):
        raise OSError("fuente temporalmente fuera de línea")

    monkeypatch.setattr(imoam.urllib.request, "urlopen", unavailable)
    result = imoam.fetch(max_bulletins=1)
    assert not result.ok
    assert any("se conserva el último dato válido" in warning for warning in result.warnings)
