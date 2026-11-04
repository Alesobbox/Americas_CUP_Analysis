"""Assemble an isolated delivery from the reviewed materials."""
from pathlib import Path
import shutil
P=Path(__file__).resolve().parents[1]
F=P.parent/'2026-11-04-final'
F.mkdir(exist_ok=True)
for directory in ['assets','chapters','source','tools']:
    shutil.copytree(P/directory,F/directory,dirs_exist_ok=True,ignore=shutil.ignore_patterns('__pycache__','finish_editions.py','deliver_final.py'))
for name in ['pyproject.toml','package.json','05_Learning_Routes.md','06_Narration.md','VERIFICATION.md']:
    shutil.copy2(P/name,F/name)
for directory in ['evidence','verification']:
    (F/directory).mkdir(exist_ok=True)
    for f in (P/directory).iterdir():
        if f.is_file():shutil.copy2(f,F/directory/f.name)
f=F/'tools/build_pack.py';s=f.read_text(encoding='utf8')
s=s.replace("        if kind=='h1':\n", "        if kind=='break':\n            story.append(PageBreak());continue\n        if kind=='h1':\n")
s=s.replace("        elif kind=='break':story.append(PageBreak())\n",'')
s=s.replace(".replace('</','<\\/')", ".replace('</',r'<\\/')")
f.write_text(s,encoding='utf8')
f=F/'tools/verify_pack.py';s=f.read_text(encoding='utf8').replace("        for obj in p.get('/Resources',{}).get('/Font',{}).values():", "        resources=p['/Resources']\n        fonts=resources['/Font'] if '/Font' in resources else {}\n        for obj in fonts.values():")
f.write_text(s,encoding='utf8')
f=F/'tools/offline_browser.mjs';s=f.read_text(encoding='utf8').replace("import {pathToFileURL} from 'node:url';","import {pathToFileURL,fileURLToPath} from 'node:url';").replace("const pack=path.resolve('offline-study-pack/2026-11-04');","const pack=fileURLToPath(new URL('../',import.meta.url));")
f.write_text(s,encoding='utf8')
f=F/'tools/author_learning.py';s=f.read_text(encoding='utf8').replace('C:\\Workspace\\Americas Cup\\2D_regatta_replay','C:/Workspace/Americas Cup/2D_regatta_replay');f.write_text(s,encoding='utf8')
