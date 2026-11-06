"""Contratos del Excel histórico; fechas y valores se leen del snapshot vigente."""
from copy import deepcopy
from datetime import date, datetime
import json
from pathlib import Path
import re
import zipfile
import xml.etree.ElementTree as ET

import openpyxl
import pytest
import build_excel as X
from excel_layout import EXCLUDED, SHEETS

ROOT=Path(__file__).resolve().parents[1]

@pytest.fixture(scope='module')
def payload():return json.loads((ROOT/'data/indicadores.json').read_text())

@pytest.mark.parametrize('key',list(SHEETS))
def test_all_source_values_preserved_in_cells(payload,key):
    ind=payload['indicators'][key];m=X.build_workbook([ind])
    excluded=EXCLUDED.get(key,{})
    for o in ind['observations']:
        d=X._period_date(o['period'])
        for column,value in enumerate(o['values']):
            if value is None or column in excluded:continue
            assert (key,column,d) in m.coords,(key,column,d)
            sheet,address=m.coords[key,column,d]
            actual=m.wb[sheet][address].value
            if isinstance(value,str) and re.fullmatch(r'\d{4}-\d{2}-\d{2}',value):assert actual==date.fromisoformat(value)
            else:assert actual==value,(key,column,d,value,actual)
    for ws in m.wb:
        assert ws.freeze_panes is None
        assert not ws.sheet_view.showGridLines
        for row in ws:
            for c in row:
                if c.value is not None:assert c.font.name=='Noto Sans'
    assert sum(len(ws._charts) for ws in m.wb)>0

@pytest.mark.parametrize('key',['TIPOCAMBIO','TASA','RESERVAS'])
def test_daily_weekly_dates_are_typed_and_exact(payload,key):
    m=X.build_workbook([payload['indicators'][key]])
    for (k,i,d),(sheet,address) in m.coords.items():
        if k!=key:continue
        row=m.wb[sheet][address].row
        assert m.wb[sheet].cell(row,1).value==d
        assert m.wb[sheet].cell(row,1).number_format=='yyyy-mm-dd'


def test_quarterly_population_has_only_quarterly_rows(payload):
    ind=payload['indicators']['DESOCUP'];m=X.build_workbook([ind]);ws=m.wb['Población ocupada']
    rows=[ws.cell(r,1) for r in range(1,ws.max_row+1) if isinstance(ws.cell(r,1).value,date)]
    expected=[o for o in ind['observations'] if o['values'][5] is not None]
    assert len(rows)==len(expected)
    assert all('T ' in c.number_format for c in rows)
    assert all(c.value.month in (1,4,7,10) for c in rows)


def test_no_inferred_definitive_and_no_repeated_bulletin(payload):
    for key in ['IMOAM','INPC','BCMM']:
        m=X.build_workbook([payload['indicators'][key]])
        for ws in m.wb:
            values=[c.value for row in ws for c in row]
            assert 'Definitivo' not in values
            assert 'Fecha de publicación' not in values
            assert 'URL del boletín' not in values
    m=X.build_workbook([payload['indicators']['PIB']])
    assert any(c.value=='Preliminar' for ws in m.wb for row in ws for c in row)


def test_original_imai_history_restored_and_rates_not_overwritten(payload):
    ind=payload['indicators']['IMAI'];m=X.build_workbook([ind])
    assert m.wb.sheetnames==['Niveles','Variaciones','Originales']
    first=X._period_date(ind['observations'][0]['period'])
    assert ('IMAI',3,first) in m.coords
    assert any(c.data_type=='f' for ws in m.wb for row in ws for c in row)
    for o in ind['observations']:
        for col in [1,2]:
            if o['values'][col] is not None:
                s,c=m.coords['IMAI',col,X._period_date(o['period'])]
                assert m.wb[s][c].value==o['values'][col]


def test_never_calculates_adjusted_igae_from_original_index(payload):
    ind=payload['indicators']['IGAE'];m=X.build_workbook([ind])
    for (key,index,d),(sheet,address) in m.coords.items():
        if key=='IGAE' and index==1:assert m.wb[sheet][address].data_type!='f'


def test_formula_guards_missing_zero_and_changed_source_cells():
    obs=[{'period':f'{month} 25','values':[v,None,None]} for month,v in [('Ene',100),('Feb',110),('Mar',None),('Abr',120),('May',0),('Jun',125)]]
    ind={'key':'EMOE','nombre':'Confianza','frecuencia':'Mensual','columns':[{'index':0,'label':'Nivel','fmt':'idx'},{'index':1,'label':'Cambio mensual','fmt':'emoe'},{'index':2,'label':'Cambio anual','fmt':'emoe'}], 'observations':obs}
    m=X.build_workbook([ind]);s,c=m.coords['EMOE',1,date(2025,2,1)]
    formula=m.wb[s][c].value
    assert formula.startswith('=IF(COUNT(') and '-\'' in formula
    # La referencia es a la celda de nivel editable, no a un número incrustado.
    ls,lc=m.coords['EMOE',0,date(2025,2,1)]
    assert f"'{ls}'!{lc}" in formula
    assert ('EMOE',1,date(2025,4,1)) in m.coords
    missing_sheet,missing_cell=m.coords['EMOE',1,date(2025,4,1)]
    assert m.wb[missing_sheet][missing_cell].value is None


