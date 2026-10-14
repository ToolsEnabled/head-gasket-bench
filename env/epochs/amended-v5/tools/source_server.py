"""Bind the tool package to a closed, verified source snapshot before importing it.

Project modules execute compiled verified bytes, ignoring their normal import
cache. Bootstrap hashes describe file custody, not a loaded-code attestation.
Installed libraries and the interpreter need separate deployment qualification.
This source binder is not an operating-system sandbox or physical admission.
"""
import argparse
import copy
import hashlib
import importlib
import importlib.abc
import importlib.util
import json
import re
import sys
import threading
from contextlib import contextmanager
from pathlib import Path

SOURCE_PATHS={
    'hgj':'hgj/__init__.py',
    **{'hgj.'+name:'hgj/'+name+'.py' for name in (
        'codec','api','geometry','initial_conditions','action_conditions',
        'action_domains','game','backends','exact_imports','mcp','repair_scoring','human_time','repair_report','procedure_actions','removal_policy','benchmark_geometry','checkpoints')},
}
MAX_FILE_BYTES=131072
MAX_SOURCE_BYTES=524288
MAX_RECORD_BYTES=134217728
_LOCK=threading.RLock()
DIRECT_SERVER_BLOCKER='Managed process control remains unqualified after owned-child EPERM; source-bound server/replay start withheld'


def canonical(value):
    return (json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)+'\n').encode()


def sha(data):return hashlib.sha256(data).hexdigest()


def read_source(root,relative,limit):
    path=root/relative
    if Path(relative).is_absolute() or '..' in Path(relative).parts:
        raise ValueError('Invalid environment source path')
    for part in (path,*path.parents):
        if part==root:break
        if part.is_symlink():raise ValueError('Environment source links are forbidden')
    if not path.is_file() or path.stat().st_size>limit:
        raise ValueError('Environment source file unavailable or oversized')
    with path.open('rb') as stream:data=stream.read(limit+1)
    if len(data)>limit:raise ValueError('Environment source read exceeds size bound')
    return data


class SourceRuntime(importlib.abc.MetaPathFinder,importlib.abc.Loader):
    def __init__(self,root,manifest_path,expected_sha256):
        self.root=Path(root).resolve()
        path=Path(manifest_path)
        if path.is_symlink() or not path.is_file() or path.stat().st_size>MAX_FILE_BYTES:
            raise ValueError('Environment source manifest unavailable or oversized')
        with path.open('rb') as stream:raw=stream.read(MAX_FILE_BYTES+1)
        if len(raw)>MAX_FILE_BYTES or not isinstance(expected_sha256,str) or not re.fullmatch('[a-f0-9]{64}',expected_sha256) or sha(raw)!=expected_sha256:
            raise ValueError('Environment source manifest hash mismatch')
        manifest=json.loads(raw)
        if not isinstance(manifest,dict) or set(manifest)!={'schema','sources','bootstrap'} or manifest['schema']!='hgj/environment-source/v1':
            raise ValueError('Invalid environment source manifest')
        sources=manifest['sources'];bootstrap=manifest['bootstrap']
        if not isinstance(sources,dict) or set(sources)!=set(SOURCE_PATHS):
            raise ValueError('Environment source closure differs from production package')
        if not isinstance(bootstrap,dict) or set(bootstrap)!={'path','sha256'} or bootstrap['path']!='tools/source_server.py' or not isinstance(bootstrap['sha256'],str) or not re.fullmatch('[a-f0-9]{64}',bootstrap['sha256']):
            raise ValueError('Invalid source bootstrap binding')
        bootstrap_bytes=read_source(self.root,bootstrap['path'],MAX_FILE_BYTES)
        if sha(bootstrap_bytes)!=bootstrap['sha256']:raise ValueError('Environment bootstrap source hash mismatch')
        self.codes={};total=len(bootstrap_bytes)
        for name,relative in sorted(SOURCE_PATHS.items()):
            item=sources[name]
            if not isinstance(item,dict) or set(item)!={'path','sha256'} or item['path']!=relative or not isinstance(item['sha256'],str) or not re.fullmatch('[a-f0-9]{64}',item['sha256']):
                raise ValueError('Invalid environment source member')
            data=read_source(self.root,relative,MAX_FILE_BYTES);total+=len(data)
            if sha(data)!=item['sha256']:raise ValueError('Environment source member hash mismatch: '+name)
            if total>MAX_SOURCE_BYTES:raise ValueError('Environment source closure exceeds size bound')
            self.codes[name]=compile(data,'<environment:'+name+'>','exec',dont_inherit=True)
        self.executed_modules=set();self._module_objects={};self._owner_thread=None;self._ready=False
        self._identity={'schema':'hgj/environment-source-identity/v1',
            'qualification':'verified-module-source-closure',
            'source_manifest_sha256':expected_sha256,'source_manifest_body_sha256':sha(canonical(manifest)),
            'sources':copy.deepcopy(sources),'bootstrap':copy.deepcopy(bootstrap),
            'bootstrap_qualification':'source-file-custody-only',
            'interpreter':{'implementation':sys.implementation.name,'version':list(sys.version_info[:3]),
                           'cache_tag':sys.implementation.cache_tag}}

    @property
    def identity(self):return copy.deepcopy(self._identity)

    def require_active(self):
        if not self._ready or self._owner_thread!=threading.get_ident():
            raise ValueError('Environment source runtime context is not active')

    def require_module(self,name,scope):
        self.require_active();module=self._module_objects.get(name)
        if module is None or module.__dict__ is not scope or scope.get('__loader__') is not self or sys.modules.get(name) is not module:
            raise ValueError('Environment source runtime does not own this module')

    def require_deployment(self):
        self.require_active()
        if DIRECT_SERVER_BLOCKER:raise RuntimeError(DIRECT_SERVER_BLOCKER)

    def owns(self,name):return name=='hgj' or name.startswith('hgj.')

    def find_spec(self,fullname,path=None,target=None):
        if fullname in self.codes:
            return importlib.util.spec_from_loader(fullname,self,origin='<environment:'+fullname+'>',is_package=fullname=='hgj')
        if self.owns(fullname):raise ModuleNotFoundError('Unpinned environment module: '+fullname)
        return None

    def create_module(self,spec):return None

    def exec_module(self,module):
        module.__file__=str(self.root/SOURCE_PATHS[module.__name__])
        if module.__name__=='hgj':module.__path__=[]
        exec(self.codes[module.__name__],module.__dict__)
        self.executed_modules.add(module.__name__);self._module_objects[module.__name__]=module

    @contextmanager
    def active(self):
        with _LOCK:
            if self._owner_thread is not None:raise ValueError('Environment source runtime is already active')
            self._owner_thread=threading.get_ident();self._ready=False;self._module_objects={}
            previous={name:module for name,module in sys.modules.copy().items() if self.owns(name)}
            for name in previous:sys.modules.pop(name,None)
            sys.meta_path.insert(0,self);self.executed_modules.clear()
            try:
                # Execute definitions from the complete closure before any model
                # initialization or action. There is no project bytecode fallback.
                for name in sorted(self.codes):importlib.import_module(name)
                self._ready=True
                yield self
            finally:
                for name in list(sys.modules):
                    if self.owns(name):sys.modules.pop(name,None)
                sys.modules.update(previous);sys.meta_path.remove(self)
                self._ready=False;self._owner_thread=None;self._module_objects={}


