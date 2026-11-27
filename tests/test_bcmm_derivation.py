"""Regression for first-seen monthly balances in the institutional pipeline."""
import copy
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from build_data import compute_bcmm_metrics  # noqa: E402


def row(period, exports, imports):
    return {'period':period,'values':[exports,imports,None]}


def payload(rows):
    return {'indicators':{'BCMM':{'observations':rows}}}


def test_new_month_has_accumulated_exports_imports_and_balance_in_one_pass():
    datum=payload([row('Ene 26',7,4),row('Feb 26',14,16)])
    compute_bcmm_metrics(datum)
    january,february=datum['indicators']['BCMM']['observations']
    assert january['values'][2]==3 and january['values'][26:29]==[7,4,3]
    assert february['values'][2]==-2 and february['values'][26:29]==[21,20,1]
    before=copy.deepcopy(datum)
    compute_bcmm_metrics(datum)
    assert datum==before


def test_order_does_not_change_accumulation_or_annual_balance():
    january=row('Ene 26',7,4)
    february=row('Feb 26',14,16)
    previous=row('Ene 25',4,2)
    datum=payload([february,january,previous])
    compute_bcmm_metrics(datum)
    assert february['values'][26:29]==[21,20,1]
    assert january['values'][5]==pytest.approx(.5)


def test_missing_month_stays_missing_not_zero():
    march=row('Mar 26',7,4)
    datum=payload([row('Ene 26',10,8),march])
    compute_bcmm_metrics(datum)
    assert march['values'][2]==3
    assert march['values'][26:29]==[None,None,None]


def test_derived_totals_are_identical_in_json_csv_and_excel(tmp_path, monkeypatch):
    import csv
    from datetime import datetime

    from openpyxl import load_workbook

    import lib_data as data
    from build_excel import _build_bcmm_workbook

    datum=payload([row('Ene 26',7,4),row('Feb 26',14,16)])
    ind=datum['indicators']['BCMM']
    ind.update(key='BCMM',nombre='Balanza Comercial de Mercancías de México',
               frecuencia='Mensual',unidad='millones de dólares',last_observation='Feb 26')
    compute_bcmm_metrics(datum)
    expected=ind['observations'][-1]['values'][26:29]
    out=tmp_path/'indicadores.json'
    data.save_data(datum,out)
    assert data.load_data(out)['indicators']['BCMM']['observations'][-1]['values'][26:29]==expected
    monkeypatch.setattr(data,'DATA_DIR',tmp_path)
    data.write_csvs(datum)
    with (tmp_path/'csv/BCMM.csv').open() as f:
        output=list(csv.reader(f))[-1]
    assert output[0]=='Feb 26' and list(map(float,output[27:30]))==expected
    xlsx=tmp_path/'BCMM_datos.xlsx'
    _build_bcmm_workbook(ind,xlsx)
    bk=load_workbook(xlsx,read_only=True,data_only=True)
    try:
        rows=[r for r in bk['Comercio total'].iter_rows(values_only=True) if r[0]==datetime(2026,2,1)]
        assert any(list(r[1:4])==expected for r in rows)
    finally:
        bk.close()
