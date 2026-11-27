import test from 'node:test';
import assert from 'node:assert/strict';
import {fmtVal} from '../assets/js/format.js';

test('La tabla monetaria conserva centésimas sin cambiar otros porcentajes', () => {
  assert.equal(fmtVal(6.25,'pct-rate'),'6.25%');
  assert.equal(fmtVal(6.5,'pct-rate'),'6.50%');
  assert.equal(fmtVal(0,'pct-rate'),'0.00%');
  assert.equal(fmtVal(null,'pct-rate'),'—');
  assert.equal(fmtVal(3.84,'pct-raw'),'3.8%');
});
