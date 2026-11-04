"""Freeze a selected first-party reading set without copying telemetry or dependencies."""
from pathlib import Path
import hashlib, json, subprocess, datetime, shutil, logging

ROOT = Path(__file__).resolve().parents[3]
PACK = Path(__file__).resolve().parents[1]
def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT).decode('utf-8', 'replace').strip()
def sha(p):
    h = hashlib.sha256()
    with p.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''): h.update(chunk)
    return h.hexdigest()
excluded = {'__pycache__', 'node_modules', '.agents', '.git', 'Data', 'dist', '.venv'}
roots = ['pipeline','src','scripts','docs','tests']
files = []
for prefix in roots:
    for p in (ROOT/prefix).rglob('*'):
        if p.is_file() and not any(x in excluded for x in p.relative_to(ROOT).parts) and p.suffix.lower() in {'.py','.ts','.tsx','.css','.md','.mjs','.json'}:
            files.append(p)
for name in ['AGENTS.md','PROJECT.md','README.md','package.json','package-lock.json','run.ps1','vite.config.ts','index.html','requirements.txt','LICENSE','LICENSE.md','LICENSE.txt','NOTICE']:
    p=ROOT/name
    if p.is_file(): files.append(p)
for p in ROOT.glob('tsconfig*.json'): files.append(p)
for p in (ROOT/'config').rglob('*') if (ROOT/'config').exists() else []:
    if p.is_file() and p.suffix.lower() in {'.json','.yaml','.yml','.toml'}: files.append(p)
records=[]
for p in sorted(set(files)):
    rel=p.relative_to(ROOT).as_posix()
    dest=PACK/'source'/rel
    dest.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(p,dest)
    records.append({'path':rel,'bytes':p.stat().st_size,'sha256':sha(p)})
status=git('status','--porcelain=v1','--untracked-files=all')
status='\n'.join(x for x in status.splitlines() if 'offline-study-pack/' not in x)
snap={'review_date':'2026-11-04','timezone':'Europe/Rome','captured_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'commit':git('rev-parse','HEAD'),'branch':git('branch','--show-current'),'dirty':bool(status),'status_excluding_pack':status,'reading_set':'Selected first-party source snapshot, including tests and documentation; no raw telemetry, dependencies, caches or credentials. Public evidence is separately bounded.','files':records}
(PACK/'evidence'/'snapshot.json').write_text(json.dumps(snap,indent=2),encoding='utf8')
(PACK/'evidence'/'git-status.txt').write_text(status+'\n',encoding='utf8')
logging.basicConfig(level=logging.INFO)
logging.info(json.dumps({'commit':snap['commit'],'dirty':snap['dirty'],'source_files':len(records),'source_bytes':sum(r['bytes'] for r in records),'status_lines':len(status.splitlines())}))
