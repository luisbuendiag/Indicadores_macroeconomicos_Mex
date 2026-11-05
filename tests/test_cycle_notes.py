import ast,json,shutil
from pathlib import Path
from types import SimpleNamespace
import pytest
from docx import Document
import notas_sic as N
import notas_sic_word as V
import build_cycle_notes as R
from sources import inegi_sic as P
ROOT=Path(__file__).resolve().parents[1]
class PDF:
    def __init__(self,pages):self.pages=[SimpleNamespace(extract_text=lambda p=p:p) for p in pages]
    def __enter__(self):return self
    def __exit__(self,*a):pass

def fixture(monkeypatch,key='SIC'):
    pages=json.loads((ROOT/'tests/fixtures/sic2026_11_pages.json').read_text())
    monkeypatch.setattr(N.pdfplumber,'open',lambda _:PDF(pages));return pages

def test_periods_points_precision_and_inverses(monkeypatch):
    fixture(monkeypatch);f=N.extract(b'fixture');c,a=f['groups']
    assert f['period']=='Ago 26' and f['bulletin']=='679/26' and f['publication_date']=='2026-11-04'
    assert (c['level'],c['delta'],a['level'],a['delta'])==(100.2,.12,100.8,.01)
    assert c['period']=='Ago 26' and a['period']=='Sep 26'
    assert len(c['history'])==len(a['history'])==12
    assert [r['delta'] for r in c['components']]==[.17,.18,0,-.01,-.10,.22]
    assert [r['delta'] for r in a['components']]==[.13,.04,-.13,.02,0,.02]
    assert [r['label'] for g in [c,a] for r in g['components'] if r['inverse']]==['Desocupación urbana','Tipo de cambio real México-EUA','TIIE']
    assert c['history'][0]['ym']=='2025-09' and a['history'][0]['ym']=='2025-10'

@pytest.mark.parametrize('case',['pages','edition','period','cover','method','units','columns','gap','inverse','position','duplicate'])
def test_changed_source_rejected(monkeypatch,case):
    pages=fixture(monkeypatch)
    if case=='pages':pages.pop()
    elif case=='edition':pages[7]=pages[7].replace('679/26','999/26')
    elif case=='period':pages[5]=pages[5].replace('octubre de 2025–septiembre de 2026','septiembre de 2025–agosto de 2026')
    elif case=='cover':pages[0]=pages[0].replace('100.2 ▲ 0.12','100.2 ▲ 0.99')
    elif case=='method':pages[12]=pages[12].replace('Hodrick-Prescott','OTRO')
    elif case=='units':pages[2]=pages[2].replace('diferencia en puntos','variación en porcentaje')
    elif case=='columns':pages[2]=pages[2].replace('Importaciones','Exportaciones')
    elif case=='gap':pages[5]=pages[5].replace('Ago. 0.02','Jul. 0.02')
    elif case=='inverse':pages[3]=pages[3].replace('Tasa de desocupación urbana1/','Tasa de desocupación urbana')
    elif case=='position':pages[0]=pages[0].replace('por arriba','por debajo')
    else:pages[2]=pages[2].replace('Ago. 0.12','Jul. 0.12')
    with pytest.raises(ValueError):N.extract(b'fixture')

def test_source_url_follows_official_publication_not_reference():
    ind={'fecha_publicacion_oficial':'4 de noviembre de 2026','last_observation':'Ago 26'}
    assert P.expected_bulletin_url(ind).endswith('/2026/sic_cya/sic2026_11.pdf')
    ind['fecha_publicacion_oficial']='2026-01-08';assert P.expected_bulletin_url(ind).endswith('sic2026_01.pdf')
    for value in ['x','1 de enero de 2099']:
        with pytest.raises(ValueError):P.expected_bulletin_url({'fecha_publicacion_oficial':value})

def test_source_correction_race_rollback_and_observations(monkeypatch,tmp_path):
    path=tmp_path/'data/indicadores.json';path.parent.mkdir();p={'indicators':{'SIC':{'url_boletin_oficial':'old','last_observation':'Ago 26','fecha_publicacion_oficial':'4 de noviembre de 2026','observations':[{'period':'Ago 26','values':[100.1741]}]}}};path.write_text(json.dumps(p));before=path.read_bytes()
    f={'period':'Ago 26','publication_date':'2026-11-04','bulletin':'679/26'}
    with pytest.raises(ValueError):R.publish(tmp_path,None,f,'fp','new',{}, {},'raced','4 de noviembre de 2026')
    assert path.read_bytes()==before
    monkeypatch.setattr(R.A,'publish',lambda *a:(_ for _ in ()).throw(ValueError('rollback')))
    with pytest.raises(ValueError):R.publish(tmp_path,None,f,'fp','new',{}, {},'old','4 de noviembre de 2026')
    assert path.read_bytes()==before
    monkeypatch.setattr(R.A,'publish',lambda *a:{'status':'vigente'})
    assert R.publish(tmp_path,None,f,'fp','new',{}, {},'old','4 de noviembre de 2026')['status']=='vigente'
    new=json.loads(path.read_text())['indicators']['SIC'];assert new['url_boletin_oficial']=='new' and new['observations']==p['indicators']['SIC']['observations']

