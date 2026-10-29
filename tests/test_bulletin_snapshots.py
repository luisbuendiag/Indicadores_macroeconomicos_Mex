"""Las revisiones BIE no deben borrar la edición utilizada por una nota."""
import copy
import pytest
from build_data import apply_inegi_total

@pytest.mark.parametrize('key,column,value', [('IMAI',4,.035),('IGAE',1,.006)])
def test_preserve_bulletin_edition_when_bie_revises(key,column,value):
    payload={'indicators':{key:{'columns':[{}]*9,'observations':[{'period':'Ago 26','values':[None]*9}]}}}
    source={'target_column':column,'api_total':[{'ym':'2026-08','value':value,'period':'Ago 26'}],
            'serie':'official-pdf','metodo':'INEGI boletín PDF','freq':8,
            'link':f'https://www.inegi.org.mx/contenidos/saladeprensa/boletines/2026/{key.lower()}/{key.lower()}2026_10.pdf',
            'fecha_publicacion':'2026-10-12'}
    apply_inegi_total(payload,key,source,None)
    snapshot=copy.deepcopy(payload['indicators'][key]['boletin_cifras'])
    revised={**source,'serie':'BIE','metodo':'INEGI BIE API','link':'https://www.inegi.org.mx/app/indicadores/',
             'api_total':[{'ym':'2026-08','value':value+.001,'period':'Ago 26'}]}
    apply_inegi_total(payload,key,revised,None)
    assert payload['indicators'][key]['boletin_cifras']==snapshot
    assert snapshot['2026-08'][str(column)]['value']==value
    assert payload['indicators'][key]['observations'][-1]['values'][column]==pytest.approx(value+.001)
