"""Pruebas del hueco observado: ficha 739/26 publicada y calendario parcial."""
from datetime import date
import json

import pytest

import build_calendar as b

PUB = date(2026, 11, 26)
PDF = "https://www.inegi.org.mx/contenidos/saladeprensa/boletines/2026/imoam/imoam2026_11.pdf"
GENERIC = "https://www.inegi.org.mx/app/saladeprensa/calendario/"
TITLE = "Indicador Mensual Oportuno de la Actividad Manufacturera"
SNAPSHOT = {"key":"IMOAM", "last_observation":"Oct 26", "periodo_boletin":"Oct 26",
            "fecha_publicacion":"26 de noviembre de 2026", "fecha_publicacion_oficial":"28 de octubre de 2026",
            "numero_boletin":"739/26", "boletin_validado":True, "tipo_documento":"PDF",
            "fuente":{"nombre":"INEGI"}, "url_boletin_oficial":PDF}
SEP = {"indicator":"IMOAM", "institution":"INEGI", "frequency":"Mensual",
       "product":TITLE, "period":"Sep 26", "date":date(2026,10,28), "url":GENERIC}

def test_calendario_parcial_usa_boletin_validado_sin_adelantar_otro_periodo(monkeypatch,tmp_path):
    monkeypatch.setattr(b,"DATA_DIR",tmp_path)
    monkeypatch.setattr(b,"NEW_OUT",tmp_path/"calendario.json")
    monkeypatch.setattr(b,"LEGACY_OUT",tmp_path/"calendario_publicaciones.json")
    monkeypatch.setattr(b,"_build_events",lambda *_: ([dict(SEP)],[],{}))
    edition = b.build(as_of=PUB, offline=True, indicators={"IMOAM":SNAPSHOT})
    sep, oct_ = edition["items"]
    assert sep["periodo_referencia"]=="Sep 26" and oct_["periodo_referencia"]=="Oct 26"
    assert oct_["fecha_iso"]==PUB.isoformat() and oct_["url_boletin"]==PDF and oct_["publication_confirmed"] is True
    assert len(edition["items"])==2
    recent = json.loads(b.NEW_OUT.read_text())["recent"][0]
    assert recent["reference_period"]=="Oct 26" and recent["publication_evidence_url"]==PDF
    assert b.build(as_of=PUB,offline=True,indicators={"IMOAM":SNAPSHOT})["items"]==edition["items"]

def test_conserva_evento_oficial_existente_no_duplica():
    existing={**SEP,"date":PUB,"period":"Octubre de 2026"}
    found=[dict(SEP),existing]
    b._supplement_current_imoam(found,PUB,{"IMOAM":SNAPSHOT})
    assert found==[SEP,existing]

@pytest.mark.parametrize(("as_of","invalid"),[
    (date(2026,11,25),{}),
    (PUB,{"boletin_validado":False}),
    (PUB,{"fuente":{"nombre":"otro"}}),
    (PUB,{"tipo_documento":"HTML"}),
    (PUB,{"numero_boletin":"739/25"}),
    (PUB,{"periodo_boletin":"4T-26"}),
    (PUB,{"last_observation":"Sep 26"}),
    (PUB,{"fecha_publicacion":"28 de octubre de 2026"}),
    (PUB,{"fecha_publicacion":"fecha no verificable"}),
    (PUB,{"url_boletin_oficial":GENERIC}),
    (PUB,{"url_boletin_oficial":PDF.replace("imoam2026_11","imoam2026_10")}),
    (PUB,{"url_boletin_oficial":PDF+"?other=1"}),
])
def test_no_crea_evento_si_fecha_pdf_o_periodo_no_corresponden(as_of,invalid):
    found=[dict(SEP)]
    b._supplement_current_imoam(found,as_of,{"IMOAM":{**SNAPSHOT,**invalid}})
    assert found==[SEP]
