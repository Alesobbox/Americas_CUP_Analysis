"""Keep superseded drafts outside the delivery and refresh local navigation."""
from pathlib import Path
import json,shutil
import build_pack as b
P=b.P
backup=P.parent/'.qa-2026-11-04'/'superseded-materials'
backup.mkdir(parents=True,exist_ok=True)
for name in ['examples','study-materials','source-companion','04_Workbook_Solutions.md','04_Workbook_Solutions.html','04_Workbook_Solutions.pdf']:
    src=(P/name).resolve()
    assert src.is_relative_to(P.resolve())
    if src.exists():shutil.move(str(src),str(backup/name))
keep={'archive-overview.json','concept_lab_output.json','coverage-26_09_23_nap_ipr_pr1.json','coverage-naples_mr_final.json','coverage-naples_pr1.json','cup_publication_snapshot.json','data_metrics_review.json','forecast_backtest_snapshot.json','forecast_model_snapshot.json','forecast_review.json','git-status.txt','interface_review.json','public-artifact-hashes.json','snapshot.json','storage.json'}
for src in (P/'evidence').iterdir():
    if src.is_file() and src.name not in keep:
        dest=backup/'evidence'/src.name;dest.parent.mkdir(exist_ok=True);shutil.move(str(src),str(dest))
for name in ['03_Repository_Atlas','VERIFICATION']:
    b.write_html(name,(P/(name+'.md')).read_text(encoding='utf8'))
b.evidence_index()
for f in [P/'START_HERE.html',P/'07_Flashcards.html',P/'09_Interactive_Lab.html',P/'source/_SOURCE_INDEX.html']:
    s=f.read_text(encoding='utf8').replace('<a href="#contents">Contents</a>','')
    f.write_text(s,encoding='utf8')
checks=b.P/'verification/pack-checks.json'
data=json.loads(checks.read_text())
# PDF checks were rendered and inspected separately; refresh local links after cleanup.
from verify_pack import link_check,source_check
data['local_links']=link_check();data['source']=source_check()
assert not data['local_links']['errors'],data['local_links']['errors']
assert not data['source']['source_drift'] and not data['source']['public_drift'] and not data['source']['invalid_citation_ranges']
checks.write_text(json.dumps(data,indent=2),encoding='utf8')
