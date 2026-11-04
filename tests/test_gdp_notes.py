import ast,json,shutil
from pathlib import Path
from types import SimpleNamespace
import pytest
from docx import Document
import notas_pib as N
import notas_pib_word as V
import build_gdp_notes as R
ROOT=Path(__file__).resolve().parents[1]
class PDF:
    def __init__(self,pages):self.pages=[SimpleNamespace(extract_text=lambda p=p:p) for p in pages]
    def __enter__(self):return self
    def __exit__(self,*a):pass

def fixture(monkeypatch,key):
    pages=json.loads((ROOT/f'tests/fixtures/{key.lower()}_gdp.json').read_text())
    monkeypatch.setattr(N.pdfplumber,'open',lambda _:PDF(pages));return pages

@pytest.mark.parametrize('key',['PIB','PIBSEC'])
def test_quarter_edition_and_series(monkeypatch,key):
    fixture(monkeypatch,key);f=N.extract(b'fixture',key)
    if key=='PIB':
        assert f['period']=='3T-26 P' and f['quarter']==3 and f['bulletin']=='673/26'
        assert (f['rows'][0]['mom'],f['rows'][0]['yoy'],f['rows'][0]['ytd'])==(.9,3.2,1.9)
        assert f['originals'][0]['ytd']==1.8 and len(f['originals'])==4
        assert f['rows'][1]['mom']==-.4
    else:
        assert f['period']=='2T-26' and f['quarter']==2 and f['bulletin']=='500/26'
        assert f['rows'][0]['yoy']==1.9 and f['originals'][0]['original']==2.1
        assert len(f['originals'])==24
        m=next(r for r in f['originals'] if r['id']=='31-33')
        assert m['original']==-.4 and m['ytd']==-1.1
        assert len(V.selected(f))==6 and V.selected(f)[0]['id']=='43'

@pytest.mark.parametrize('key',['PIB','PIBSEC'])
@pytest.mark.parametrize('case',['pages','edition','period','cover','method','series','columns','order','missing'])
def test_changed_source_rejected(monkeypatch,key,case):
    pages=fixture(monkeypatch,key);i=2 if key=='PIB' else 3
    if case=='pages':pages.pop()
    elif case=='edition':pages[1]=pages[1].replace('BOLETÍN DE INDICADOR','OTRO DOCUMENTO').replace('673/26','999/26').replace('500/26','999/26')
    elif case=='period':pages[i]=pages[i].replace('al tercer trimestre','al cuarto trimestre').replace('al segundo trimestre','al cuarto trimestre')
    elif case=='cover':pages[0]=pages[0].replace('▲ 0.9 %','▲ 9.9 %').replace('▲ 1.4 %','▲ 9.9 %')
    elif case=='method':pages[-1]=pages[-1].replace('X-13ARIMA-SEATS','OTRO')
    elif case=='series':pages[i]=pages[i].replace('Cifras preliminares','Cifras definitivas')
    elif case=='columns':pages[1]=pages[1].replace('9 meses','8 meses').replace('6 meses','5 meses')
    elif case=='order':pages[i]=pages[i].replace('3.er 4.o','4.o 3.er').replace('2.° 3.er','3.er 2.°')
    else:pages[i]=pages[i].replace('Actividades terciarias','Otro agregado')
    with pytest.raises(ValueError):N.extract(b'fixture',key)

def test_primary_duplicate_checked(monkeypatch):
    pages=fixture(monkeypatch,'PIBSEC')
    start=pages[3].index('11 Agricultura');end=pages[3].index('Actividades secundarias',start)
    pages[3]=pages[3][:start]+pages[3][start:end].replace('4.8 2.1','9.8 2.1')+pages[3][end:]
    with pytest.raises(ValueError):N.extract(b'fixture','PIBSEC')

