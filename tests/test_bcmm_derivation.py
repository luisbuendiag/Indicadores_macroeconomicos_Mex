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
