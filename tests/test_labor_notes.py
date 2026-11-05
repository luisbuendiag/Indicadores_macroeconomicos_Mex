import ast,json,shutil
from pathlib import Path
from types import SimpleNamespace
import pytest
from docx import Document
import notas_enoe as N
import notas_enoe_word as V
import build_labor_notes as R
ROOT=Path(__file__).resolve().parents[1]
class PDF:
    def __init__(self,pages):self.pages=[SimpleNamespace(extract_text=lambda p=p:p) for p in pages]
    def __enter__(self):return self
    def __exit__(self,*a):pass

def fixture(monkeypatch,key='DESOCUP'):
    pages=json.loads((ROOT/'tests/fixtures/enoe2026_10_pages.json').read_text())
    monkeypatch.setattr(N.pdfplumber,'open',lambda _:PDF(pages));return pages

def test_edition_series_population_and_published_precision(monkeypatch):
    fixture(monkeypatch);f=N.extract(b'fixture');assert f['period']=='Sep 26' and f['bulletin']=='634/26' and f['wage_base']=='2026'
    assert len(f['pages'])==15 and len(f['population'])==21 and len(f['sectors'])==29 and len(f['rates'])==11
    assert N.get(f,'pea')['current']==61735269 and N.get(f,'pea')['difference']==-358839
    assert N.get(f,'occupied')['difference']==-267333 and N.get(f,'unemployed')['difference']==-91506
    assert N.get(f,'occupied','women')['difference']==578137 and N.get(f,'occupied','men')['difference']==-845470
    assert N.rate(f,'unemployment')['current']==2.8 and N.rate(f,'unemployment')['difference']==-.1
    assert round(N.rate(f,'unemployment')['current']-N.rate(f,'unemployment')['previous'],1)==-.2
    assert N.rate(f,'unemployment',True)['current']==2.6 and N.rate(f,'unemployment',True)['mom']==-.1
    assert N.rate(f,'participation',True)['mom']==-.8
    assert N.rate(f,'informality')['current']==54.3 and N.rate(f,'informal_sector')['current']==29.4
    assert N.rate(f,'critical')['difference']==.2 and N.rate(f,'critical')['denominator']=='Población ocupada'
    assert f['urban'][3]['current']==3.0 and len(f['urban'])==len(f['adjusted'])==8
    assert next(r for r in f['sectors'] if r['id']=='manufacturing')['difference']==-70993

@pytest.mark.parametrize('case',['pages','edition','period','row','identity','denominator','method','cover','year','adjusted','wage','rate'])
def test_changed_source_rejected(monkeypatch,case):
    p=fixture(monkeypatch)
    if case=='pages':p.pop()
    elif case=='edition':p[10]=p[10].replace('634/26','999/26')
    elif case=='period':p[3]=p[3].replace('septiembre de 2025 y 2026','agosto de 2025 y 2026')
    elif case=='row':p[3]=p[3].replace('Ocupada2/ 60 244 382','Otro grupo2/ 60 244 382')
    elif case=='identity':p[3]=p[3].replace('61 735 269 -358 839','61 735 270 -358 838')
    elif case=='denominator':p[8]=p[8].replace('Porcentaje respecto a la PEA','Porcentaje respecto a otra población')
    elif case=='method':p[14]=p[14].replace('X-13ARIMA-SEATS','OTRO')
    elif case=='cover':p[0]=p[0].replace('58.5 % 2.8 %','58.5 % 9.8 %')
    elif case=='year':p[5]=p[5].replace('2026-2025','2026-2024')
    elif case=='adjusted':p[11]=p[11].replace('cifras desestacionalizadas','cifras originales')
    elif case=='wage':p[8]=p[8].replace('base enero de 2026','base desconocida')
    else:p[8]=p[8].replace('3.0 2.8 -0.1','3.0 200.0 -0.1')
    with pytest.raises(ValueError):N.extract(b'fixture')

@pytest.mark.parametrize('text,expected',[('62 094 108 61 735 269 -358 839',[62094108,61735269,-358839]),('0 93 93',[0,93,93])])
def test_thousands_groups_have_unique_arithmetic_partition(text,expected):assert N.integers(text)==expected