def replay_manifest(record_path,manifest_path,out,runtime,manifest_sha256):
    if type(runtime) is not SourceRuntime:raise ValueError('Environment source runtime context is required')
    runtime.require_deployment()
    path=Path(record_path)
    if not path.is_file() or path.stat().st_size>MAX_RECORD_BYTES:raise ValueError('Replay record unavailable or oversized')
    with path.open('rb') as stream:raw=stream.read(MAX_RECORD_BYTES+1)
    if len(raw)>MAX_RECORD_BYTES:raise ValueError('Replay record exceeds size bound')
    record=json.loads(raw);identity=runtime.identity
    # Source mismatch precedes project imports and backend constructors.
    if record.get('schema')!='hgj/run/v2' or record.get('environment_source')!=identity or record.get('environment_source_sha256')!=sha(canonical(identity)):
        raise ValueError('Replay environment source identity mismatch')
    from hgj.game import replay
    from hgj.backends import load_manifest
    config,joint,soak=load_manifest(manifest_path,expected_sha256=manifest_sha256)
    if record['config']!=config:raise ValueError('Replay manifest differs from recorded inputs')
    result=replay(record,joint=joint,soak=soak,source_runtime=runtime)
    with open(out,'xb') as stream:stream.write(canonical(result))
    return result


def main():
    # No argument, source manifest or historical receipt overrides this hold.
    if DIRECT_SERVER_BLOCKER:raise RuntimeError(DIRECT_SERVER_BLOCKER)
    parser=argparse.ArgumentParser()
    parser.add_argument('--source-root',required=True);parser.add_argument('--source-manifest',required=True)
    parser.add_argument('--source-sha256',required=True);parser.add_argument('--manifest',required=True)
    parser.add_argument('--manifest-sha256',required=True);parser.add_argument('--out',required=True);parser.add_argument('--record')
    args=parser.parse_args();runtime=SourceRuntime(args.source_root,args.source_manifest,args.source_sha256)
    with runtime.active():
        if args.record:replay_manifest(args.record,args.manifest,args.out,runtime,args.manifest_sha256)
        else:
            from hgj.mcp import run_manifest
            run_manifest(args.manifest,args.out,runtime,args.manifest_sha256)


if __name__=='__main__':
    try:main()
    except Exception as error:
        print('Source-bound environment stopped: '+type(error).__name__+': '+str(error),file=sys.stderr)
        raise SystemExit(1)
