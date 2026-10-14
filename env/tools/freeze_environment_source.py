"""Write a small source manifest from reviewed production files; no code launch."""
import argparse
import json
import hashlib
from pathlib import Path
# Standalone generator: no ordinary project import/cache supplies freeze rules.
SOURCE_PATHS={'hgj':'hgj/__init__.py',**{'hgj.'+name:'hgj/'+name+'.py' for name in (
    'codec','api','geometry','initial_conditions','action_conditions','action_domains',
    'game','backends','exact_imports','mcp','repair_scoring','human_time','repair_report','procedure_actions','removal_policy','benchmark_geometry','checkpoints')}}
MAX_FILE_BYTES=131072
MAX_SOURCE_BYTES=524288


def sha(data):return hashlib.sha256(data).hexdigest()


def canonical(value):
    return (json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)+'\n').encode()


def read_source(root,relative,limit):
    path=root/relative
    for part in (path,*path.parents):
        if part==root:break
        if part.is_symlink():raise ValueError('Environment source links are forbidden')
    if not path.is_file() or path.stat().st_size>limit:raise ValueError('Environment source unavailable or oversized')
    with path.open('rb') as stream:data=stream.read(limit+1)
    if len(data)>limit:raise ValueError('Environment source exceeds size bound')
    return data


def snapshot(root):
    root=Path(root).resolve();sources={};total=0
    for name,relative in sorted(SOURCE_PATHS.items()):
        data=read_source(root,relative,MAX_FILE_BYTES);total+=len(data)
        sources[name]={'path':relative,'sha256':sha(data)}
    bootstrap='tools/source_server.py';data=read_source(root,bootstrap,MAX_FILE_BYTES);total+=len(data)
    if total>MAX_SOURCE_BYTES:raise ValueError('Environment source closure exceeds size bound')
    return {'schema':'hgj/environment-source/v1','sources':sources,
            'bootstrap':{'path':bootstrap,'sha256':sha(data)}}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--root',required=True);parser.add_argument('--out',required=True)
    args=parser.parse_args();manifest=snapshot(args.root);raw=canonical(manifest)
    with open(args.out,'xb') as stream:stream.write(raw)
    print(json.dumps({'manifest_sha256':sha(raw),'source_count':len(manifest['sources']),
                      'qualification':'declared source custody; deployment and physical review required'},sort_keys=True))


if __name__=='__main__':main()
