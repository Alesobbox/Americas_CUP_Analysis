"""Create a manifest and ZIP, then extract to a different directory for testing."""
from pathlib import Path
import hashlib,json,zipfile,datetime,logging
P=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    files=sorted(f for f in P.rglob('*') if f.is_file() and '__pycache__' not in f.parts and f.name!='PACK_MANIFEST.json')
    records=[{'path':f.relative_to(P).as_posix(),'bytes':f.stat().st_size,'sha256':sha(f)} for f in files]
    manifest={'review_date':'2026-11-04','provenance':'evidence/snapshot.json','manifest_policy':'Every payload file is hashed by actual bytes. This manifest cannot hash itself; its size is included in the total. The ZIP byte hash is in the adjacent ZIP_INFO.json.','file_count_including_manifest':len(files)+1,'total_uncompressed_bytes':0,'files':records}
    target=P/'PACK_MANIFEST.json'
    for _ in range(6):
        target.write_text(json.dumps(manifest,indent=2),encoding='utf8')
        total=sum(x['bytes'] for x in records)+target.stat().st_size
        if total==manifest['total_uncompressed_bytes']:break
        manifest['total_uncompressed_bytes']=total
    archive=P.parent/'2026-11-04_Offline_Study_Pack.zip'
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for f in files+[target]:z.write(f,P.name+'/'+f.relative_to(P).as_posix())
    dest=P.parent/'.qa-2026-11-04'/('extracted-'+datetime.datetime.now().strftime('%H%M%S'))
    dest.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        z.extractall(dest)
    info={'archive':str(archive),'archive_bytes':archive.stat().st_size,'archive_sha256':sha(archive),'uncompressed_bytes':total,'files':len(files)+1,'extracted_pack':str(dest/P.name)}
    (P.parent/'ZIP_INFO.json').write_text(json.dumps(info,indent=2),encoding='utf8')
    logging.basicConfig(level=logging.INFO);logging.info(json.dumps(info))
if __name__=='__main__':main()
