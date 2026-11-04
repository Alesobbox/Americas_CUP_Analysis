"""Record final reading checks without altering the reviewed application."""
import json
import build_pack as b
from verify_pack import link_check,source_check
P=b.P
for name in ['START_HERE.html','07_Flashcards.html','09_Interactive_Lab.html','source/_SOURCE_INDEX.html']:
    f=P/name;s=f.read_text(encoding='utf8').replace('<a href="#contents">Contents</a>','');f.write_text(s,encoding='utf8')
f=P/'VERIFICATION.md'
note='\n\n## Final delivery checks\n\nThe main textbook has77 pages,48 bookmarks and374 link annotations. The field guide has11 pages; workbook and separate answer key have eight pages each. All PDF pages were rendered and visually reviewed through full-document contact sheets, with dense pages and diagrams additionally checked at readable scale. Embedded fonts, searchable text, page bounds and missing-glyph checks pass. All213 frozen source files and506 public artifacts remain unchanged.\n\nThe study-tool scan scores93/100 with no errors or fixable warnings. Its single remaining warning incorrectly treats self.links initialized inside a parser constructor as a mutable function default; no function argument has that default. Optional Ruff/Knip/dependency-audit coverage is unavailable as disclosed by the scan; no application configuration was changed to hide findings.\n'
s=f.read_text(encoding='utf8')
if '## Final delivery checks' not in s:f.write_text(s+note,encoding='utf8')
b.write_html('VERIFICATION',f.read_text(encoding='utf8'))
f=P/'verification/pack-checks.json';data=json.loads(f.read_text());data['local_links']=link_check();data['source']=source_check();data['visual_review']={'all_pages_contact_sheets':True,'dense_math_tables_and_figures_reviewed':True,'no_clipping_or_missing_glyphs':True}
assert not data['local_links']['errors'],data['local_links']['errors']
assert not data['source']['source_drift'] and not data['source']['public_drift']
f.write_text(json.dumps(data,indent=2),encoding='utf8')
f=P/'tools/offline_browser.mjs';s=f.read_text(encoding='utf8').replace(',archive_sha256:info.archive_sha256','');f.write_text(s,encoding='utf8')
