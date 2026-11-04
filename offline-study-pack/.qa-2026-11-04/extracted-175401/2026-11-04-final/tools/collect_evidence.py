from pathlib import Path
import json,hashlib,shutil,subprocess,datetime,logging
R=Path(__file__).resolve().parents[3]; P=Path(__file__).resolve().parents[1]
def h(p):
    m=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):m.update(b)
    return m.hexdigest()
snap=json.loads((P/'evidence/snapshot.json').read_text())
for rel in ['pyproject.toml','uv.lock','.gitignore','.python-version','public/fonts/OFL.txt','public/fonts/README.md']:
    f=R/rel
    if f.is_file():
        d=P/'source'/rel;d.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(f,d)
        if rel not in {x['path'] for x in snap['files']}:snap['files'].append({'path':rel,'bytes':f.stat().st_size,'sha256':h(f)})
(P/'evidence/snapshot.json').write_text(json.dumps(snap,indent=2),encoding='utf8')
records=[]
for f in sorted((R/'public/data').rglob('*')):
    if f.is_file():records.append({'path':f.relative_to(R).as_posix(),'bytes':f.stat().st_size,'sha256':h(f)})
(P/'evidence/public-artifact-hashes.json').write_text(json.dumps({'recorded_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'scope':'Actual bytes of all existing public data files; raw Data archive not read or hashed in this review.','files':records},indent=2),encoding='utf8')
sizes={}
for folder in ['dist','public/data']:
    fs=[f for f in (R/folder).rglob('*') if f.is_file()]
    sizes[folder]={'files':len(fs),'bytes':sum(f.stat().st_size for f in fs)}
sizes['optional_dashboard_policy']='Measured but not included: copy a prepared build separately only after testing a local HTTP server. Grid needs no tiles; new forecasts need a prepared Python backend/dataset. Core study pack is standalone.'
(P/'evidence/storage.json').write_text(json.dumps(sizes,indent=2),encoding='utf8')
overview=subprocess.check_output([str(R/'.venv/Scripts/python.exe'),'scripts/analysis_snapshot.py'],cwd=R)
(P/'evidence/archive-overview.json').write_bytes(overview)
for rid in ['naples_pr1','naples_mr_final','26_09_23_nap_ipr_pr1']:
    out=subprocess.check_output([str(R/'.venv/Scripts/python.exe'),'scripts/analysis_snapshot.py','--race',rid],cwd=R)
    (P/'evidence'/('coverage-'+rid+'.json')).write_bytes(out)
# Retain readable test summaries and logs, avoiding redundant browser screenshots.
for f in (P/'verification').rglob('*.png'):
    if f.parent.name in {'dashboard-browser','forecast-browser'}:f.unlink()
logging.basicConfig(level=logging.INFO)
logging.info(json.dumps({'source_files':len(snap['files']),'public_files':len(records),'public_bytes':sum(x['bytes'] for x in records),'sizes':sizes}))