@pytest.mark.parametrize('key',['PIB','PIBSEC'])
def test_word_tables_all_cotejadas_including_hero(monkeypatch,key):
    fixture(monkeypatch,key);f=N.extract(b'fixture',key);d=Document()
    for data in V.tables(f):
        t=d.add_table(rows=0,cols=len(data[0]))
        for row in data:
            for c,v in zip(t.add_row().cells,row):c.text=v
    candidate=SimpleNamespace(tables=d.tables,inline_shapes=[1,2]);V.validate(f,candidate)
    candidate.tables[0].rows[1].cells[0].text='Índice 9999'
    with pytest.raises(ValueError):V.validate(f,candidate)

@pytest.mark.parametrize('key',['PIB','PIBSEC'])
def test_strict_source_allowlist(key):
    directory,name=N.PRODUCTS[key];url=f'https://www.inegi.org.mx/contenidos/saladeprensa/boletines/2026/{directory}/{name}2026_10.pdf'
    assert R.allowed(url,key)
    for bad in [url+'?x=evil',url+'#x',url.replace('www.inegi.org.mx','example.com'),url.replace('https:','http:'),url.replace(name+'2026','otro2026')]:assert not R.allowed(bad,key)
    assert not R.allowed(url,'EMIM')

@pytest.mark.parametrize('case',['disabled','source_error','local_pdf','pause'])
def test_publication_preserves_previous_word(monkeypatch,tmp_path,case):
    for name in ['data/indicadores.json','data/notas/estado.json','config/notas_automaticas.json']:
        p=tmp_path/name;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,p)
    dest=tmp_path/'downloads/indicadores/PIB/nota/PIB_nota.docx';dest.parent.mkdir(parents=True);dest.write_bytes(b'previous-word')
    cfg=json.loads((tmp_path/'config/notas_automaticas.json').read_text())
    if case=='disabled':
        cfg['enabled']=False;(tmp_path/'config/notas_automaticas.json').write_text(json.dumps(cfg))
        monkeypatch.setattr(R,'download',lambda *a:pytest.fail('No descargar cuando está pausado'))
        assert R.run('PIB',tmp_path,True)['status']=='deshabilitada'
    elif case=='local_pdf':assert R.run('PIB',tmp_path,True,Path('/tmp/local.pdf'))['status']=='error'
    elif case=='source_error':
        monkeypatch.setattr(R,'download',lambda *a:(_ for _ in ()).throw(ValueError('Fuente incorrecta')))
        assert R.run('PIB',tmp_path,True)['status']=='error'
    else:
        cfg['auto_publish']=False;(tmp_path/'config/notas_automaticas.json').write_text(json.dumps(cfg))
        fixture(monkeypatch,'PIB');monkeypatch.setattr(R,'download',lambda *a:b'fixture')
        template=tmp_path/cfg['template'];template.parent.mkdir(parents=True);shutil.copyfile(ROOT/cfg['template'],template)
        for name in ['build_gdp_notes.py','notas_pib.py','notas_pib_word.py','notas_layout.py','notas_word.py','build_auto_notes.py']:
            p=tmp_path/'scripts'/name;p.parent.mkdir(exist_ok=True);shutil.copyfile(ROOT/'scripts'/name,p)
        monkeypatch.setattr(R.V,'build',lambda *a:shutil.copyfile(template,a[-1]))
        monkeypatch.setattr(R.W,'render',lambda *a:(None,[1,2]));monkeypatch.setattr(R.V,'validate',lambda *a:None)
        monkeypatch.setattr(R.A,'publish',lambda *a:pytest.fail('Publicación deshabilitada'))
        assert R.run('PIB',tmp_path,True)['status']=='validada_sin_publicar'
    assert dest.read_bytes()==b'previous-word'

def test_workflow_python_311_compatibility():
    for name in ['build_gdp_notes.py','notas_pib.py','notas_pib_word.py','notas_layout.py']:
        ast.parse((ROOT/'scripts'/name).read_text(),feature_version=(3,11))
