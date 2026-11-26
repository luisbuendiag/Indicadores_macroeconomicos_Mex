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


def test_same_day_date_is_not_bulletin_confirmation(monkeypatch, tmp_path):
    import json

    today = date(2026, 11, 26)
    official = "https://www.inegi.org.mx/contenidos/saladeprensa/boletines/2026/iooe/IOE2026_11.pdf"
    generic = "https://www.inegi.org.mx/app/saladeprensa/calendario/"
    event = {"indicator": "DESOCUP", "date": today, "period": "Octubre de 2026", "url": generic}
    matching = {"boletin_validado": True, "periodo_boletin": "Oct 26",
                "url_boletin_oficial": official, "fecha_publicacion": "26 de noviembre de 2026"}
    monkeypatch.setattr(b, "DATA_DIR", tmp_path)
    monkeypatch.setattr(b, "NEW_OUT", tmp_path / "calendario.json")
    monkeypatch.setattr(b, "LEGACY_OUT", tmp_path / "calendario_publicaciones.json")
    monkeypatch.setattr(b, "_build_events", lambda *args: ([dict(event)], [], {}))

    for fields, confirmed in (
        ({}, False),
        ({"url_boletin_oficial": generic}, False),
        ({"url_boletin_oficial": "https://example.org/same.pdf"}, False),
        ({"periodo_boletin": "Sep 26"}, False),
        ({"periodo_boletin": "4T-26"}, False),
        ({"fecha_publicacion": "2026-11-25", "fecha_publicacion_oficial": "2026-11-26"}, False),
        ({"boletin_validado": False}, False),
        ({"fecha_publicacion": "2026-11-26"}, True),
    ):
        evidence = dict(matching, **fields) if fields else {}
        legacy = b.build(as_of=today, offline=True, indicators={"DESOCUP": evidence})
        modern = json.loads(b.NEW_OUT.read_text(encoding="utf-8"))
        # Mantener el estado operativo que consume frescura; la interfaz usa la prueba separada.
        assert legacy["items"][0]["estatus"] == "publicado"
        assert legacy["items"][0]["publication_confirmed"] is confirmed
        assert modern["events"][0]["publication_confirmed"] is confirmed
        assert bool(modern["recent"]) is confirmed
        assert modern["events"][0].get("publication_evidence_url") == (official if confirmed else None)


def test_pending_and_confirmed_publication_survive_later_build(monkeypatch, tmp_path):
    import json
    due = date(2026, 11, 26)
    old = date(2026, 9, 22)
    pdf = "https://www.inegi.org.mx/contenidos/saladeprensa/boletines/2026/iooe/IOE2026_11.pdf"
    live = dict(indicator="DESOCUP", date=due, period="Octubre de 2026", product="ENOE mensual", institution="INEGI")
    historical = dict(live, date=old, period="Agosto de 2026")
    monkeypatch.setattr(b, "DATA_DIR", tmp_path)
    monkeypatch.setattr(b, "NEW_OUT", tmp_path / "calendario.json")
    monkeypatch.setattr(b, "LEGACY_OUT", tmp_path / "calendario_publicaciones.json")
    monkeypatch.setattr(b, "_build_events", lambda *args: ([dict(live), dict(historical)], [], {}))

    def check(day, ind, confirmed):
        out = b.build(as_of=day, offline=True, indicators=ind)
        modern = json.loads(b.NEW_OUT.read_text())
        row = next(x for x in modern["events"] if x["publication_date"]==due.isoformat())
        legacy = next(x for x in out["items"] if x["fecha_iso"]==due.isoformat())
        assert row["publication_confirmed"] is confirmed
        assert legacy["estatus"] == "publicado" and legacy["publication_confirmed"] is confirmed
        assert any(x["publication_date"]==due.isoformat() for x in modern["recent"]) is confirmed
        assert "publication_confirmed" not in next(x for x in modern["events"] if x["publication_date"]==old.isoformat())
        return row

    check(date(2026,11,27), {}, False)  # La primera corrida puede saltarse el día 26.
    check(date(2026,11,29), {}, False)
    confirmed = {"DESOCUP":{"boletin_validado":True,"periodo_boletin":"Oct 26","url_boletin_oficial":pdf,"fecha_publicacion":"2026-11-29"}}
    assert check(date(2026,11,29),confirmed,True)["publication_evidence_url"]==pdf
    after = check(date(2026,12,1),{},True)
    assert after["publication_evidence_url"]==pdf
    assert after["publication_evidence_date"]=="2026-11-29"
    check(date(2026,11,27), {}, False)