def test_bad_arithmetic_not_silently_parsed():
    with pytest.raises(ValueError):N.integers('62 094 108 61 735 269 -358 830')

@pytest.mark.parametrize('key',['DESOCUP'])
def test_word_tables_all_cotejadas_including_hero(monkeypatch,key):
    fixture(monkeypatch,key);f=N.extract(b'fixture',key);d=Document()
    for data in V.tables(f):
        t=d.add_table(rows=0,cols=len(data[0]))
        for row in data:
            for c,v in zip(t.add_row().cells,row):c.text=v
    candidate=SimpleNamespace(tables=d.tables,inline_shapes=[1,2]);V.validate(f,candidate)
    candidate.tables[0].rows[1].cells[0].text='Índice 9999'
    with pytest.raises(ValueError):V.validate(f,candidate)

@pytest.mark.parametrize('key',['DESOCUP'])
def test_strict_source_allowlist(key):
    directory,name=N.PRODUCTS[key];url=f'https://www.inegi.org.mx/contenidos/saladeprensa/boletines/2026/{directory}/{name}2026_10.pdf'
    assert R.allowed(url,key)
    for bad in [url+'?x=evil',url+'#x',url.replace('www.inegi.org.mx','example.com'),url.replace('https:','http:'),url.replace(name+'2026','otro2026')]:assert not R.allowed(bad,key)
    assert not R.allowed(url,'EMIM')

@pytest.mark.parametrize('case',['disabled','source_error','local_pdf','pause'])
def test_publication_preserves_previous_word(monkeypatch,tmp_path,case):
    for name in ['data/indicadores.json','data/notas/estado.json','config/notas_automaticas.json']:
        p=tmp_path/name;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,p)
    dest=tmp_path/'downloads/indicadores/DESOCUP/nota/DESOCUP_nota.docx';dest.parent.mkdir(parents=True);dest.write_bytes(b'previous-word')
    cfg=json.loads((tmp_path/'config/notas_automaticas.json').read_text())
    if case=='disabled':
        cfg['enabled']=False;(tmp_path/'config/notas_automaticas.json').write_text(json.dumps(cfg))
        monkeypatch.setattr(R,'download',lambda *a:pytest.fail('No descargar cuando está pausado'))
        assert R.run('DESOCUP',tmp_path,True)['status']=='deshabilitada'
    elif case=='local_pdf':assert R.run('DESOCUP',tmp_path,True,Path('/tmp/local.pdf'))['status']=='error'
    elif case=='source_error':
        monkeypatch.setattr(R,'download',lambda *a:(_ for _ in ()).throw(ValueError('Fuente incorrecta')))
        assert R.run('DESOCUP',tmp_path,True)['status']=='error'
    else:
        cfg['auto_publish']=False;(tmp_path/'config/notas_automaticas.json').write_text(json.dumps(cfg))
        fixture(monkeypatch,'DESOCUP');monkeypatch.setattr(R,'download',lambda *a:b'fixture')
        template=tmp_path/cfg['template'];template.parent.mkdir(parents=True);shutil.copyfile(ROOT/cfg['template'],template)
        for name in ['build_labor_notes.py','notas_enoe.py','notas_enoe_word.py','notas_layout.py','notas_word.py','build_auto_notes.py']:
            p=tmp_path/'scripts'/name;p.parent.mkdir(exist_ok=True);shutil.copyfile(ROOT/'scripts'/name,p)
        monkeypatch.setattr(R.V,'build',lambda *a:shutil.copyfile(template,a[-1]))
        monkeypatch.setattr(R.W,'render',lambda *a:(None,[1,2]));monkeypatch.setattr(R.V,'validate',lambda *a:None)
        monkeypatch.setattr(R.A,'publish',lambda *a:pytest.fail('Publicación deshabilitada'))
        assert R.run('DESOCUP',tmp_path,True)['status']=='validada_sin_publicar'
    assert dest.read_bytes()==b'previous-word'

def test_workflow_python_311_compatibility():
    for name in ['build_labor_notes.py','notas_enoe.py','notas_enoe_word.py','notas_layout.py']:
        ast.parse((ROOT/'scripts'/name).read_text(),feature_version=(3,11))
