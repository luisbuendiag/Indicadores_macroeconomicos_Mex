import ast,json,shutil
from pathlib import Path
from types import SimpleNamespace
import pytest
from docx import Document
import notas_ioae as N
import notas_ioae_word as V
import build_nowcast_notes as R
ROOT=Path(__file__).resolve().parents[1]
class PDF:
    def __init__(self,pages):self.pages=[SimpleNamespace(extract_text=lambda p=p:p) for p in pages]
    def __enter__(self):return self
    def __exit__(self,*a):pass

def fixture(monkeypatch,key='IOAE'):
    pages=json.loads((ROOT/'tests/fixtures/ioae2026_10_pages.json').read_text())
    monkeypatch.setattr(N.pdfplumber,'open',lambda _:PDF(pages));return pages

def test_complete_edition_estimates_and_observed(monkeypatch):
    fixture(monkeypatch);f=N.extract(b'fixture');assert f['period']=='Sep 26' and f['bulletin']=='629/26' and f['base']=='2018'
    rows=V.current(f);assert [r['yoy']['point'] for r in rows]==[3.7,3.6,4]
    assert [(r['mom']['low'],r['mom']['high']) for r in rows]==[(-1,1.2),(-2.1,2.2),(-1.2,1.4)]
    assert [r['index']['point'] for r in rows]==[108.4,103.4,111.3]
    assert all(r['status']=='estimación IOAE' for r in rows)
    observed=f['rows'][2];assert observed['ym']=='2026-08' and observed['status']=='observado IMAI'
    assert observed['yoy']['point']==3.6 and observed['mom']['point']==.6 and observed['index']['point']==103.4
    assert all(observed[field]['low'] is None and observed[field]['high'] is None for field in ['yoy','mom','index'])
    assert len(f['rows'])==6 and len(f['pages'])==6
    assert 'disminuciones' in V.range_text(rows[0]['mom']) and 'por encima' in V.range_text(rows[0]['yoy'])

@pytest.mark.parametrize('case',['pages','edition','period','observed','confidence','bounds','missing','cover','series','method','base','label'])
def test_changed_source_rejected(monkeypatch,case):
    p=fixture(monkeypatch)
    if case=='pages':p.pop()
    elif case=='edition':p[4]=p[4].replace('629/26','999/26')
    elif case=='period':p[1]=p[1].replace('agosto y septiembre de 2026','julio y agosto de 2026',1)
    elif case=='observed':p[0]=p[0].replace('agosto 3.62/','agosto 3.6 2.1 5.1')
    elif case=='confidence':p[0]=p[0].replace('Intervalo de confianza a 95.0 %','Intervalo de confianza a 90.0 %')
    elif case=='bounds':p[0]=p[0].replace('septiembre 3.7 2.6 4.9','septiembre 3.7 4.9 2.6')
    elif case=='missing':p[0]=p[0].replace('septiembre 3.6 1.4 5.9','septiembre 3.6 5.9')
    elif case=='cover':p[0]=p[0].replace('▲ 3.7 %','▲ 8.7 %')
    elif case=='series':p[0]=p[0].replace('cifras desestacionalizadas','cifras originales')
    elif case=='method':p[5]=p[5].replace('no reemplaza el cálculo tradicional del IGAE','reemplaza al IGAE')
    elif case=='base':p[5]=p[5].replace('base 2018=100','base 2020=100')
    else:p[0]=p[0].replace('Actividades secundarias','Actividades primarias')
    with pytest.raises(ValueError):N.extract(b'fixture')

def test_zero_in_interval_not_positive_certainty():
    assert V.range_text({'low':0,'high':1})=='incluye la ausencia de cambio'
    assert V.range_text({'low':-2,'high':-.1})=='se mantiene por debajo de cero'

