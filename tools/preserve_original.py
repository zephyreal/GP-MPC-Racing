"""Vendor a user-supplied original archive byte-for-byte, without running its code."""
import argparse,hashlib,json
from pathlib import Path
from zipfile import ZipFile

def preserve(archive,destination):
    archive=Path(archive);destination=Path(destination);destination.mkdir(parents=True,exist_ok=True);records=[]
    with ZipFile(archive) as z:
        items=z.infolist()
        if len(items)>1000 or sum(i.file_size for i in items)>20_000_000:raise ValueError('Archive limits exceeded')
        for item in items:
            p=Path(item.filename)
            if p.is_absolute() or '..' in p.parts or '\\' in item.filename:raise ValueError('Invalid archive path')
            if item.is_dir():continue
            data=z.read(item);out=destination/p;out.parent.mkdir(parents=True,exist_ok=True);out.write_bytes(data)
            records.append({'path':p.as_posix(),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})
    manifest={'source_archive':archive.name,'archive_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'policy':'Original file bytes unchanged; adapters live outside this directory.','files':records}
    (destination/'MANIFEST.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    return manifest
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('archive');parser.add_argument('--destination',default='matlab_original');args=parser.parse_args();result=preserve(args.archive,args.destination);print(str(len(result['files']))+' original files preserved')
