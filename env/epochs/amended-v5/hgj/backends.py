"""Trusted backend admission. No fixture or descriptor flag can award physical credit."""
import json
import copy
import math
import re
import hashlib
from pathlib import Path
from .codec import file_digest, digest
from .exact_imports import ExactImports, pinned_bytes

NON_SCORE={'UNQUALIFIED','UNRESOLVED','RESOURCE_STOP','INVALID_INPUT'}
# Agreed L2 protocol. Main hold is the owner requirement; other holds are L2
# design estimates, subject to validated model domain and admission.
AGREED_PROTOCOL={'main_rpm':3000,'main_duration_s':3600,'idle_hold_s':30,'redline_hold_s':10,'redline_rpm':7000}


def validate_score(s, physical=False, expected_protocol=None):
    if not isinstance(s,dict) or s.get('schema')!='hgj/soak-result/v1': raise ValueError('Invalid soak schema')
    if s.get('status') in NON_SCORE:
        if s.get('pass') is not None or s.get('time_to_failure_s') is not None or s.get('qualification')!='unqualified':
            raise ValueError('Non-score cannot report physical failure')
        if not isinstance(s.get('cause'),str) or not s['cause']: raise ValueError('Non-score needs a readable blocker')
        return
    if type(s.get('pass')) is not bool: raise ValueError('Missing pass value')
    if physical and (s.get('qualification')!='validated-physics' or s.get('status') not in ('PASS','FAIL')):
        raise ValueError('Unqualified physical result')
    if physical and ((s['status']=='PASS') is not s['pass']): raise ValueError('Status/pass mismatch')
    if physical and not all(re.fullmatch('[a-f0-9]{64}',s.get(k,'') or '') for k in ('model_sha256','evidence_sha256')):
        raise ValueError('Physical result missing source/evidence pins')
    protocol=s.get('protocol',{})
    keys=('main_rpm','main_duration_s','idle_hold_s','redline_hold_s','redline_rpm')
    if not all(type(protocol.get(k)) in (int,float) and math.isfinite(protocol[k]) and protocol[k]>0 for k in keys):
        raise ValueError('Incomplete soak protocol')
    if protocol['main_rpm']!=3000 or protocol['main_duration_s']<3600: raise ValueError('Owner main-soak requirement not met')
    if physical and protocol!=(expected_protocol or AGREED_PROTOCOL): raise ValueError('Soak protocol differs from agreed pinned holds')
    duration=s.get('simulated_duration_s')
    if type(duration) not in (int,float) or not math.isfinite(duration) or duration<0: raise ValueError('Invalid duration')
    if s['pass']:
        if s.get('time_to_failure_s') is not None or s.get('cause') is not None or duration<sum(protocol[k] for k in ('main_duration_s','idle_hold_s','redline_hold_s')):
            raise ValueError('Incomplete successful soak')
    else:
        t=s.get('time_to_failure_s')
        if type(t) not in (int,float) or not math.isfinite(t) or not 0<=t<=duration or not s.get('cause'):
            raise ValueError('Failure has no valid physical cause/time')
        if physical:
            bracket=s.get('failure_time_bracket_s')
            if not isinstance(bracket,list) or len(bracket)!=2 or not all(type(v) in (int,float) and math.isfinite(v) for v in bracket) or not 0<=bracket[0]<=t<=bracket[1]<=duration or not isinstance(s.get('witness'),dict) or not s['witness']:
                raise ValueError('Failure lacks bracket or witness')