@pytest.mark.parametrize('key',['IOAE'])
def test_word_tables_all_cotejadas_including_hero(monkeypatch,key):
    fixture(monkeypatch,key);f=N.extract(b'fixture',key);d=Document()
    for data in V.tables(f):
        t=d.add_table(rows=0,cols=len(data[0]))
        for row in data:
            for c,v in zip(t.add_row().cells,row):c.text=v
    candidate=SimpleNamespace(tables=d.tables,inline_shapes=[1,2]);V.validate(f,candidate)
    candidate.tables[0].rows[1].cells[0].text='Índice 9999'
    with pytest.raises(ValueError):V.validate(f,candidate)

@pytest.mark.parametrize('key',['IOAE'])
def test_strict_source_allowlist(key):
    directory,name=N.PRODUCTS[key];url=f'https://www.inegi.org.mx/contenidos/saladeprensa/boletines/2026/{directory}/{name}2026_10.pdf'
    assert R.allowed(url,key)
    for bad in [url+'?x=evil',url+'#x',url.replace('www.inegi.org.mx','example.com'),url.replace('https:','http:'),url.replace(name+'2026','otro2026')]:assert not R.allowed(bad,key)
    assert not R.allowed(url,'EMIM')

@pytest.mark.parametrize('case',['disabled','source_error','local_pdf','pause'])
def test_publication_preserves_previous_word(monkeypatch,tmp_path,case):
    for name in ['data/indicadores.json','data/notas/estado.json','config/notas_automaticas.json']:
        p=tmp_path/name;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,p)
    dest=tmp_path/'downloads/indicadores/IOAE/nota/IOAE_nota.docx';dest.parent.mkdir(parents=True);dest.write_bytes(b'previous-word')
    cfg=json.loads((tmp_path/'config/notas_automaticas.json').read_text())
    if case=='disabled':
        cfg['enabled']=False;(tmp_path/'config/notas_automaticas.json').write_text(json.dumps(cfg))
        monkeypatch.setattr(R,'download',lambda *a:pytest.fail('No descargar cuando está pausado'))
        assert R.run('IOAE',tmp_path,True)['status']=='deshabilitada'
    elif case=='local_pdf':assert R.run('IOAE',tmp_path,True,Path('/tmp/local.pdf'))['status']=='error'
    elif case=='source_error':
        monkeypatch.setattr(R,'download',lambda *a:(_ for _ in ()).throw(ValueError('Fuente incorrecta')))
        assert R.run('IOAE',tmp_path,True)['status']=='error'
    else:
        cfg['auto_publish']=False;(tmp_path/'config/notas_automaticas.json').write_text(json.dumps(cfg))
        fixture(monkeypatch,'IOAE');monkeypatch.setattr(R,'download',lambda *a:b'fixture')
        template=tmp_path/cfg['template'];template.parent.mkdir(parents=True);shutil.copyfile(ROOT/cfg['template'],template)
        for name in ['build_nowcast_notes.py','notas_ioae.py','notas_ioae_word.py','notas_layout.py','notas_word.py','build_auto_notes.py']:
            p=tmp_path/'scripts'/name;p.parent.mkdir(exist_ok=True);shutil.copyfile(ROOT/'scripts'/name,p)
        monkeypatch.setattr(R.V,'build',lambda *a:shutil.copyfile(template,a[-1]))
        monkeypatch.setattr(R.W,'render',lambda *a:(None,[1,2]));monkeypatch.setattr(R.V,'validate',lambda *a:None)
        monkeypatch.setattr(R.A,'publish',lambda *a:pytest.fail('Publicación deshabilitada'))
        assert R.run('IOAE',tmp_path,True)['status']=='validada_sin_publicar'
    assert dest.read_bytes()==b'previous-word'

def test_workflow_python_311_compatibility():
    for name in ['build_nowcast_notes.py','notas_ioae.py','notas_ioae_word.py','notas_layout.py']:
        ast.parse((ROOT/'scripts'/name).read_text(),feature_version=(3,11))
