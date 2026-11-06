"""Historia sin corte artificial; la API oficial conserva fechas y valores."""
from sources import banxico

def test_requests_complete_official_series(monkeypatch):
    seen=[]
    monkeypatch.setenv('BANXICO_TOKEN','test-token')
    def response(url):
        seen.append(url)
        return {'bmx':{'series':[{'datos':[{'fecha':'12/11/1991','dato':'3.0735'},{'fecha':'05/11/2026','dato':'18.5'}]}]}}
    monkeypatch.setattr(banxico,'http_get_json',response)
    cfg={'banxico':{'TIPOCAMBIO':{'serie':'SF43718','frecuencia':'Diaria'}}}
    result=banxico.fetch(cfg)
    assert result.ok and '/SF43718/datos?' in seen[0]
    assert result.data['TIPOCAMBIO']['observations'][0]=={'period':'1991-11-12','values':[3.0735]}
    seen.clear();banxico.fetch(cfg,start='2020-01-01',end='2020-12-31')
    assert '/datos/2020-01-01/2020-12-31?' in seen[0]

def test_source_error_keeps_previous_data(monkeypatch):
    monkeypatch.delenv('BANXICO_TOKEN',raising=False)
    result=banxico.fetch({'banxico':{'TASA':{'serie':'SF61745'}}})
    assert not result.ok and not result.data
