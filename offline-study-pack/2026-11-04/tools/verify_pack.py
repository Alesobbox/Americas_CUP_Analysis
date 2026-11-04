"""Validate PDF structure, local links, source references and snapshot preservation."""
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import urlsplit,unquote
import hashlib,json,re,logging
from pypdf import PdfReader
import pdfplumber
import pypdfium2 as pdfium
from PIL import Image,ImageDraw

P=Path(__file__).resolve().parents[1];R=P.parents[1];Q=P.parent/'.qa-2026-11-04';Q.mkdir(exist_ok=True)
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
class Links(HTMLParser):
    def __init__(self):super().__init__();self.links=[];self.ids=set()
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if 'id'in a:self.ids.add(a['id'])
        if tag=='a' and 'href'in a:self.links.append(a['href'])
        if tag in {'img','script','link'}:
            src=a.get('src',a.get('href',''))
            if src and not src.startswith('data:'):self.links.append(src)

def pdf_check(f):
    reader=PdfReader(f);texts=[p.extract_text() or '' for p in reader.pages]
    outlines=[]
    def walk(items):
        for x in items:
            if isinstance(x,list):walk(x)
            else:outlines.append(str(x.title))
    walk(reader.outline)
    embedded=set();links=0
    for p in reader.pages:
        links+=len(p.get('/Annots',[]))
        for obj in p.get('/Resources',{}).get('/Font',{}).values():
            font=obj.get_object();desc=font.get('/FontDescriptor')
            if desc:
                dd=desc.get_object()
                if any(k in dd for k in ['/FontFile','/FontFile2','/FontFile3']):embedded.add(str(font.get('/BaseFont')))
    bounds=[]
    with pdfplumber.open(f) as doc:
        for i,page in enumerate(doc.pages,1):
            bad=[c for c in page.chars if c['x0']<25 or c['x1']>page.width-25 or c['top']<10 or c['bottom']>page.height-10]
            if bad:bounds.append({'page':i,'outside_safe_page':len(bad),'excerpt':''.join(c['text'] for c in bad)[:100]})
    doc=pdfium.PdfDocument(str(f));renders=Q/f.stem;renders.mkdir(exist_ok=True)
    thumbs=[]
    for i in range(len(doc)):
        bitmap=doc[i].render(scale=1.25);im=bitmap.to_pil();im.save(renders/f'page-{i+1:03}.png')
        thumb=im.copy();thumb.thumbnail((238,336));thumbs.append(thumb)
    sheets=[]
    for start in range(0,len(thumbs),12):
        sheet=Image.new('RGB',(1000,1135),'#dbe4e6');draw=ImageDraw.Draw(sheet)
        for j,im in enumerate(thumbs[start:start+12]):
            x=(j%4)*250+6;y=(j//4)*375+25;sheet.paste(im,(x,y));draw.text((x,y-18),str(start+j+1),fill='black')
        out=Q/(f.stem+f'-sheet-{start//12+1}.png');sheet.save(out);sheets.append(str(out))
    result={'file':f.name,'pages':len(reader.pages),'bytes':f.stat().st_size,'characters':sum(map(len,texts)),'bookmarks':len(outlines),'link_annotations':links,'embedded_fonts':sorted(embedded),'page_bounds_findings':bounds,'rendered_all_pages':True,'contact_sheets':sheets,'replacement_glyphs':sum(t.count('\ufffd')+t.count('\u25a0') for t in texts)}
    assert embedded and outlines and not bounds and result['replacement_glyphs']==0,result
    if f.name.startswith('01_'):assert 'Contents' in ''.join(texts[:5]) and links>100
    return result

def link_check():
    parsed={}
    originals={P/'source'/x['path'] for x in json.loads((P/'evidence/snapshot.json').read_text())['files']}
    for f in P.rglob('*.html'):
        if f in originals:continue
        x=Links();x.feed(f.read_text(encoding='utf8'));parsed[f]=x
    errors=[];count=0
    for f,doc in parsed.items():
        for link in doc.links:
            u=urlsplit(link)
            if u.scheme or u.netloc:continue
            target=(f.parent/unquote(u.path)).resolve() if u.path else f
            count+=1
            if not target.exists():errors.append([str(f.relative_to(P)),link,'missing file'])
            elif u.fragment and target in parsed and unquote(u.fragment) not in parsed[target].ids:errors.append([str(f.relative_to(P)),link,'missing anchor'])
    return {'html_files':len(parsed),'local_links_checked':count,'errors':errors}

def source_check():
    snap=json.loads((P/'evidence/snapshot.json').read_text());changed=[]
    for x in snap['files']:
        if digest(R/x['path'])!=x['sha256']:changed.append(x['path'])
        assert digest(P/'source'/x['path'])==x['sha256']
    public=json.loads((P/'evidence/public-artifact-hashes.json').read_text());pubchanged=[]
    for x in public['files']:
        if digest(R/x['path'])!=x['sha256']:pubchanged.append(x['path'])
    ranges=[]
    for f in (P/'chapters').glob('*.md'):
        for path,start,end in re.findall(r'\[([^\]\n]+?):L(\d+)-L?(\d+)\]',f.read_text(encoding='utf8')):
            original=R/path
            if not original.exists() or not 1<=int(start)<=int(end)<=len(original.read_text(encoding='utf8').splitlines()):ranges.append({'chapter':f.name,'path':path,'start':start,'end':end})
    return {'source_files_verified':len(snap['files']),'source_drift':changed,'public_files_verified':len(public['files']),'public_drift':pubchanged,'invalid_citation_ranges':ranges}

def main():
    result={'review_date':'2026-11-04','pdfs':[pdf_check(f) for f in sorted(P.glob('*.pdf'))],'local_links':link_check(),'source':source_check()}
    (P/'verification/pack-checks.json').write_text(json.dumps(result,indent=2),encoding='utf8')
    logging.basicConfig(level=logging.INFO)
    logging.info(json.dumps(result,ensure_ascii=True))
if __name__=='__main__':main()
