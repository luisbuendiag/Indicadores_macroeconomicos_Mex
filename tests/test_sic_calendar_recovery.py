"""El calendario de la segunda consulta puede corroborar una ficha SIC rezagada."""
import json
from pathlib import Path

import pytest

import build_cycle_notes as notes


URL = 'https://www.inegi.org.mx/contenidos/saladeprensa/boletines/2026/sic_cya/sic2026_11.pdf'
IND = {'last_observation': 'Ago 26', 'fecha_publicacion_oficial': '4 de diciembre de 2025'}
ROW = {'clave': 'SIC', 'institucion': 'INEGI', 'frecuencia': 'Mensual',
       'usar_para_frescura': True, 'estatus': 'publicado',
       'periodo_referencia': 'Agosto de 2026', 'fecha_iso': '2026-11-04', 'url_boletin': URL}


def calendar(root: Path, rows):
    path = root/'data/calendario_publicaciones.json'
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps({'items': rows}))


def test_corrobora_ficha_antes_del_periodo_solo_con_calendario_mensual_exacto(tmp_path):
    calendar(tmp_path, [ROW, ROW])
    assert notes.bulletin_candidate(tmp_path, IND, 'SIC') == ('2026-11-04', URL, True)
    current = {**IND, 'fecha_publicacion_oficial': '2026-11-03'}
    assert notes.bulletin_candidate(tmp_path, current, 'SIC') == ('2026-11-03', URL, False)


@pytest.mark.parametrize('changes', [
    {'clave': 'IMOAM'}, {'institucion': 'Banco de México'}, {'frecuencia': 'Trimestral'},
    {'usar_para_frescura': False}, {'estatus': 'próximo'},
    {'periodo_referencia': 'Septiembre de 2026'}, {'periodo_referencia': 'Tercer trimestre de 2026'},
    {'fecha_iso': '2026-10-31'}, {'fecha_iso': '2099-09-04'}, {'fecha_iso': 'incorrecta'},
    {'url_boletin': URL.replace('sic2026_11', 'sic2026_12')},
    {'url_boletin': URL.replace('www.inegi.org.mx', 'example.com')}, {'url_boletin': URL + '?x=1'},
])
def test_rechaza_calendario_sin_corroboracion(tmp_path, changes):
    calendar(tmp_path, [{**ROW, **changes}])
    with pytest.raises(ValueError, match='no es posterior'):
        notes.bulletin_candidate(tmp_path, IND, 'SIC')


def test_tolera_formato_defectuoso_y_no_elige_entre_dos_fechas(tmp_path):
    calendar(tmp_path, [ROW, {**ROW, 'fecha_iso': '2026-11-05'}])
    with pytest.raises(ValueError, match='no es posterior'):
        notes.bulletin_candidate(tmp_path, IND, 'SIC')
    calendar(tmp_path, [])
    (tmp_path/'data/calendario_publicaciones.json').write_text('invalid json')
    with pytest.raises(ValueError, match='no es posterior'):
        notes.bulletin_candidate(tmp_path, IND, 'SIC')


def test_corrige_ficha_solo_si_valida_y_no_cambia_calendario_ni_observaciones(monkeypatch, tmp_path):
    calendar(tmp_path, [ROW])
    path = tmp_path/'data/indicadores.json'
    source = {**IND, 'url_boletin_oficial': URL, 'observations':[{'period': 'Ago 26', 'values': [100.1741]}]}
    path.write_text(json.dumps({'indicators': {'SIC': source}}))
    before = path.read_bytes()
    facts = {'period': 'Ago 26', 'publication_date': '2026-11-04', 'bulletin': '679/26'}
    def run():
        return notes.publish(tmp_path, None, facts, 'fp', URL, {}, {}, URL,
                             '4 de diciembre de 2025', True)

    calendar(tmp_path, [{**ROW, 'fecha_iso': '2026-11-05'}])
    with pytest.raises(ValueError, match='cambió'):
        run()
    assert path.read_bytes() == before

    calendar(tmp_path, [ROW])
    monkeypatch.setattr(notes.A, 'publish', lambda *_: (_ for _ in ()).throw(ValueError('rollback')))
    with pytest.raises(ValueError, match='rollback'):
        run()
    assert path.read_bytes() == before

    monkeypatch.setattr(notes.A, 'publish', lambda *_: {'status': 'vigente'})
    assert run()['status'] == 'vigente'
    saved = json.loads(path.read_text())['indicators']['SIC']
    assert saved['fecha_publicacion_oficial'] == saved['fecha_ultima_publicacion'] == '4 de noviembre de 2026'
    assert saved['periodo_referencia_oficial'] == 'Agosto de 2026'
    assert saved['observations'] == source['observations']