def test_chart_refs_and_same_period_lengths(payload,tmp_path):
    m=X.build_workbook([payload['indicators']['IMAI']]);p=tmp_path/'IMAI.xlsx';m.wb.save(p)
    X.validate_workbook(p)
    ns={'c':'http://schemas.openxmlformats.org/drawingml/2006/chart'}
    with zipfile.ZipFile(p) as z:
        for name in z.namelist():
            if name.startswith('xl/charts/chart') and name.endswith('.xml'):
                xml=ET.fromstring(z.read(name))
                axes=xml.findall('.//c:dateAx',ns)+xml.findall('.//c:valAx',ns)
                ids={a.find('c:axId',ns).get('val') for a in axes}
                assert all(a.find('c:crossAx',ns).get('val') in ids for a in axes)
                for s in xml.findall('.//c:ser',ns):
                    values=s.find('c:val/c:numRef/c:f',ns).text
                    cats=s.find('c:cat/c:numRef/c:f',ns).text
                    a=[int(x) for x in re.findall(r'\$(\d+)',values)]
                    b=[int(x) for x in re.findall(r'\$(\d+)',cats)]
                    assert a[-1]-a[0]==b[-1]-b[0]
                    assert s.find('c:val/c:numLit',ns) is None


def test_master_and_individual_have_identical_sources_and_formulas(payload):
    inds=[payload['indicators'][k] for k in payload['order']]
    master=X.build_workbook(inds,True)
    assert len(master.wb.sheetnames)==22
    assert not any(name in master.wb.sheetnames for name in ['Resumen','Síntesis de coyuntura','Metodología y fuentes','Control de actualizaciones'])
    for ind in inds:
        one=X.build_workbook([ind])
        for key,coord in one.coords.items():
            a,b=coord;other_a,other_b=master.coords[key]
            v=one.wb[a][b].value;other=master.wb[other_a][other_b].value
            if one.wb[a][b].data_type=='f':assert master.wb[other_a][other_b].data_type=='f'
            else:assert v==other,(key,v,other)


def test_new_period_and_revised_value_extend_chart_and_table(payload):
    ind=deepcopy(payload['indicators']['PIB'])
    old=X.build_workbook([ind]);last=ind['observations'][-1];d=X._period_date(last['period'])
    next_d=X._shift(d,-3);label=f'{(next_d.month-1)//3+1}T-{str(next_d.year)[-2:]} P'
    ind['observations'][0]['values'][0]=.0123
    ind['observations'].append({'period':label,'values':[.01,.02,.03,.04]})
    new=X.build_workbook([ind])
    s,c=new.coords['PIB',0,next_d];assert new.wb[s][c].value==.01
    first=X._period_date(ind['observations'][0]['period']);s,c=new.coords['PIB',0,first]
    assert new.wb[s][c].value==.0123
    old_ref=old.wb.worksheets[0]._charts[0].series[0].val.numRef.f
    new_ref=new.wb.worksheets[0]._charts[0].series[0].val.numRef.f
    assert old_ref!=new_ref


def test_failed_generation_keeps_every_published_workbook(payload,tmp_path,monkeypatch):
    master=tmp_path/X.OUT_XLSX.name;master.write_bytes(b'previous-master')
    one=tmp_path/'indicadores/PIB/PIB_datos.xlsx';one.parent.mkdir(parents=True);one.write_bytes(b'previous-pib')
    original=X.validate_workbook;calls=0
    def fail_later(path):
        nonlocal calls
        calls+=1
        if calls==2:raise ValueError('invalid workbook')
        return original(path)
    monkeypatch.setattr(X,'validate_workbook',fail_later)
    with pytest.raises(ValueError):X.generate(payload,tmp_path)
    assert master.read_bytes()==b'previous-master'
    assert one.read_bytes()==b'previous-pib'


def test_no_history_or_unreviewed_base_cannot_replace_files(payload,tmp_path):
    broken=deepcopy(payload)
    broken['indicators']['IMAI']['observations']=[]
    with pytest.raises(ValueError,match='Sin historia'):X.generate(broken,tmp_path)
    ind=deepcopy(payload['indicators']['IMAI']);ind['unidad']='Índice base 2023=100'
    with pytest.raises(ValueError,match='base'):X.build_workbook([ind])


def test_policy_rate_keeps_two_decimal_places(payload):
    m=X.build_workbook([payload['indicators']['TASA']])
    for (key,index,day),(sheet,address) in m.coords.items():
        if key=='TASA':assert m.wb[sheet][address].number_format=='0.00"%"'
