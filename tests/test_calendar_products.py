from datetime import date

import build_calendar as b


def test_trimestral_enoe_no_actualiza_ficha_mensual():
    ev = b._precise_event({'indicator': 'DESOCUP', 'period': 'Tercer trimestre de 2026', 'frequency': 'Mensual'})
    assert ev['frequency'] == 'Trimestral'
    assert not ev['usar_para_frescura']
    assert 'trimestrales' in ev['product']


def test_bcmm_sin_boletin_no_se_confunde_con_nota_mensual():
    ev = b._precise_event({'indicator': 'BCMM', 'comentario': 'No se elabora comunicado de prensa, boletín de indicador ni reporte de resultados.'})
    assert ev['product'] == 'BCMM · Difusión de datos sin boletín'
    assert not ev['usar_para_frescura']


def test_periodos_distintos_mismo_dia_se_preservan():
    cfg = {'inegi': {'indicators': {'DESOCUP': {'acronyms': ['ENOE']}}}}
    entries = [{'program': 'Encuesta (ENOE)', 'date': date(2026, 11, 25), 'period': period}
               for period in ['Tercer trimestre de 2026', 'Octubre de 2026']]
    mapped = b._map_inegi_events(entries, cfg, [])
    assert len(mapped) == 2
    assert len(b._dedup_events(mapped + mapped)) == 2


def test_runner_utc_does_not_publish_tomorrows_enoe_in_mexico(monkeypatch, tmp_path):
    import json
    from datetime import datetime, timezone

    class FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 11, 26, 2, 31, tzinfo=timezone.utc).astimezone(tz)

    monkeypatch.setattr(b, "datetime", FixedDatetime)
    monkeypatch.setattr(b, "DATA_DIR", tmp_path)
    monkeypatch.setattr(b, "NEW_OUT", tmp_path / "calendario.json")
    monkeypatch.setattr(b, "LEGACY_OUT", tmp_path / "calendario_publicaciones.json")
    (tmp_path / "indicadores.json").write_text(
        '{"indicators":{"DESOCUP":{"last_updated":"2026-11-26"}}}', encoding="utf-8"
    )
    event = {
        "indicator": "DESOCUP", "date": date(2026, 11, 26), "period": "Octubre de 2026",
        "url": "https://www.inegi.org.mx/app/saladeprensa/calendario/",
        "product": "ENOE · Indicadores mensuales de ocupación y empleo",
    }
    monkeypatch.setattr(b, "_build_events", lambda *args: ([event], [], {}))

    assert b.main(["--offline"]) == 0
    legacy = json.loads(b.LEGACY_OUT.read_text(encoding="utf-8"))
    modern = json.loads(b.NEW_OUT.read_text(encoding="utf-8"))
    assert legacy["as_of"] == modern["as_of"] == "2026-11-25"
    assert [r["estatus"] for r in legacy["items"]] == ["próximo"]
    assert [r["status"] for r in modern["events"]] == ["próximo"]
    assert b.build(as_of=date(2026, 11, 26), offline=True)["items"][0]["estatus"] == "publicado"

    import build_data
    monkeypatch.setattr(build_data.L, "DATA_DIR", tmp_path)
    monkeypatch.setattr(build_data.lib_kpicfg, "get_cfg", lambda *args: {})
    monkeypatch.setattr(build_data.lib_kpicfg, "build_cfg", lambda **_: None)
    monkeypatch.setattr(build_data.lib_metrics, "compute_all_metrics", lambda _: {})
    changes = build_data.apply_freshness_and_meta({"indicators": {}}, {"warnings": []}, offline=True)
    assert "calendario: regenerado con as_of=2026-11-25" in changes
    assert json.loads(b.LEGACY_OUT.read_text(encoding="utf-8"))["items"][0]["estatus"] == "próximo"
