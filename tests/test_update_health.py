import json
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from io import BytesIO
import pytest
from build_update_health import build
from sources.base import http_get_json


def files(tmp_path, log, notes=None, rows=None):
    (tmp_path / 'data/notas').mkdir(parents=True)
    for name, data in [('update_log.json', log), ('manifest.json', {'indicadores': rows or []}),
                       ('notas/estado.json', notes or {})]:
        (tmp_path / 'data' / name).write_text(json.dumps(data))


def test_health_does_not_present_offline_or_failed_validation_as_a_fresh_query(tmp_path):
    files(tmp_path, {'mode': 'offline', 'network_calls': False, 'finished_at': '2026-11-09T14:00:00Z'})
    assert build(tmp_path)['data_checked_at'] is None
    assert build(tmp_path)['data_error']


def test_all_network_requests_failed_does_not_count_as_successful_query(tmp_path):
    files(tmp_path, {'mode':'online','network_calls':True,'result':'OK',
                     'consultas':[], 'finished_at':'2026-11-11T14:17:00Z'})
    assert build(tmp_path)['data_checked_at'] is None
    assert build(tmp_path)['data_error']


def test_pending_word_is_independent_of_current_data_and_manual_ied(tmp_path):
    files(tmp_path, {'mode': 'online', 'network_calls': True, 'critical': [], 'result': 'OK', 'consultas': [{'indicador': 'INPC'}], 'finished_at': '2026-11-09T14:00:00Z'},
          {'INPC': {'status': 'error', 'target_period': 'Oct 26', 'published': {'periodo': 'Sep 26'}},
           'INPP': {'status': 'vigente', 'target_period': 'Oct 26', 'published': {'periodo': 'Oct 26'}}},
          [{'clave': 'IED', 'estado': 'ACTUALIZADO', 'usa_respaldo': True}, {'clave': 'IMAI', 'estado': 'ERROR DE FUENTE'}])
    health = build(tmp_path)
    assert health['data_checked_at'] == '2026-11-09T14:00:00Z'
    assert health['pending_notes'] == ['INPC']
    assert health['pending_data'] == ['IMAI']


def response(data):
    return BytesIO(data)


def test_transient_http_failure_retries_and_succeeds():
    with patch('sources.base.urllib.request.urlopen', side_effect=[HTTPError('https://example.test', 503, '', {}, None), response(b'{"ok": true}')]) as request, patch('sources.base.time.sleep') as sleep:
        assert http_get_json('https://example.test') == {'ok': True}
        assert request.call_count == 2
        sleep.assert_called_once_with(2)


def test_missing_bulletin_is_not_retried():
    with patch('sources.base.urllib.request.urlopen', side_effect=HTTPError('https://example.test', 404, '', {}, None)) as request, patch('sources.base.time.sleep') as sleep:
        with pytest.raises(HTTPError): http_get_json('https://example.test')
        assert request.call_count == 1
        sleep.assert_not_called()


def test_transient_failure_is_bounded_and_malformed_json_is_not_retried():
    with patch('sources.base.urllib.request.urlopen', side_effect=URLError('timed out')) as request, patch('sources.base.time.sleep'):
        with pytest.raises(URLError): http_get_json('https://example.test')
        assert request.call_count == 3
    with patch('sources.base.urllib.request.urlopen', return_value=response(b'not json')) as request:
        with pytest.raises(json.JSONDecodeError): http_get_json('https://example.test')
        assert request.call_count == 1



def test_imss_state_warning_is_separate_from_release_health(tmp_path):
    from datetime import datetime

    files(tmp_path, {'mode': 'online', 'result': 'OK',
                     'consultas': [{'indicador': 'INPC'}], 'finished_at': '2026-11-15T15:00:00Z'})
    snapshot = tmp_path / 'data/estados.json'
    snapshot.write_text(json.dumps({'estado': 'oficial', 'indicadores': [
        {'clave': 'IMSS', 'periodo': '2026-09', 'estatus': 'oficial'}
    ]}))
    assert 'state_warnings' not in build(tmp_path, now=datetime.fromisoformat('2026-11-15T05:59:00Z'))
    warned = build(tmp_path, now=datetime.fromisoformat('2026-11-15T06:00:00Z'))
    assert warned['state_warnings'] == [{'indicator': 'IMSS', 'period': '2026-09', 'age_days': 46}]
    assert warned['query_coverage'] == 'valid'
    assert warned['pending_data'] == []
    snapshot.write_text('{"estado":"prueba","indicadores":[]}')
    assert 'state_warnings' not in build(tmp_path, now=datetime.fromisoformat('2026-11-24T12:00:00Z'))
