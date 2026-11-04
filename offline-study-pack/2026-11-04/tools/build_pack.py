"""Build local reading editions and PDFs from the authored Markdown sources."""
from pathlib import Path
import base64,csv,hashlib,html,json,re
from urllib.parse import quote
from xml.sax.saxutils import escape
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet,ParagraphStyle
from reportlab.lib.pagesizes import A4
from reportlab.platypus import BaseDocTemplate,PageTemplate,Frame,Paragraph,Spacer,PageBreak,Table,TableStyle,Image,KeepTogether
from reportlab.platypus.tableofcontents import TableOfContents

P=Path(__file__).resolve().parents[1]
CSS='''*{box-sizing:border-box}body{margin:0;background:#f4f5f3;color:#172d36;font:17px/1.65 system-ui,sans-serif}header,main{max-width:980px;margin:auto;padding:26px}header{background:#153c4a;color:white}header a{color:#d0eeed}nav{position:sticky;top:0;background:#fff;padding:12px;z-index:5;border-bottom:1px solid #b8c8cd}nav a{margin-right:16px}input{padding:10px;min-width:220px;font:inherit}article{background:white;padding:30px;margin-bottom:24px}h1{font-size:2em}h2{font-size:1.6em;margin-top:1.7em;line-height:1.3}h3{font-size:1.17em;color:#256272;margin-top:1.5em}p{margin:0 0 1em}a{color:#145c7c;overflow-wrap:anywhere}code{font:0.87em/1.5 Consolas,monospace;background:#f0f3f4;overflow-wrap:anywhere}pre{white-space:pre-wrap;background:#f0f3f4;padding:16px;overflow-wrap:anywhere}table{border-collapse:collapse;width:100%;font-size:.86em;display:block;overflow-x:auto;margin:20px 0}th,td{border:1px solid #ccd7db;padding:10px;vertical-align:top}th{background:#e4eff0;text-align:left}img{max-width:100%;height:auto}figure{margin:22px 0}figcaption{font-size:.9em;color:#405b66}li{margin-bottom:.5em}.toc{columns:2;column-gap:30px}.line{display:block;white-space:pre-wrap;overflow-wrap:anywhere;font:13px/1.6 Consolas,monospace}.line:target{background:#fff0b0}.num{display:inline-block;width:4.5em;color:#607880}.note{padding:16px;background:#e8f2f2;border-left:4px solid #29808d}button{padding:12px;font:inherit;cursor:pointer}#search-status{margin-left:12px}.hidden{display:none}@media(max-width:650px){main,header{padding:16px}article{padding:18px}.toc{columns:1}table{font-size:.82em}}@media print{nav{display:none}body{background:white}article{padding:0}h2{break-before:page}a{color:inherit}}'''
SEARCH='''document.querySelector('#search')?.addEventListener('input',e=>{const q=e.target.value.toLowerCase().trim();let n=0;document.querySelectorAll('article').forEach(a=>{const show=!q||a.textContent.toLowerCase().includes(q);a.hidden=!show;if(show)n++});document.querySelector('#search-status').textContent=q?n+' sections match':''});'''
def ident(s):return re.sub(r'[^a-z0-9]+','-',s.lower()).strip('-')
def content_hash(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def spaced(s):
    def fix(m):
        t=m.group()
        if '_' in t or (len(t)>=7 and re.fullmatch('[a-fA-F0-9]+',t)):return t
        prefix=re.match('[A-Za-z]+',t)
        if prefix and prefix[0].isupper():return t
        return re.sub(r'(?<=[A-Za-z])(?=\d)|(?<=\d)(?=[A-Za-z])',' ',t)
    return re.sub(r'\b(?:[A-Za-z]+\d+[A-Za-z0-9]*|\d+[A-Za-z]+)\b',fix,s)

def ref_link(path,start):
    if (P/'source'/path).is_file():return 'source/'+quote(path,safe='/')+'.html#L'+start
    return '08_Evidence_Index.html#'+ident(path)
REF=re.compile(r'\[([^\]\n]+?):L(\d+)-L?(\d+)\]')
def inline(s,pdf=False):
    s=escape(s) if pdf else html.escape(s)
    s=REF.sub(lambda m:('<link href="'+ref_link(m[1],m[2])+'" color="#245b71">'+m[1]+':'+m[2]+'-'+m[3]+'</link>') if pdf else ('<a href="'+ref_link(m[1],m[2])+'">'+m[1]+':'+m[2]+'-'+m[3]+'</a>'),s)
    def link(m):
        label,target=m[1],html.unescape(m[2]);target=target.replace('"','%22')
        return f'<link href="{escape(target)}" color="#245b71">{label}</link>' if pdf else f'<a href="{html.escape(target,quote=True)}">{label}</a>'
    s=re.sub(r'\[([^\]]+)\]\(([^)]+)\)',link,s)
    s=re.sub(r'`([^`]+)`',r'<font name="Mono">\1</font>' if pdf else r'<code>\1</code>',s)
    s=re.sub(r'\*\*([^*]+)\*\*',r'<b>\1</b>',s)
    s=re.sub(r'(?<!\*)\*([^*\n]+)\*(?!\*)',r'<i>\1</i>',s)
    return s

def blocks(md):
    lines=md.splitlines();out=[];i=0
    while i<len(lines):
        s=lines[i].strip()
        if not s:i+=1;continue
        if s.startswith('```'):
            i+=1;chunk=[]
            while i<len(lines) and not lines[i].strip().startswith('```'):chunk.append(lines[i]);i+=1
            out.append(('code','\n'.join(chunk)));i+=1;continue
        if s.startswith('<!-- PAGEBREAK'):out.append(('break',''));i+=1;continue
        h=re.match(r'^(#{1,4}) (.*)',s)
        if h:out.append(('h'+str(len(h[1])),h[2]));i+=1;continue
        image=re.fullmatch(r'!\[([^]]*)\]\(([^)]+)\)',s)
        if image:out.append(('image',(image[1],image[2])));i+=1;continue
        if s.startswith('|'):
            rows=[]
            while i<len(lines) and lines[i].strip().startswith('|'):
                row=[x.strip() for x in lines[i].strip().strip('|').split('|')]
                if not all(re.fullmatch(r'[:\- ]+',x or '-') for x in row):rows.append(row)
                i+=1
            out.append(('table',rows));continue
        li=re.match(r'^(?:[-*]|\d+[.)]) (.*)',s)
        if li:out.append(('li',li[1]));i+=1;continue
        chunk=[s];i+=1
        while i<len(lines) and lines[i].strip() and not re.match(r'^(#{1,4} |\||```|!\[|<!--|[-*] |\d+[.)] )',lines[i].strip()):chunk.append(lines[i].strip());i+=1
        out.append(('p',' '.join(chunk)))
    return out

def html_body(md,embedded=True):
    result=[];heads=[];used={}
    for kind,value in blocks(md):
        if kind.startswith('h'):
            base=ident(value);used[base]=used.get(base,0)+1;anchor=base+('' if used[base]==1 else '-'+str(used[base]))
            if kind in {'h1','h2'}:heads.append((value,anchor))
            if kind=='h2':result.append('</article><article>')
            result.append(f'<{kind} id="{anchor}">{inline(value)}</{kind}>')
        elif kind in {'p','li','code'}:
            tags={'p':('<p>','</p>'),'li':('<p class="item">• ','</p>'),'code':('<pre>','</pre>')}
            opening,closing=tags[kind]
            result.append(opening+(html.escape(value) if kind=='code' else inline(value))+closing)
        elif kind=='table':
            result.append('<table>')
            for k,row in enumerate(value):
                tag='th' if k==0 else 'td';result.append('<tr>'+''.join('<'+tag+'>'+inline(c)+'</'+tag+'>' for c in row)+'</tr>')
            result.append('</table>')
        elif kind=='image':
            caption,filename=value;f=P/filename
            uri='data:image/png;base64,'+base64.b64encode(f.read_bytes()).decode() if embedded else filename
            result.append(f'<figure><img src="{uri}" alt="{html.escape(caption,quote=True)}"><figcaption>{inline(caption)}</figcaption></figure>')
    toc='<div class="toc">'+''.join('<p><a href="#'+a+'">'+html.escape(t)+'</a></p>' for t,a in heads)+'</div>'
    return toc,'<article>'+''.join(result)+'</article>'

def html_page(title,body,search=True):
    controls='<input id="search" aria-label="Search sections" type="search" placeholder="Search this edition"><span id="search-status" role="status"></span>' if search else ''
    return f'<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(title)}</title><style>{CSS}</style><header><h1>{html.escape(title)}</h1><a href="START_HERE.html">Study pack home</a></header><nav><a href="#contents">Contents</a>{controls}</nav><main>{body}</main><script>{SEARCH}</script></html>'

def write_html(name,md):
    toc,body=html_body(md);title=next((x[1] for x in blocks(md) if x[0]=='h1'),name)
    (P/(name+'.html')).write_text(html_page(title,'<section id="contents"><h2>Contents</h2>'+toc+'</section>'+body),encoding='utf8')

for family,file in [('Body','arial.ttf'),('Body-Bold','arialbd.ttf'),('Body-Italic','ariali.ttf'),('Body-BoldItalic','arialbi.ttf'),('Mono','consola.ttf')]:
    pdfmetrics.registerFont(TTFont(family,'C:/Windows/Fonts/'+file))
pdfmetrics.registerFontFamily('Body',normal='Body',bold='Body-Bold',italic='Body-Italic',boldItalic='Body-BoldItalic')
styles=getSampleStyleSheet()
styles.add(ParagraphStyle(name='Text',fontName='Body',fontSize=9.7,leading=13.3,spaceAfter=7,splitLongWords=True,allowWidows=0,allowOrphans=0))
styles.add(ParagraphStyle(name='Part',fontName='Body-Bold',fontSize=19,leading=24,textColor=colors.HexColor('#164f60'),spaceAfter=13,keepWithNext=True))
styles.add(ParagraphStyle(name='Chapter',fontName='Body-Bold',fontSize=17,leading=22,spaceAfter=13,keepWithNext=True))
styles.add(ParagraphStyle(name='Sub',fontName='Body-Bold',fontSize=11.2,leading=15,spaceBefore=9,spaceAfter=6,keepWithNext=True,textColor=colors.HexColor('#195b6b')))
styles.add(ParagraphStyle(name='Cell',fontName='Body',fontSize=7.4,leading=10,spaceAfter=0,splitLongWords=True))
styles.add(ParagraphStyle(name='Caption',fontName='Body-Italic',fontSize=8.2,leading=11,spaceAfter=10))
styles.add(ParagraphStyle(name='CodeSmall',fontName='Mono',fontSize=7.3,leading=10,spaceAfter=10))
styles.add(ParagraphStyle(name='TitlePack',fontName='Body-Bold',fontSize=31,leading=37,spaceAfter=24,textColor=colors.HexColor('#163c4b')))
styles.add(ParagraphStyle(name='TOCPack',fontName='Body',fontSize=8.7,leading=12,leftIndent=10,firstLineIndent=-10,spaceAfter=5))

class PackDoc(BaseDocTemplate):
    def __init__(self,filename,title):
        super().__init__(str(filename),pagesize=A4,rightMargin=45,leftMargin=45,topMargin=43,bottomMargin=43,title=title,author='Repository study pack',subject='Evidence-grounded offline explanation of the AC40 regatta repository')
        self.short_title=title;self.counter=0
        frame=Frame(self.leftMargin,self.bottomMargin,self.width,self.height,id='normal',leftPadding=0,rightPadding=0,topPadding=0,bottomPadding=0)
        self.addPageTemplates(PageTemplate(id='normal',frames=frame,onPage=self.footer))
    def footer(self,c,doc):
        c.saveState();c.setFont('Body',7);c.setFillColor(colors.HexColor('#4d6670'));c.drawString(45,25,'Regatta repository study pack | Review 4 November 2026');c.drawRightString(A4[0]-45,25,str(doc.page));c.restoreState()
    def afterFlowable(self,f):
        if isinstance(f,Paragraph) and f.style.name in {'Part','Chapter'}:
            level=0 if f.style.name=='Part' else 1
            text=f.getPlainText();key='bookmark-'+str(self.counter);self.counter+=1
            self.canv.bookmarkPage(key);self.canv.addOutlineEntry(text,key,level=level,closed=False)
            self.notify('TOCEntry',(level,text,self.page,key))
    def beforeDocument(self):self.counter=0

def pdf(name,md,title,contents=True):
    d=PackDoc(P/(name+'.pdf'),title);story=[]
    story+=[Spacer(1,70),Paragraph(title,styles['TitlePack']),Paragraph('A local textbook and evidence companion for conceptual mastery',styles['Sub']),Spacer(1,22),Paragraph('Reviewed 4 November 2026 · Europe/Rome<br/>Base commit f956f8a14feb3d6bfa483b91ea10384f3bcb84d4<br/>Dirty working tree identified by per-file hashes',styles['Text']),Spacer(1,24),Paragraph('Observations, calculations, interpolation, estimates, assumptions and unavailable values remain distinct. All essential explanations are local. The study pack does not require a running dashboard.',styles['Text']),PageBreak()]
    if contents:
        story.append(Paragraph('Contents',styles['Part']));toc=TableOfContents();toc.levelStyles=[styles['TOCPack'],styles['TOCPack']];story+=[toc,PageBreak()]
    pending_part=False
    for kind,value in blocks(md):
        if kind=='h1':
            if story and not isinstance(story[-1],PageBreak):story.append(PageBreak())
            story.append(Paragraph(inline(value,True),styles['Part']));pending_part=True
        elif kind=='h2':
            if not pending_part and story and not isinstance(story[-1],PageBreak):story.append(PageBreak())
            story.append(Paragraph(inline(value,True),styles['Chapter']));pending_part=False
        elif kind in {'h3','h4'}:story.append(Paragraph(inline(value,True),styles['Sub']))
        elif kind in {'p','li'}:
            story.append(Paragraph(('• ' if kind=='li' else '')+inline(value,True),styles['Text']))
        elif kind=='code':
            for line in value.splitlines():story.append(Paragraph(escape(line).replace(' ','&#160;'),styles['CodeSmall']))
        elif kind=='table':
            n=max(map(len,value));width=d.width/n
            rows=[[Paragraph(inline(c,True),styles['Cell']) for c in row]+['']*(n-len(row)) for row in value]
            t=Table(rows,colWidths=[width]*n,repeatRows=1,hAlign='LEFT')
            t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e4eff0')),('GRID',(0,0),(-1,-1),.3,colors.HexColor('#b7cbd1')),('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),6),('RIGHTPADDING',(0,0),(-1,-1),6),('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6)]));story+=[t,Spacer(1,10)]
        elif kind=='image':
            cap,f=value;im=Image(str(P/f));w=min(d.width,im.imageWidth);h=w*im.imageHeight/im.imageWidth
            if h>365:w*=365/h;h=365
            story.append(KeepTogether([Image(str(P/f),width=w,height=h),Spacer(1,5),Paragraph(inline(cap,True),styles['Caption'])]))
        elif kind=='break':story.append(PageBreak())
    d.multiBuild(story)

def source_companion():
    entries=[]
    originals=json.loads((P/'evidence/snapshot.json').read_text())['files']
    for record in sorted(originals,key=lambda r:r['path']):
        f=P/'source'/record['path']
        rel=f.relative_to(P/'source').as_posix();txt=f.read_text(encoding='utf8',errors='replace');lines=txt.splitlines()
        listing=''.join(f'<span class="line" id="L{i}"><a class="num" href="#L{i}">{i}</a>{html.escape(s)}</span>' for i,s in enumerate(lines,1))
        root='../'*(len(Path(rel).parts))
        page=f'<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>{html.escape(rel)}</title><style>{CSS}</style><main><a href="{root}START_HERE.html">Pack home</a> | <a href="{root}source/_SOURCE_INDEX.html">Source index</a><h1>{html.escape(rel)}</h1><p>{len(lines)} lines · {f.stat().st_size:,} bytes · SHA-256 {content_hash(f)}</p><p>Frozen selected first-party source. Line references use these exact bytes. No license grant is inferred from inclusion.</p>{listing}</main></html>'
        f.with_name(f.name+'.html').write_text(page,encoding='utf8');entries.append((rel,len(lines),f.stat().st_size))
    body='<article><h2>Selected first party reading set</h2><p>This is not a full Git clone or operational backup. It includes source, tests, documentation, dependency manifests and existing font notices. Raw telemetry, dependency trees, caches and credentials are excluded. No top-level repository license was found; this private study copy does not grant redistribution rights. Original notices are preserved. The PDF fonts are embedded subsets; font files are not redistributed separately.</p><table><tr><th>Path</th><th>Lines</th><th>Bytes</th></tr>'+''.join(f'<tr><td><a href="{quote(r,safe="/")}.html">{html.escape(r)}</a></td><td>{n}</td><td>{s:,}</td></tr>' for r,n,s in entries)+'</table></article>'
    (P/'source/_SOURCE_INDEX.html').write_text(html_page('Frozen source companion',body,False).replace('href="START_HERE.html"','href="../START_HERE.html"'),encoding='utf8')

def evidence_index():
    refs=set()
    for f in (P/'chapters').glob('*.md'):
        refs.update(m[1] for m in REF.finditer(f.read_text(encoding='utf8')))
    lines=['# Offline evidence index','The source companion is a selected reading set. Line references resolve to copied text when present. Full public telemetry/replay arrays are deliberately not bundled. For public objects below, use bounded local evidence and the actual-byte digest manifest. A source citation is a route to the original artifact, not a claim that every large original is copied.','## Snapshot and evidence files']
    for f in sorted((P/'evidence').glob('*')):
        if f.is_file():lines.append(f'- [{f.name}](evidence/{f.name}) · {f.stat().st_size:,} bytes')
    records=json.loads((P/'evidence/public-artifact-hashes.json').read_text())['files'];by={x['path']:x for x in records}
    for ref in sorted(refs):
        if (P/'source'/ref).is_file():continue
        lines+=['## '+ref]
        if ref in by:lines+=[f"Reviewed original: {by[ref]['bytes']:,} bytes. SHA-256 `{by[ref]['sha256']}`. Full original omitted from this selected reading set."]
        lines+=['Consult [bounded data and case evidence](evidence/data_metrics_review.json), [forecast evaluation evidence](evidence/forecast_backtest_snapshot.json), [Cup publication snapshot](evidence/cup_publication_snapshot.json), and the [complete public-byte digest list](evidence/public-artifact-hashes.json).']
    md='\n\n'.join(lines);(P/'08_Evidence_Index.md').write_text(md,encoding='utf8');write_html('08_Evidence_Index',md)

def interactive_tools():
    cards=list(csv.DictReader((P/'07_Flashcards.csv').open(encoding='utf8')))
    body='<article><h2>Offline flashcards</h2><p>60 cards. Think first, reveal reasoning, then advance. No data leaves this page.</p><p id="count"></p><h3 id="front"></h3><div id="back" hidden></div><p><button id="show">Reveal answer</button> <button id="prev">Previous</button> <button id="next">Next</button></p></article>'
    script='const cards='+json.dumps(cards).replace('</','<\/')+''';let i=0;function draw(){document.querySelector('#count').textContent=(i+1)+' / '+cards.length+' · '+cards[i].topic;document.querySelector('#front').textContent=cards[i].front;document.querySelector('#back').textContent=cards[i].back;document.querySelector('#back').hidden=true}document.querySelector('#show').onclick=()=>document.querySelector('#back').hidden=false;document.querySelector('#next').onclick=()=>{i=(i+1)%cards.length;draw()};document.querySelector('#prev').onclick=()=>{i=(i+cards.length-1)%cards.length;draw()};draw();'''
    (P/'07_Flashcards.html').write_text(html_page('Offline flashcards',body,False).replace('</body>','')+'<script>'+script+'</script>',encoding='utf8')
    body='''<article><h2>Synthetic unresolved path laboratory</h2><p>This standard browser tool illustrates bounds, not the repository tournament simulator. Three teams have fixed resolved shares of50%,30%,20%; increase unresolved mass and watch why interval endpoints cannot be normalized.</p><label>Unresolved paths percent <input id="u" type="range" min="0" max="100" value="20"></label><p id="label"></p><table><thead><tr><th>Team</th><th>Lower</th><th>Upper</th></tr></thead><tbody id="rows"></tbody></table><p id="sum"></p><p>Each upper bound allocates all unresolved paths to that team separately. Endpoints can represent mutually incompatible completions. Reducing uncertainty requires evidence or rules, not normalization.</p></article>'''
    js='''function draw(){let u=Number(document.querySelector('#u').value)/100;document.querySelector('#label').textContent='Unresolved mass '+(100*u).toFixed(0)+'%';document.querySelector('#rows').innerHTML=[.5,.3,.2].map((w,i)=>'<tr><td>'+['A','B','C'][i]+'</td><td>'+((1-u)*w).toFixed(3)+'</td><td>'+((1-u)*w+u).toFixed(3)+'</td></tr>').join('');document.querySelector('#sum').textContent='Sum lower = '+(1-u).toFixed(3)+'; sum upper = '+(1+2*u).toFixed(3)}document.querySelector('#u').oninput=draw;draw();'''
    (P/'09_Interactive_Lab.html').write_text(html_page('Synthetic bounds laboratory',body,False)+'<script>'+js+'</script>',encoding='utf8')

def main():
    for filename in ['02_Field_Guide.md','04_Workbook.md','04_Answer_Key.md','06_Narration.md']:
        f=P/filename;f.write_text(spaced(f.read_text(encoding='utf8')),encoding='utf8')
    front='''# The regatta repository explained

This textbook explains the specific local repository as reviewed on 4 November 2026. It is intended to help you derive the central quantities, trace their evidence, critique the assumptions and plan improvements independently. It assumes undergraduate mathematics and programming but introduces sailing and telemetry conventions.

## How to use this textbook

Read a chapter's question and worked example before its source-reading route. Use the field guide for recall and the workbook to test yourself. Source citations name frozen files and verified line ranges. HTML links open the local source companion; PDF links may depend on your viewer allowing relative local files, so the same references remain readable as text. Actual evidence and synthetic examples are labelled separately.

The frozen source is a selected first-party reading set with per-file hashes. Git HEAD alone is insufficient because the working tree is dirty. The main text, figures, exercises and source companion work without internet access. Published forecasts are reviewed, not regenerated or improved for this report. No independent official results or new empirical validation are invented.

Notation: x and y are local east/north metres; t is time with explicit seconds or milliseconds; N is scheduled field size; i indexes boats; l indexes legs; I is a performance index, not a probability; p is a probability only where explicitly defined. A source value, reconstructed event, interpolated state, model estimate, scenario assumption and unavailable field occupy different evidence tiers. The glossary in the atlas maps these terms to UI and artifact identifiers.

Use the companion learning routes for one hour, one day or three days. The central conclusion is scoped: this project provides reproducible and inspectable replay, descriptive metrics and provisional conditional forecasts, with material limits from source coverage, small correlated race samples, unverified outcomes, cross-class transfer and unresolved event rules.
'''
    chapters=[(P/'chapters'/x).read_text(encoding='utf8') for x in ['01_data_metrics.md','02_forecasting.md','03_interface.md','04_trust_decisions.md']]
    book=front+'\n\n'+'\n\n'.join(chapters)
    if (P/'chapters/05_figures.md').exists():
        book+='\n\n'+(P/'chapters/05_figures.md').read_text(encoding='utf8')
    (P/'01_Repository_Explained.md').write_text(book,encoding='utf8')
    source_companion();evidence_index();interactive_tools()
    jobs=[('01_Repository_Explained',book,'The regatta repository explained',True),('02_Field_Guide',(P/'02_Field_Guide.md').read_text(),'Regatta repository field guide',False),('04_Workbook',(P/'04_Workbook.md').read_text(),'Regatta repository workbook',True),('04_Answer_Key',(P/'04_Answer_Key.md').read_text(),'Regatta workbook answer key',True)]
    for name,md,title,toc in jobs:write_html(name,md);pdf(name,md,title,toc)
    for name in ['03_Repository_Atlas','05_Learning_Routes','06_Narration','VERIFICATION']:write_html(name,(P/(name+'.md')).read_text(encoding='utf8'))
    links=[('01_Repository_Explained.pdf','Main textbook PDF'),('01_Repository_Explained.html','Searchable self-contained textbook HTML'),('02_Field_Guide.pdf','Field guide PDF'),('03_Repository_Atlas.html','Subsystem atlas and glossary'),('04_Workbook.pdf','Workbook PDF with36 questions'),('04_Answer_Key.pdf','Separate full answer key'),('05_Learning_Routes.html','One hour one day and three day routes'),('06_Narration.html','Narration and oral rehearsal'),('07_Flashcards.html','60 offline flashcards'),('09_Interactive_Lab.html','Synthetic interactive bounds lab'),('source/_SOURCE_INDEX.html','Frozen source companion'),('08_Evidence_Index.html','Evidence and snapshot index'),('VERIFICATION.html','What was verified and limitations')]
    body='<article><h2>Open this first</h2><p>Start with the field guide, then the textbook sailing/data chapters, actual case studies and forecast evidence limits. Use the workbook closed-book. All essential reading needs only a PDF viewer or browser.</p><ul>'+''.join('<li><a href="'+a+'">'+b+'</a></li>' for a,b in links)+'</ul><h2>Before departure</h2><p>Extract the entire ZIP. Copy both the ZIP and extracted directory to your laptop. For a phone/tablet, copy the PDFs or the entire extracted pack for the source companion and HTML. Test with Wi-Fi disabled. The four PDFs and every HTML reading page work without installation. The standard-library concept lab needs Python3; saved output is included. No audio was generated; use the narration script with a device read-aloud feature.</p><h2>Size and scope</h2><p id="pack-size">Exact compressed and uncompressed sizes are in PACK_MANIFEST.json and ZIP_INFO.json beside the archive.</p><p>The optional dashboard was measured at266,118,514 bytes built, including263,706,323 bytes of public data. It is not included. Grid can work without tiles when a prepared application is locally served. New forecast generation requires its separate prepared Python backend and feature dataset. Opening this HTML does not create that service.</p><p>Review date4 November2026; base commit f956f8a, dirty state identified in evidence/snapshot.json. Source copy is selected and preserves notices; no raw telemetry, dependencies, caches or credentials are bundled.</p></article>'
    (P/'START_HERE.html').write_text(html_page('Offline regatta study pack',body,False),encoding='utf8')
    print(json.dumps({'book_words':len(book.split()),'pdfs':len(jobs),'source_files':len(json.loads((P/'evidence/snapshot.json').read_text())['files'])}))
if __name__=='__main__':main()