@pytest.mark.parametrize('key',['SIC'])
def test_word_tables_all_cotejadas_including_hero(monkeypatch,key):
    fixture(monkeypatch,key);f=N.extract(b'fixture',key);d=Document()
    for data in V.tables(f):
        t=d.add_table(rows=0,cols=len(data[0]))
        for row in data:
            for c,v in zip(t.add_row().cells,row):c.text=v
    candidate=SimpleNamespace(tables=d.tables,inline_shapes=[1,2]);V.validate(f,candidate)
    candidate.tables[0].rows[1].cells[0].text='Índice 9999'
    with pytest.raises(ValueError):V.validate(f,candidate)

@pytest.mark.parametrize('key',['SIC'])
def test_strict_source_allowlist(key):
    directory,name=N.PRODUCTS[key];url=f'https://www.inegi.org.mx/contenidos/saladeprensa/boletines/2026/{directory}/{name}2026_10.pdf'
    assert R.allowed(url,key)
    for bad in [url+'?x=evil',url+'#x',url.replace('www.inegi.org.mx','example.com'),url.replace('https:','http:'),url.replace(name+'2026','otro2026')]:assert not R.allowed(bad,key)
    assert not R.allowed(url,'EMIM')

@pytest.mark.parametrize('case',['disabled','source_error','local_pdf','pause'])
def test_publication_preserves_previous_word(monkeypatch,tmp_path,case):
    for name in ['data/indicadores.json','data/notas/estado.json','config/notas_automaticas.json']:
        p=tmp_path/name;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,p)
    dest=tmp_path/'downloads/indicadores/SIC/nota/SIC_nota.docx';dest.parent.mkdir(parents=True);dest.write_bytes(b'previous-word')
    cfg=json.loads((tmp_path/'config/notas_automaticas.json').read_text())
    if case=='disabled':
        cfg['enabled']=False;(tmp_path/'config/notas_automaticas.json').write_text(json.dumps(cfg))
        monkeypatch.setattr(R,'download',lambda *a:pytest.fail('No descargar cuando está pausado'))
        assert R.run('SIC',tmp_path,True)['status']=='deshabilitada'
    elif case=='local_pdf':assert R.run('SIC',tmp_path,True,Path('/tmp/local.pdf'))['status']=='error'
    elif case=='source_error':
        monkeypatch.setattr(R,'download',lambda *a:(_ for _ in ()).throw(ValueError('Fuente incorrecta')))
        assert R.run('SIC',tmp_path,True)['status']=='error'
    else:
        cfg['auto_publish']=False;(tmp_path/'config/notas_automaticas.json').write_text(json.dumps(cfg))
        fixture(monkeypatch,'SIC');monkeypatch.setattr(R,'download',lambda *a:b'fixture')
        template=tmp_path/cfg['template'];template.parent.mkdir(parents=True);shutil.copyfile(ROOT/cfg['template'],template)
        for name in ['build_cycle_notes.py','notas_sic.py','notas_sic_word.py','notas_layout.py','notas_word.py','build_auto_notes.py','sources/inegi_sic.py']:
            p=tmp_path/'scripts'/name;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/'scripts'/name,p)
        monkeypatch.setattr(R.V,'build',lambda *a:shutil.copyfile(template,a[-1]))
        monkeypatch.setattr(R.W,'render',lambda *a:(None,[1,2]));monkeypatch.setattr(R.V,'validate',lambda *a:None)
        monkeypatch.setattr(R.A,'publish',lambda *a:pytest.fail('Publicación deshabilitada'))
        assert R.run('SIC',tmp_path,True)['status']=='validada_sin_publicar'
    assert dest.read_bytes()==b'previous-word'

def test_workflow_python_311_compatibility():
    for name in ['build_cycle_notes.py','notas_sic.py','notas_sic_word.py','notas_layout.py']:
        ast.parse((ROOT/'scripts'/name).read_text(),feature_version=(3,11))
