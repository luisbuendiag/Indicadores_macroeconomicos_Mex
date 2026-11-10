import test from 'node:test';import assert from 'node:assert/strict';import fs from 'node:fs';import vm from 'node:vm';
const src=fs.readFileSync(new URL('../assets/js/app.js',import.meta.url),'utf8');
const el=(tag,attrs={},...kids)=>({tag,attrs,kids,append(...more){this.kids.push(...more)}});
const build=vm.runInNewContext('('+src.slice(src.indexOf('function buildIedRanking('),src.indexOf('function productToolbar(')).trim()+')',{el});
const data=JSON.parse(fs.readFileSync(new URL('../data/ied_estatal.json',import.meta.url)));
function all(n,tag){return (n&&typeof n==='object'?[...(n.tag===tag?[n]:[]),...n.kids.flatMap(x=>all(x,tag))]:[])}
test('Ranking muestra diez entidades y el desplegable conserva las 32 y el corte estatal',()=>{const node=build(data),tables=all(node,'table');assert.equal(all(tables[0],'tbody')[0].kids.length,10);assert.equal(all(tables[1],'tbody')[0].kids.length,32);assert.ok(all(node,'h3')[0].kids[0].includes(data.ranking.label));assert.equal(all(node,'details').length,1);assert.equal(all(node,'a')[0].attrs.href,data.source_url);});
test('No muestra un universo incompleto; flechas con signo y comparación anual',()=>{assert.equal(build(null),null);assert.equal(build({ranking:{rows:[]}}),null);const node=build(data),cells=all(node,'td');for(let i=0;i<10;i++){const row=data.ranking.rows[i];const text=cells[i*5+4].kids[0];assert.equal(text,row.change>0?'↑ '+row.change:row.change<0?'↓ '+Math.abs(row.change):'—');}});