class Backend:
    """Compiles exactly hash-verified source bytes, avoiding stale bytecode.

    Trusted modules may import preinstalled standard/scientific dependencies. All
    project/data dependencies must be listed and their current bytes pinned.
    The admission receipt is coordinator configuration, unavailable to subjects.
    """
    def __init__(self, descriptor, admission):
        self.descriptor=copy.deepcopy(descriptor)
        self.descriptor_sha256=digest(self.descriptor)
        self.admission_sha256=digest(admission)
        self.expected_protocol=copy.deepcopy(admission.get('expected_protocol',AGREED_PROTOCOL))
        if descriptor.get('schema')!='hgj/backend/v1' or descriptor.get('kind') not in ('joint','soak'):
            raise ValueError('Invalid backend descriptor')
        if descriptor.get('qualification')!='validated-physics': raise ValueError('Fixture cannot be admitted')
        if admission.get('schema')!='hgj/admission/v1' or admission.get('status')!='validated-physics':
            raise ValueError('Missing independent physical admission receipt')
        if admission.get(descriptor['kind']+'_descriptor_sha256')!=digest(descriptor):
            raise ValueError('Backend not pinned by admission')
        for k in ('geometry_sha256','joint_descriptor_sha256','soak_descriptor_sha256','validation_sha256'):
            if not re.fullmatch('[a-f0-9]{64}',admission.get(k,'')): raise ValueError('Incomplete physical admission pins')
        self._verify()
        ExactImports(self.descriptor.get('dependencies',[]))
        self.code=compile(pinned_bytes({'path':self.descriptor['module'],'sha256':self.descriptor['sha256']}),
                          self.descriptor['module'],'exec')

    def _verify(self):
        if digest(self.descriptor)!=self.descriptor_sha256:
            raise ValueError('Backend descriptor changed after admission')
        for item in [{'path':self.descriptor['module'],'sha256':self.descriptor['sha256']},*self.descriptor.get('dependencies',[])]:
            pinned_bytes(item)

    def _call(self, name, *args):
        runtime=globals().get('__loader__')
        if hasattr(runtime,'require_deployment'):
            runtime.require_module(__name__,globals());runtime.require_deployment()
        self._verify()
        # Serialized arguments/results own all mutable project/model state.
        # Fresh declared project modules prevent hidden globals surviving either
        # a successful call or a rolled-back attempt. This is no sandbox for
        # trusted code: external side effects and installed-library globals are
        # forbidden by the facade contract and require independent source review.
        imports=ExactImports(self.descriptor.get('dependencies',[]))
        scope={'__name__':'hgj_trusted_'+self.descriptor['kind'],'__file__':self.descriptor['module']}
        with imports.active():
            exec(self.code,scope)
            return scope[name](*args)
    def initialize(self, config): return self._call('initialize',config)
    def apply(self, state, operation): return self._call('apply',state,operation)
    def score(self, job):
        s=self._call('score',job); validate_score(s,physical=True,expected_protocol=self.expected_protocol); return s


MAX_MANIFEST_BYTES=65536
MAX_INPUT_BYTES=16777216
MAX_INPUT_TOTAL_BYTES=67108864
MAX_INPUT_FILES=32


def read_json_bytes(path,limit):
    path=Path(path)
    if not path.is_file() or path.stat().st_size>limit:raise ValueError('JSON input unavailable or oversized')
    with path.open('rb') as stream:data=stream.read(limit+1)
    if len(data)>limit:raise ValueError('JSON input exceeds size bound')
    return data


def load_manifest(path,expected_sha256=None):
    """Resolve and verify a trusted run manifest; tool callers cannot select it."""
    path=Path(path).resolve();raw=read_json_bytes(path,MAX_MANIFEST_BYTES);raw_pin=hashlib.sha256(raw).hexdigest()
    if expected_sha256 is not None and (not isinstance(expected_sha256,str) or not re.fullmatch('[a-f0-9]{64}',expected_sha256) or raw_pin!=expected_sha256):
        raise ValueError('Job manifest raw hash mismatch')
    m=json.loads(raw);root=path.parent
    if m.get('schema')!='hgj/manifest/v1': raise ValueError('Invalid run manifest')
    if not isinstance(m.get('inputs'),dict) or not m['inputs'] or len(m['inputs'])>MAX_INPUT_FILES:raise ValueError('Invalid manifest input set')
    inputs={};pins={'manifest_sha256':raw_pin,'manifest_body_sha256':digest(m)};total=0
    for name,item in m['inputs'].items():
        p=(root/item['path']).resolve()
        data=read_json_bytes(p,MAX_INPUT_BYTES);total+=len(data)
        if total>MAX_INPUT_TOTAL_BYTES:raise ValueError('Manifest input total exceeds size bound')
        if hashlib.sha256(data).hexdigest()!=item['sha256']:raise ValueError('Input hash mismatch: '+name)
        inputs[name]=json.loads(data);pins[name+'_sha256']=item['sha256'];pins[name+'_body_sha256']=digest(inputs[name])
    c={'schema':'hgj/config/v1',**inputs,'variant_id':m['variant_id'],'factors':m['factors'],'identity':pins}
    joint=soak=None
    if m.get('admission'):
        if c['factors'].get('turn_budget_unit')!='job-tool-action-attempts':
            raise ValueError('Physical runs require the owner-selected action turn budget unit')
        if c.get('policy',{}).get('public_observation')!='technician-v2':
            raise ValueError('Physical runs require the reviewed public observation policy')
        a=inputs['admission']
        if a['geometry_sha256']!=pins['geometry_sha256']: raise ValueError('Geometry is not admitted')
        if not pins.get('initial_conditions_sha256') or a.get('initial_conditions_sha256')!=pins['initial_conditions_sha256']:
            raise ValueError('Physical runs require independently pinned initial conditions')
        from .action_domains import ActionDomains
        ActionDomains(c) # Validate private operation admission before source compilation.
        joint=Backend(inputs['joint_descriptor'],a); soak=Backend(inputs['soak_descriptor'],a)
    return c,joint,soak
