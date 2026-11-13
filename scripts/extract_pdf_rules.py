"""Extract and search text from rules PDFs using embedded CMaps."""
from pathlib import Path
import re
import zlib


def extract_pdf_pages(pdf_path: Path) -> list[str]:
    raw = Path(pdf_path).read_bytes()
    objs = {}
    for m in re.finditer(rb'(?:^|\D)(\d+)\s+(\d+)\s+obj\b(.*?)\bendobj', raw, re.DOTALL):
        oid = int(m.group(1))
        body = m.group(3)
        sm = re.search(rb'\bstream\r?\n', body)
        if sm:
            hdr = body[:sm.start()]
            stream_data = body[sm.end():]
            try:
                d = zlib.decompressobj().decompress(stream_data)
                objs[oid] = (hdr, d)
            except Exception:
                objs[oid] = (hdr, stream_data)
        else:
            objs[oid] = (body, b'')

    # Parse CMaps
    cmaps = {}
    for oid, (hdr, d) in objs.items():
        if b'beginbfrange' in d or b'beginbfchar' in d:
            cmap = {}
            for block in re.finditer(rb'beginbfrange(.*?)endbfrange', d, re.DOTALL):
                for m in re.finditer(rb'<([0-9a-fA-F]+)>\s*<([0-9a-fA-F]+)>\s*<([0-9a-fA-F]+)>', block.group(1)):
                    s, e, dst = int(m.group(1), 16), int(m.group(2), 16), int(m.group(3), 16)
                    for i in range(e - s + 1):
                        cmap[s + i] = chr(dst + i)
            for block in re.finditer(rb'beginbfchar(.*?)endbfchar', d, re.DOTALL):
                for m in re.finditer(rb'<([0-9a-fA-F]+)>\s*<([0-9a-fA-F]+)>', block.group(1)):
                    s, dst = int(m.group(1), 16), int(m.group(2), 16)
                    cmap[s] = chr(dst)
            cmaps[oid] = cmap

    # Map font objects to CMaps
    font_to_cmap = {}
    for oid, (hdr, d) in objs.items():
        if re.search(rb'/Type\s*/Font\b', hdr):
            tm = re.search(rb'/ToUnicode\s+(\d+)\s+\d+\s+R', hdr)
            if tm and int(tm.group(1)) in cmaps:
                font_to_cmap[oid] = cmaps[int(tm.group(1))]

    # Find page objects in order
    page_oids = [oid for oid, (hdr, d) in objs.items() if re.search(rb'/Type\s*/Page\b', hdr) and not re.search(rb'/Type\s*/Pages\b', hdr)]
    pages = []
    for oid in page_oids:
        hdr, d = objs[oid]
        rm = re.search(rb'/Resources\s+(\d+)\s+\d+\s+R', hdr)
        r_hdr = objs[int(rm.group(1))][0] if rm and int(rm.group(1)) in objs else hdr
        font_map = {}
        for fm in re.finditer(rb'/([A-Za-z0-9_]+)\s+(\d+)\s+\d+\s+R', r_hdr):
            fname = fm.group(1).decode()
            foid = int(fm.group(2))
            if foid in font_to_cmap:
                font_map[fname] = font_to_cmap[foid]

        cm = re.search(rb'/Contents\s+(\d+)\s+\d+\s+R', hdr)
        cids = [int(cm.group(1))] if cm else []
        if not cids:
            carr = re.search(rb'/Contents\s*\[(.*?)\]', hdr)
            if carr:
                cids = [int(x) for x in re.findall(rb'(\d+)\s+\d+\s+R', carr.group(1))]

        page_pieces = []
        for cid in cids:
            if cid not in objs:
                continue
            cstream = objs[cid][1]
            curr_font = next(iter(font_map.keys()), None)
            for token in re.finditer(rb'/([A-Za-z0-9_]+)\s+[\d\.]+\s+Tf|\[([^\]]*?)\]\s*TJ|\(((?:\\.|[^\\()])*)\)\s*Tj', cstream):
                if token.group(1):
                    curr_font = token.group(1).decode()
                elif token.group(2):
                    cmap = font_map.get(curr_font, {})
                    parts = []
                    for s in re.finditer(rb'\(((?:\\.|[^\\()])*)\)', token.group(2)):
                        raw_bytes = s.group(1).replace(b'\\(', b'(').replace(b'\\)', b')').replace(b'\\\\', b'\\')
                        parts.append(''.join(cmap.get(b, chr(b)) for b in raw_bytes))
                    page_pieces.append(''.join(parts))
                elif token.group(3):
                    cmap = font_map.get(curr_font, {})
                    raw_bytes = token.group(3).replace(b'\\(', b'(').replace(b'\\)', b')').replace(b'\\\\', b'\\')
                    page_pieces.append(''.join(cmap.get(b, chr(b)) for b in raw_bytes))
        pages.append(' '.join(page_pieces))
    return pages


def search_rules():
    rules_dir = Path('.forecast/rules')
    keywords = [
        '24.2', 'article 24', 'hull', '21.1', 'article 21', 'crew', 'female',
        'cyclor', 'tie', 'sail-off', 'head-to-head', 'semi-final', 'final'
    ]
    for pdf in rules_dir.glob('*.pdf'):
        pages = extract_pdf_pages(pdf)
        print(f"\n==================== {pdf.name} ({len(pages)} pages) ====================")
        for idx, p in enumerate(pages):
            for para in re.split(r'\n{2,}|\.\s+', p):
                para_clean = ' '.join(para.split())
                if any(k in para_clean.lower() for k in ['24.2', 'article 24', 'article 21', '21.1', 'tie-break', 'tie break', 'sail-off', 'head-to-head']):
                    if len(para_clean) > 20:
                        print(f"  [p.{idx+1}] {para_clean[:220]}...")


if __name__ == '__main__':
    search_rules()
