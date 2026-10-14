import copy
import math
import re
from .api import DEFINITIONS, validate
from .codec import digest, canonical
from .geometry import validate_geometry
from .initial_conditions import initial_values
from .action_domains import ActionDomains, MECHANICAL
from . import procedure_actions, benchmark_geometry


class Refusal(ValueError): pass

ACTION_TURN_UNIT='job-tool-action-attempts'


def service_terms(text):
    # A technician's "head bolts" must match "head-bolt" source headings.
    return {w[:-1] if len(w)>3 and w.endswith('s') else w for w in re.findall(r'[a-z0-9]+',text.lower())}


class Game:
    def __init__(self, config, joint=None, soak=None, environment_source=None, source_runtime=None):
        if environment_source is not None:raise ValueError('Environment source identity requires an active runtime context')
        self._source_runtime=source_runtime
        self.environment_source=self._source_identity()
        self.config = copy.deepcopy(config)
        self.procedure_scoring = 'repair_scoring' in self.config
        if self.procedure_scoring:
            from .human_time import validate_policy
            if joint is not None or soak is not None:
                raise ValueError('Procedure scoring does not accept engine or soak backends')
            validate_policy(self.config['repair_scoring']['human_time_policy'])
        factors=self.config['factors']
        if type(factors.get('service_info')) is not bool or type(factors.get('feedback')) is not bool:
            raise ValueError('Factors must be boolean')
        for k in ('turn_budget','tool_call_limit'):
            if type(factors.get(k)) is not int or factors[k]<1: raise ValueError('Invalid budget')
        if factors.get('turn_budget_unit') not in (None,ACTION_TURN_UNIT):raise ValueError('Unknown turn budget unit')
        if len({v['id'] for v in self.config['variants']})!=len(self.config['variants']): raise ValueError('Duplicate variants')
        self.part_defs = validate_geometry(self.config['geometry'])
        self.fasteners = {f['id']: f for f in self.config['geometry']['fasteners']}
        self.joint_backend, self.soak_backend = joint, soak
        self.records, self.score, self.finished = [], None, False
        self.config_hash = digest(self.config)
        variant = next(v for v in self.config['variants'] if v['id'] == self.config['variant_id'])
        initial=initial_values(self.config,self.part_defs,self.fasteners,variant)
        self.action_domains=ActionDomains(self.config)
        self.physical_conditions=(not self.procedure_scoring and
                                  (self.config['geometry']['qualification']=='cad-derived'
                                   or self.config.get('admission',{}).get('status')=='validated-physics'))
        if self.physical_conditions and self._source_runtime is not None:self._source_runtime.require_deployment()
        self._active_action=None
        self._attempt_effects=None
        self.state = {'schema': 'hgj/job-state/v1', 'identity': {'config_sha256': self.config_hash, **self.config.get('identity', {})},
                      'variant_id': variant['id'], 'revision': 0, 'simulated_labor_s': 0,
                      'parts': {pid: {'location': 'assembly' if p['installed'] else 'supply', 'damaged': None if 'condition' in p and p['condition'] is None else False}
                                for pid, p in self.part_defs.items()},
                      'bolts': {}, 'surfaces': {}, 'gasket': {'active_id': self.role('gasket_old'), 'type': 'old', 'orientation': 'up'},
                      'timing': {'cam_phase_deg': 0, 'crank_phase_deg': 0, 'checks': []},
                      'action_history': [], 'joint': None}
        for f in (self.fasteners.values() if initial is None else []):
            required=f.get('service_required',True)
            self.state['bolts'][f['id']] = {'turns': f['initial_engagement_turns'], 'torque_N_m': self.config['policy']['initial_torque_N_m'][f['group']] if required else None,
                                          'thread_clean': False, 'thread_oiled': False, 'washer_oiled': False,
                                          'stretch_mm': (variant.get('stretched_bolts', {}).get(str(f['sequence_index']), 0) if f['group'] == 'head' else 0) if required else None,
                                          **({'qualification':'retained condition unresolved','unknown_fields':copy.deepcopy(f.get('unknown_fields',[]))} if not required else {}),
                                          'history': []}
        for sid in (('head_face', 'block_deck', 'cover_face') if initial is None else []):
            self.state['surfaces'][sid] = {'residue_fraction': 1, 'dry': False, 'debris_count': 0, 'damaged': False,
                                         'warpage_m': variant.get('warpage_m', {}).get(sid, 0.00002),
                                         'roughness_ra_um': 0.5}
        if initial is not None:
            self.state.update(initial)
            self.state['condition_sources']=copy.deepcopy(self.config['initial_conditions']['field_sources'])
        self.variant = variant
        procedure_actions.initialize(self, variant)
        benchmark_geometry.initialize(self)
        self.public_ids={pid:('stock_'+digest({'body_id':pid,'variant':variant['id']})[:12]
                              if self.config['policy'].get('public_observation')=='technician-v2'
                              and (p['role'] in ('gasket_new','gasket_wrong')
                                   or self.config.get('benchmark_task') and not p['installed']) else pid) for pid,p in self.part_defs.items()}
        if len(set(self.public_ids.values()))!=len(self.public_ids): raise ValueError('Public body ID collision')
        self.public_to_body={public:pid for pid,public in self.public_ids.items()}
        if self.physical_conditions:
            for kind,backend in (('joint',joint),('soak',soak)):
                if backend is not None:self._bound_backend(kind,backend)
        if joint is not None:
            self.state['joint'] = joint.initialize(copy.deepcopy(self.config))
            self._check_joint(self.state['joint'])
            if initial is None and self.state['joint']['head_warpage_m'] is None:
                self.state['surfaces']['head_face']['warpage_m']=None
        self._refresh_identity(self.state)
        if self.procedure_scoring:
            from .repair_scoring import validate_reference
            self._repair_initial = copy.deepcopy(self.state)
            self._time_charge_cache = {}
            validate_reference(self.config, self._repair_initial)
            from .repair_scoring import score_repair
            self.score = score_repair(self.config, self._repair_initial, [], self.state,
                                      _charge_cache=self._time_charge_cache)

    def _source_identity(self):
        runtime=self._source_runtime
        if runtime is None:
            if getattr(self,'environment_source',None) is not None:
                raise ValueError('Environment source identity has no active runtime owner')
            return None
        if runtime is not globals().get('__loader__'):raise ValueError('Environment source runtime does not own Game')
        runtime.require_module(__name__,globals())
        identity=runtime.identity
        if canonical(getattr(self,'environment_source',identity))!=canonical(identity):
            raise ValueError('Environment source identity differs from active runtime')
        return identity

    def _position_map(self):
        # These are service-position bindings, never replacement-body geometry.
        return {pid:{'body_id':pid,'service_position_id':f.get('original_id',pid),
                     'group':f['group'],'sequence_index':f.get('sequence_index'),
                     'washer_id':f['washer_id'],'holds':copy.deepcopy(f['holds']),
                     'service_required':f.get('service_required',True),
                     'spec_ref':f.get('spec_ref'),'position_source_id':f['source_id']}
                for pid,f in self.fasteners.items()}

    def _refresh_identity(self, state):
        if self._source_runtime is not None:
            state['identity'].update(config_sha256=self.config_hash,
                selected_variant_sha256=digest(self.variant),
                environment_source_sha256=digest(self.environment_source))
            state['fastener_mapping']=self._position_map()
            state['identity']['fastener_mapping_sha256']=digest(state['fastener_mapping'])
        state['identity']['joint_state_sha256']=digest(state['joint'])
        state['identity']['action_history_sha256']=digest(state['action_history'])

    def role(self, name):
        matches = [p['id'] for p in self.part_defs.values() if p['role'] == name]
        if len(matches) != 1: raise ValueError('Ambiguous singleton role: ' + name)
        return self.bound_part(matches[0])

    def bound_part(self, pid):
        return getattr(self, 'state', {}).get('service_replacements', {}).get(pid, pid)

    def public_id(self, body_id): return self.public_ids[body_id]

    def budget(self,attempted=None):
        if self.config['factors'].get('turn_budget_unit')!=ACTION_TURN_UNIT:return None
        attempted=len(self.records) if attempted is None else attempted
        limit=self.config['factors']['turn_budget']
        return {'unit':ACTION_TURN_UNIT,'limit':limit,'used':min(attempted,limit),
                'attempted_calls':attempted,'exhausted':attempted>=limit}

    def _resolve_arguments(self,args):
        out=copy.deepcopy(args)
        for key in ('part_id','replacement_id','target'):
            if key in out:
                if key=='target' and out[key] in self.state['surfaces']: continue
                self._require(out[key] in self.public_to_body,'Unknown component identifier')
                out[key]=self.public_to_body[out[key]]
        return out

    def _public_result(self,value):
        if isinstance(value,str): return self.public_ids.get(value,value)
        if isinstance(value,list): return [self._public_result(v) for v in value]
        if isinstance(value,dict):
            public={}
            for k,v in value.items():
                if k=='score':
                    if v is not None and not self.procedure_scoring and self.config['policy'].get('public_observation')=='technician-v2':
                        public[k]={'status':v.get('status','scored'),
                                   **{field:v.get(field) for field in ('qualification','pass','time_to_failure_s','cause')}}
                    else: public[k]=v
                else: public[k]=self._public_result(v)
            return public
        return value

    def tools(self):
        return [{'name': n, 'description': d, 'inputSchema': copy.deepcopy(s),
                 'annotations': {'readOnlyHint': n in ('look','inspect','measure','search_service_info'),
                                 'destructiveHint': False, 'openWorldHint': False}}
                for n,d,s in DEFINITIONS
                if (n != 'search_service_info' or self.config['factors']['service_info'])
                and (n not in procedure_actions.EXTRA_TOOLS or self.config.get('benchmark_task'))
                and (n not in benchmark_geometry.TOOLS or self.config.get('benchmark_removal'))]

    def _require(self, condition, message):
        if not condition: raise Refusal(message)

    def _bound_backend(self,kind,backend):
        from .backends import Backend
        self._require(type(backend) is Backend,'Physical '+kind+' requires the exact source backend')
        admission=self.config.get('admission',{})
        self._require(backend.admission_sha256==digest(admission),'Physical backend admission differs from the game')
        self._require(backend.descriptor.get('kind')==kind
            and digest(backend.descriptor)==admission.get(kind+'_descriptor_sha256'),
            'Physical backend descriptor differs from admitted '+kind)

    def _part(self, pid):
        self._require(pid in self.part_defs, 'Unknown part')
        return self.state['parts'][pid]

    def _accessible(self, pid):
        def current_body(source_id):
            # A replacement inherits the service position and all its edges.
            return self.bound_part(next((f['id'] for f in self.fasteners.values() if f.get('original_id',f['id'])==source_id),source_id))
        source_id=self.fasteners.get(pid,{}).get('original_id',self.part_defs[pid].get('replacement_for',pid))
        return all(self.state['parts'][current_body(x)]['location'] != 'assembly'
                   for x in self.part_defs[source_id]['requires_removed'])

    def _surface_access(self, sid):
        self._require(sid in self.state['surfaces'], 'Unknown surface')
        if sid=='cover_face':
            self._require(self.state['parts'][self.role('valve_cover')]['location']!='assembly','Cover sealing face is obstructed')
            return
        self._require(self.state['parts'][self.role('head')]['location'] != 'assembly' and
                      self.state['parts'][self.role('gasket_old')]['location'] != 'assembly', 'Surface is obstructed')

    def _check_joint(self, j):
        if not isinstance(j, dict) or not isinstance(j.get('bolt_tensions_N'), dict): raise ValueError('Joint returned no tensions')
        expected = {f['id'] for f in self.fasteners.values() if f['group'] == 'head' and f.get('service_required',True)}
        if set(j['bolt_tensions_N']) != expected or not all(type(v) in (int,float) and math.isfinite(v) and v >= 0 for v in j['bolt_tensions_N'].values()):
            raise ValueError('Invalid per-bolt tension output')
        warp=j.get('head_warpage_m')
        unknown=(warp is None and j.get('acceptance_eligible') is False
                 and j.get('qualification')=='rigid-reference-component-only'
                 and isinstance(j.get('missing_physics'),list) and bool(j['missing_physics']))
        if not unknown and (type(warp) not in (int,float) or not math.isfinite(warp) or warp < 0):
            raise ValueError('Invalid joint warpage output')
        canonical(j)

    def _joint(self, op):
        if self.joint_backend is None: return
        op = {**op, 'bolts': copy.deepcopy(self.state['bolts']), 'surfaces': copy.deepcopy(self.state['surfaces']),
              'gasket': copy.deepcopy(self.state['gasket']), 'ordinal': len(self.state['action_history'])}
        active=self._active_action
        if active is not None:
            op.update(before_conditions=copy.deepcopy(active['before']),
                      before_conditions_sha256=digest(active['before']),attempt_sequence=len(self.records)+1)
        out = self.joint_backend.apply(copy.deepcopy(self.state['joint']), copy.deepcopy(op))
        self._check_joint(out)
        if active is not None:
            updated,evidence=self.action_domains.apply(active['name'],active['arguments'],active['before'],
                op,out.get('condition_effects'),self.joint_backend.descriptor)
            if active['name']=='check_timing':
                checks=updated['timing']['checks'];prior=active['before']['timing']['checks']
                self._require(isinstance(prior,list) and isinstance(checks,list)
                    and len(checks)==len(prior)+1 and checks[:-1]==prior,
                    'Timing evidence must append exactly one check without rewriting history')
                check=checks[-1]
                self._require(type(check.get('seq')) is int and check['seq']==len(self.records)+1
                    and type(check.get('crank_revolutions')) is int
                    and check['crank_revolutions']==active['arguments']['crank_revolutions']
                    and type(check.get('marks_align')) is bool,
                    'Timing evidence differs from the requested check')
            # Apply only validated condition leaves, preserving tentative command
            # locations, identities, engagement, mapping and command history.
            for path,item in out['condition_effects']['fields'].items():
                keys=[key.replace('~1','/').replace('~0','~') for key in path.split('/')[1:]]
                source=updated;destination=self.state
                for key in keys[:-1]:source=source[key];destination=destination[key]
                destination[keys[-1]]=copy.deepcopy(source[keys[-1]])
                provenance=self.state['condition_sources']
                for old in list(provenance):
                    if old==path or old.startswith(path+'/'):del provenance[old]
                provenance[path]={'sha256':item['source_sha256'],'status':item['status'],'note':item['note']}
            self.state['joint']=copy.deepcopy(out)
            self._attempt_effects=evidence
            return
        self.state['joint'] = copy.deepcopy(out)
        # Detached loaded distortion is a separate diagnostic channel. It does
        # not supply unloaded surface flatness, including an unknown baseline.
        if out.get('qualification')=='detached-estimate' or 'head_warpage_basis' in out:
            return
        prior_warp=self.state['surfaces']['head_face']['warpage_m']
        self.state['surfaces']['head_face']['warpage_m']=(None if out['head_warpage_m'] is None else
            max(prior_warp if prior_warp is not None else 0,out['head_warpage_m']))

    def call(self, name, args):
        self._source_identity()
        # Inside a valid source context every job-tool attempt is journalled.
        # Ownership failure is an apparatus fault before job-tool dispatch.
        before = copy.deepcopy(self.state); pre = digest(before)
        before_fasteners=copy.deepcopy(self.fasteners)
        prior_finished,prior_score=self.finished,copy.deepcopy(self.score)
        self._attempt_effects=None
        clean_args = copy.deepcopy(args)
        try: canonical(clean_args)
        except (ValueError, TypeError): clean_args = None
        try:
            validate(name, clean_args)
            self._require(not self.finished, 'Job has ended')
            self._require(self.budget() is None or not self.budget()['exhausted'],'Environment turn budget reached')
            self._require(len(self.records) < self.config['factors']['tool_call_limit'], 'Tool-call guard reached')
            self._require(name in [x['name'] for x in self.tools()], 'Tool disabled by condition')
            resolved_args=self._resolve_arguments(args)
            result = self._public_result({'ok': True, **self._dispatch(name, resolved_args)})
            self.state['simulated_labor_s'] += self.config['labor']['actions'][name]['seconds']
            self.state['revision'] += 1
            self.state['action_history'].append({'seq':len(self.records)+1, 'name': name, 'input': resolved_args})
            self._refresh_identity(self.state)
        except (Refusal, ValueError, KeyError, TypeError) as e:
            self.state = before
            self.fasteners=before_fasteners
            self.finished,self.score=prior_finished,prior_score
            result = {'ok': False, 'refusal': str(e)}
        except Exception as e:
            # Ordinary trusted failures still form an atomic, counted attempt.
            # BaseException process/cancellation signals retain their semantics.
            self.state=before; self.fasteners=before_fasteners
            self.finished,self.score=prior_finished,prior_score
            result={'ok':False,'refusal':'Trusted computation unavailable','backend_error':type(e).__name__}
        if self.budget() is not None:
            result['turns_remaining']=max(0,self.config['factors']['turn_budget']-len(self.records)-1)
        record = {'seq': len(self.records)+1, 'name': name, 'input': clean_args, 'result': copy.deepcopy(result),
                  'pre_state_sha256': pre, 'post_state_sha256': digest(self.state),
                  'previous_action_sha256': digest(self.records[-1]) if self.records else self.config_hash}
        if self._attempt_effects is not None:
            record['authorized_condition_effects']=copy.deepcopy(self._attempt_effects)
            record['condition_effects_committed']=result['ok']
        self.records.append(record)
        if self.procedure_scoring:
            from .repair_scoring import score_repair
            report = score_repair(self.config, self._repair_initial, self.records, self.state,
                                  _charge_cache=self._time_charge_cache)
            self.state['human_time'] = {key: report['human_time'][key] for key in
                ('productive_seconds', 'penalty_seconds', 'total_seconds', 'reference_seconds')}
            self.state['human_time']['attempt_seconds'] = sum(
                row['base_seconds'] for row in report['human_time']['ledger'])
            record['human_time_charge'] = copy.deepcopy(report['human_time']['ledger'][-1])
            record['post_state_sha256'] = digest(self.state)
            self.score = report
            if self.finished and name == 'finish' and result['ok']:
                result['score'] = copy.deepcopy(report)
                result['scoring_status'] = report['status']
                record['result'] = copy.deepcopy(result)
        return copy.deepcopy(result)

    def _dispatch(self, name, a):
        if self.physical_conditions and name in MECHANICAL:
            rule=self.action_domains.resolve(name,a)
            self._require(rule is not None,
                          'Source-defined physical action effects are not admitted')
            required=set()
            if name=='check_timing':required={'/timing/checks'}
            if name=='install':
                role=self.part_defs[a['part_id']]['role']
                if role=='timing_belt':required={'/timing/cam_phase_deg','/timing/crank_phase_deg'}
                if role.startswith('gasket_'):
                    required={'/gasket/orientation'}
                    if 'condition' in self.state['gasket']:required.add('/gasket/condition')
            self._require(required<=set(rule['required_paths']),
                          'Operation domain omits required source-defined outcomes')
            self._bound_backend('joint',self.joint_backend)
            self._require(digest(self.joint_backend.descriptor)==self.action_domains.packet['joint_descriptor_sha256'],
                          'Effect facade descriptor differs from admitted domain')
            self._active_action={'name':name,'arguments':copy.deepcopy(a),
                'before':{key:copy.deepcopy(self.state[key]) for key in ('parts','bolts','surfaces','gasket','timing')}}
            try:return self._dispatch_core(name,a)
            finally:self._active_action=None
        return self._dispatch_core(name,a)

    def _dispatch_core(self, name, a):
        if name in benchmark_geometry.TOOLS:
            return benchmark_geometry.dispatch(self, name, a)
        if name in procedure_actions.EXTRA_TOOLS:
            return procedure_actions.dispatch(self, name, a)
        if name == 'look':
            def category(pid):
                role=self.part_defs[pid]['role']
                if self.config['policy'].get('public_observation')=='technician-v2' and role.startswith('gasket_'): return 'head_gasket'
                return role
            rows=self.state['parts'].items()
            if self.config['policy'].get('public_observation')=='technician-v2': rows=sorted(rows,key=lambda row:self.public_id(row[0]))
            return {'parts': [{'id':pid, 'role':category(pid), 'location':p['location'],
                               'accessible':self._accessible(pid),
                               **({'carried_with':p['carried_with']} if p.get('carried_with') else {})} for pid,p in rows],
                    **({'human_time': {
                        'action_attempt_seconds': self.state.get('human_time', {}).get('attempt_seconds', 0),
                        'mistake_assessment': 'Reported after finish'}}
                       if self.procedure_scoring else {'simulated_labor_s':self.state['simulated_labor_s']}),
                    **benchmark_geometry.observation(self),
                    **({'work_budget':self.budget(len(self.records)+1)} if self.budget() is not None else {})}
        if name == 'search_service_info':
            words = service_terms(a['query'])
            entries = self.config['service']['entries']
            scores = [(3*len(words & service_terms(' '.join(e['tags'])+' '+e['title']+' '+e['id']))+
                       len(words & service_terms(e['body'])),e) for e in entries]
            matched = [e for n,e in sorted(scores,key=lambda row:(-row[0],row[1]['id'])) if n>0]
            return {'entries':copy.deepcopy(matched), 'sources':{s:self.config['service']['sources'][s] for e in matched for s in e['source_ids']}}
        if name in ('inspect','measure'):
            target = a['target']
            if target in self.state['surfaces']: self._surface_access(target)
            else:
                p = self._part(target)
                self._require(p['location'] != 'assembly' or self._accessible(target)
                              or name=='inspect' and self.config.get('benchmark_removal'), 'Component is obstructed')
            if name=='measure':
                kind=a['kind']
                if kind in ('bolt_stretch','bolt_free_length'):
                    self._require(target in self.state['bolts'] and self._part(target)['location'] != 'assembly', 'Remove bolt before measuring')
                elif kind in ('gasket_bore','gasket_thickness'):
                    self._require(target in self.part_defs and self.part_defs[target]['role'].startswith('gasket_'),
                                  'Gasket dimension measurement requires gasket stock')
                else:
                    self._require(target in self.state['surfaces'], 'Instrument incompatible with target')
            if not self.config['factors']['feedback']: return {'observation':{'feedback':'disabled'}}
            if name == 'inspect':
                if target in self.state['surfaces']:
                    return {'observation':{k:v for k,v in self.state['surfaces'][target].items() if k not in ('warpage_m','roughness_ra_um')}}
                if target in self.state['bolts']: return {'observation':{'damaged':self.state['parts'][target]['damaged'], 'thread_clean':self.state['bolts'][target]['thread_clean'], **benchmark_geometry.observation(self,target)}}
                return {'observation':{'damaged':self._part(target)['damaged'],
                        **copy.deepcopy(self.part_defs[target].get('catalog',{})),
                        **benchmark_geometry.observation(self,target),
                        **({'failed_cylinder':self.variant['failed_cylinder']} if target == self.role('gasket_old') else {})}}
            if kind in ('bolt_stretch','bolt_free_length'):
                field,instrument=('stretch_mm','length_comparator') if kind=='bolt_stretch' else ('free_length_mm','length_caliper')
                return {'observation':{'value':self.state['bolts'][target].get(field), 'unit':'mm', 'instrument':instrument}}
            if kind in ('gasket_bore','gasket_thickness'):
                field = 'bore_mm' if kind == 'gasket_bore' else 'compressed_thickness_mm'
                return {'observation':{'value':self.part_defs[target]['catalog'][field], 'unit':'mm', 'instrument':'caliper'}}
            field,unit = ('warpage_m','m') if kind == 'flatness' else ('roughness_ra_um','um')
            return {'observation':{'value':self.state['surfaces'][target][field], 'unit':unit, 'instrument':kind}}
        if name == 'remove':
            pid = a['part_id']; p = self._part(pid)
            if (self.config.get('benchmark_removal') and self.part_defs[pid]['role']=='cover_gasket_old'
                    and p['location']=='tray'):
                carrier=p.get('carried_with')
                self._require(carrier is not None and self.state['parts'][carrier]['location']=='tray',
                              'Bench seal removal requires its removed carrier')
                p.pop('carried_with');p['location']='waste'
                return {'part_id':pid,'location':'waste','service_context':'bench seal replacement',
                        'basis':'E11 new cover seal; provisional discrete bench-detachment operation',
                        'physical_qualification':False}
            self._require(self.part_defs[pid]['removable'] and p['location'] == 'assembly', 'Part cannot be withdrawn')
            decision=benchmark_geometry.prepare_removal(self,pid,a.get('route_id'))
            self._require(self._accessible(pid), 'Withdrawal is blocked by installed parts')
            carried=(decision['carried_body_ids'] if decision is not None else
                     [child for child in self.part_defs[pid].get('carried_body_ids',[])
                      if self.state['parts'][child]['location']=='assembly'])
            moving={pid,*carried}
            self._require(all(self.state['parts'][f['id']]['location']!='assembly'
                              for f in self.fasteners.values() if any(self.bound_part(held) in moving for held in (f['holds'] or [])) and f['id'] not in carried),
                          'Component is retained by an installed fastener')
            if pid in self.fasteners: self._require(self.state['bolts'][pid]['turns'] <= 1e-9, 'Fastener is still engaged')
            p['location'] = 'waste' if self.part_defs[pid]['role'] == 'gasket_old' else 'tray'
            for child in carried:
                self.state['parts'][child].update({'location':'tray','carried_with':pid})
            if self.config.get('benchmark_task') and procedure_actions.effective_role(self.part_defs[pid])=='timing_belt':
                self.state['timing'].update(tensioned=False,belt_tensioned=False)
            benchmark_geometry.record_removal(self,pid,decision)
            if self.state['gasket']['active_id'] == pid: self.state['gasket']['active_id'] = None
            self._joint({'kind':'remove', **a,**({'carried_body_ids':carried} if carried else {})})
            return {'part_id':pid,'location':p['location'],**({'carried_body_ids':carried} if carried else {})}
        if name == 'install':
            pid=a['part_id']; p=self._part(pid)
            self._require(p['location'] in ('tray','supply') and self.part_defs[pid]['role'] != 'gasket_old', 'Part is not an installable supply')
            self._require(not p.get('carried_with'),'Body is retained by its carrier on the tray')
            carried=benchmark_geometry.carried_for_install(self,pid)
            self._require(benchmark_geometry.installation_context_allowed(self,pid,carried),
                          'Head-relative installation requires an installed or jointly moving compatible head')
            moving={pid,*carried}
            self._require(all(self.state['parts'][self.bound_part(x)]['location']=='assembly' or self.bound_part(x) in moving
                              for x in self.part_defs[pid]['requires_installed']), 'Required support or mate is absent')
            role=procedure_actions.effective_role(self.part_defs[pid])
            if role in ('head', 'timing_belt') and self.part_defs[pid].get('replacement_for'):
                self._require(self.bound_part(self.part_defs[pid]['replacement_for']) == pid,
                              'Replacement supply must be exchanged into its service position before installation')
            if role in ('head_bolt','cover_bolt'):
                self._require(pid in self.fasteners,'Fastener supply has no mapped service position; replace first')
            if role.startswith('gasket_'):
                self._require('condition' not in self.state['gasket'] or self._active_action is not None,
                              'Gasket condition requires admitted source effects')
                self._require(self.state['parts'][self.role('head')]['location'] != 'assembly' and self.state['gasket']['active_id'] is None, 'Gasket access is blocked')
                self.state['gasket'].update({'active_id':pid,'type': 'correct' if role=='gasket_new' else 'wrong',
                    'orientation':self.state['gasket']['orientation'] if self._active_action else a.get('orientation','up')})
            if role.startswith('gasket_') and self.config.get('benchmark_task'):
                dowels=[key for key,definition in self.part_defs.items() if definition['role']=='dowel']
                self.state['gasket'].update(
                    dowels_aligned=bool(dowels) and all(self.state['parts'][key]['location']=='assembly' for key in dowels)
                                   and a.get('orientation','up')=='up' and role=='gasket_new',
                    alignment_basis='Discrete benchmark installation at retained dowel positions; fit/clearance not simulated')
            if role=='head': self._require(self.state['gasket']['active_id'] is not None, 'No gasket fitted')
            if role=='timing_belt':
                self._require('cam_phase_deg' in a and 'crank_phase_deg' in a, 'Timing phases must be supplied')
                if self._active_action is None:self.state['timing'].update({k:a[k] for k in ('cam_phase_deg','crank_phase_deg')})
                if self.config.get('benchmark_task'):
                    self.state['timing'].update(belt_id=pid, tensioned=False, belt_tensioned=False, installed_seq=len(self.records)+1)
            if pid in self.fasteners:
                f=self.fasteners[pid]; self._require(self.state['parts'][f['washer_id']]['location']=='assembly'
                    or f['washer_id'] in carried, 'Washer is absent')
                self.state['bolts'][pid].update({'turns':self.state['bolts'][pid]['install_engagement_turns']
                    if self.config.get('initial_conditions') else 2,'torque_N_m':0})
                self.state['bolts'][pid]['history'].append({'kind':'start','seq':len(self.records)+1})
            self._require(all(self.state['parts'][self.bound_part(mate)]['location']=='assembly' or self.bound_part(mate) in moving
                              for child in carried for mate in self.part_defs[child]['requires_installed']),
                          'Carried body support is absent')
            p['location']='assembly'
            for child in carried:
                self.state['parts'][child]['location']='assembly';self.state['parts'][child].pop('carried_with')
            benchmark_geometry.record_install(self,pid,carried)
            self._joint({'kind':'install',**a,**({'carried_body_ids':carried} if carried else {})})
            return {'part_id':pid,'location':'assembly',**({'carried_body_ids':carried} if carried else {})}
        if name=='clean':
            target=a['target']
            if target in self.state['surfaces']:
                self._surface_access(target); s=self.state['surfaces'][target]
                if self._active_action is None:
                    s['residue_fraction']=0; s['dry']=True
                    if not a.get('protect_openings',False): s['debris_count']+=1
                    if a['method']=='abrasive_disc': s['damaged']=True; s['roughness_ra_um']=5
                    if target=='cover_face':
                        s['tube_seals_oiled']=a.get('oil',False)
                        s['cam_holder_corner_sealant']=a.get('sealant')=='cam_holder_corners'
            else:
                self._require(target in self.state['bolts'] and self._part(target)['location']=='tray', 'Removed fastener required')
                self._require(a['method']=='thread_brush','Fastener needs thread brush')
                if self._active_action is None:
                    self.state['bolts'][target].update({'thread_clean':True,'thread_oiled':a.get('oil',False),'washer_oiled':a.get('oil',False)})
            self._joint({'kind':'clean',**a}); return {'target':target,'operation':'completed'}
        if name=='replace':
            pid,new=a['part_id'],a['replacement_id']; p=self._part(pid); q=self._part(new)
            self._require(not p.get('carried_with'),'Body is retained by its carrier on the tray')
            self._require(not any(v.get('carried_with')==pid for v in self.state['parts'].values())
                          or benchmark_geometry.can_exchange_carrier(self,pid,new),'Carrier retains separate bodies on the tray')
            self._require(p['location'] in ('tray','waste') and q['location']=='supply' and pid!=new, 'Replacement supplies unavailable')
            oldrole,newrole=procedure_actions.effective_role(self.part_defs[pid]),procedure_actions.effective_role(self.part_defs[new])
            self._require(oldrole==newrole or oldrole.startswith('gasket_') and newrole.startswith('gasket_') or
                          oldrole.startswith('cover_gasket_') and newrole.startswith('cover_gasket_'), 'Incompatible replacement role')
            self._require(new not in self.fasteners, 'Fastener replacement needs a mapped service position')
            if pid in self.fasteners:
                self._require(self.part_defs[new].get('replacement_for')==self.fasteners[pid].get('original_id',pid),
                              'Replacement does not match this service position')
                f=self.fasteners.pop(pid); f=copy.deepcopy(f); f['id']=new; self.fasteners[new]=f
                f['original_id']=f.get('original_id',pid)
                if self.config.get('initial_conditions'):
                    b=copy.deepcopy(self.state['bolts'][new])
                else:
                    b=copy.deepcopy(self.state['bolts'][pid]); b.update({'stretch_mm':0,'turns':0,'torque_N_m':0,'thread_clean':False,'thread_oiled':False,'washer_oiled':False})
                b['history'].append({'kind':'replacement','old_id':pid,'seq':len(self.records)+1})
                self.state['bolts'][new]=b
            procedure_actions.after_replace(self, pid, new)
            benchmark_geometry.exchange(self,pid,new)
            p['location']='waste'; q['location']='tray'
            self._joint({'kind':'replace',**a}); return {'removed':pid,'supply':new}
        if name=='torque':
            pid=a['part_id']; p=self._part(pid)
            self._require(pid in self.fasteners and self.fasteners[pid].get('service_required',True)
                          and self.part_defs[pid]['removable'] and p['location']=='assembly' and self._accessible(pid), 'Fastener is inaccessible or retained')
            f=self.fasteners[pid]; b=self.state['bolts'][pid]
            if a['mode']=='loosen':
                self._require(b['turns']>0, 'Fastener is already disengaged')
                b['turns']=max(0,b['turns']+a['angle_deg']/360); b['torque_N_m']=0
            else:
                self._require(all(self.state['parts'][x['id']]['location']=='assembly' for x in self.fasteners.values() if x['group']==f['group']), 'Start all group fasteners before torque')
                self._require(all(self.state['bolts'][x['id']]['turns']>0 for x in self.fasteners.values()
                                  if x['group']==f['group'] and x.get('service_required',True)),
                              'Start all required group threads before torque')
                b['torque_N_m']=a['value_N_m']
            b['history'].append({'seq':len(self.records)+1,'kind':a['mode'], **{k:v for k,v in a.items() if k not in ('part_id','mode')}})
            self._joint({'kind':'torque','group':f['group'],'sequence_index':f['sequence_index'],**a})
            return {'part_id':pid,'operation':'completed'}
        if name=='check_timing':
            self._require(self.state['parts'][self.role('timing_belt')]['location']=='assembly','Timing drive is absent')
            if self._active_action is not None:
                self._joint({'kind':'check_timing',**a})
                return {'observation':{'marks_align':self.state['timing']['checks'][-1]['marks_align']}
                    if self.config['factors']['feedback'] else {'feedback':'disabled'}}
            t=self.state['timing']; error=(t['cam_phase_deg']-t['crank_phase_deg']/2+180)%360-180
            t['checks'].append({'seq':len(self.records)+1,'crank_revolutions':a['crank_revolutions'],'phase_error_deg':error})
            return {'observation': {'marks_align':abs(error)<=self.config['policy']['timing_tolerance_deg'],
                    **({'tdc_cylinder':1 if t.get('set_seq') is not None and t['cam_phase_deg']==0 and t['crank_phase_deg']==0 else None,
                        'basis':'Discrete benchmark cylinder-one compression-TDC phase datum; no engine rotation simulation'}
                       if self.config.get('benchmark_task') else {})} if self.config['factors']['feedback'] else {'feedback':'disabled'}}
        if name=='finish':
            if self.procedure_scoring:
                self.finished = True
                return {'scoring_status': 'scored', 'score': None}
            # Historical replay compatibility only; new study runs use procedure scoring.
            # Score the same final state that the journal will commit.
            final=copy.deepcopy(self.state)
            final['revision']+=1; final['simulated_labor_s']+=self.config['labor']['actions']['finish']['seconds']
            final['action_history'].append({'seq':len(self.records)+1,'name':'finish','input':{}})
            self._refresh_identity(final)
            if self.physical_conditions or self.soak_backend is not None and self.joint_backend is not None:
                blocker=None;joint=final['joint']
                if self.physical_conditions:
                    for kind,backend in (('joint',self.joint_backend),('soak',self.soak_backend)):
                        if backend is not None:self._bound_backend(kind,backend)
                    if self.joint_backend is None or self.soak_backend is None:
                        blocker='Physical scoring requires both admitted source backends'
                    elif any(source['status']=='unknown' for source in final.get('condition_sources',{}).values()):
                        blocker='Source-defined final conditions remain unknown'
                    elif any(type(final['bolts'][pid].get('free_length_mm')) not in (int,float)
                            or not math.isfinite(final['bolts'][pid]['free_length_mm'])
                            or final['bolts'][pid]['free_length_mm']<=0
                            for pid,f in self.fasteners.items()
                            if f['group']=='head' and f.get('service_required',True)):
                        blocker='Selected head bolt free lengths are required before physical scoring'
                    elif joint.get('acceptance_eligible') is not True or joint.get('qualification')!='validated-physics':
                        blocker='Joint state is ineligible for physical scoring'
                elif joint.get('acceptance_eligible') is False:
                    blocker='Joint state is ineligible for physical scoring'
                if blocker:
                    out={'schema':'hgj/soak-result/v1','status':'INVALID_INPUT','qualification':'unqualified',
                         'pass':None,'time_to_failure_s':None,'cause':blocker}
                else:
                    out=self.soak_backend.score(final)
                    if not self.physical_conditions and out.get('qualification')=='validated-physics':
                        out={'schema':'hgj/soak-result/v1','status':'INVALID_INPUT','qualification':'unqualified',
                             'pass':None,'time_to_failure_s':None,'cause':'Fixture configuration cannot receive physical scoring credit'}
                canonical(out)
                from .backends import validate_score
                validate_score(out,physical=self.physical_conditions,
                    expected_protocol=self.config.get('admission',{}).get('expected_protocol'))
                self.score=copy.deepcopy(out)
            self.finished=True
            status=self.score.get('status','scored') if self.score is not None else 'unavailable'
            return {'scoring_status':status,'score':copy.deepcopy(self.score)}
        raise Refusal('Unknown operation')

    def export(self):
        self._source_identity()
        if self.environment_source is not None:
            if digest(self.config)!=self.config_hash:
                raise ValueError('Run config differs from initialized source job')
            selected=[v for v in self.config['variants'] if v['id']==self.config['variant_id']]
            if (len(selected)!=1 or canonical(self.variant)!=canonical(selected[0])
                    or self.state['variant_id']!=self.config['variant_id']):
                raise ValueError('Final selected variant differs from source job')
            expected=copy.deepcopy(self.state)
            self._refresh_identity(expected)
            if (canonical(expected['identity'])!=canonical(self.state['identity'])
                    or canonical(expected['fastener_mapping'])!=canonical(self.state.get('fastener_mapping'))):
                raise ValueError('Final owned commitments differ from current source job')
        return {'schema':'hgj/run/v2' if self.environment_source is not None else 'hgj/run/v1',
                **({'environment_source':copy.deepcopy(self.environment_source),
                    'environment_source_sha256':digest(self.environment_source)} if self.environment_source is not None else {}),
                'config':copy.deepcopy(self.config),'config_sha256':self.config_hash,
                **({'initial_state':copy.deepcopy(self._repair_initial),
                    'initial_state_sha256':digest(self._repair_initial)} if self.procedure_scoring else {}),
                'actions':copy.deepcopy(self.records),'final_state':copy.deepcopy(self.state),'final_state_sha256':digest(self.state),
                'score':copy.deepcopy(self.score),'score_sha256':digest(self.score),
                'finished':self.finished,'scoring_status':self.score.get('status','scored') if self.score is not None else 'unavailable',
                **({'budget':self.budget()} if self.budget() is not None else {})}


def replay(record, joint=None, soak=None, environment_source=None, source_runtime=None):
    if environment_source is not None:raise ValueError('Replay environment source requires an active runtime context')
    if source_runtime is not None:
        if source_runtime is not globals().get('__loader__'):raise ValueError('Replay environment source runtime does not own this module')
        source_runtime.require_module(__name__,globals());environment_source=source_runtime.identity
    schema=record.get('schema')
    if schema not in ('hgj/run/v1','hgj/run/v2') or digest(record['config'])!=record['config_sha256']: raise ValueError('Run input hash mismatch')
    if schema=='hgj/run/v2':
        if environment_source is None or record.get('environment_source')!=environment_source or record.get('environment_source_sha256')!=digest(environment_source):
            raise ValueError('Replay environment source identity mismatch')
    elif environment_source is not None or 'environment_source' in record or 'environment_source_sha256' in record:
        raise ValueError('Legacy replay cannot claim environment source custody')
    game=Game(record['config'],joint=joint,soak=soak,source_runtime=source_runtime)
    for r in record['actions']:
        game.call(r['name'],r['input'])
        if canonical(game.records[-1])!=canonical(r): raise ValueError('Action replay mismatch at sequence '+str(r.get('seq')))
    actual=game.export()
    for key in ('final_state','final_state_sha256','score','score_sha256','finished','scoring_status')+ (('budget',) if game.budget() is not None else ()):
        if canonical(actual[key])!=canonical(record.get(key)): raise ValueError('Final replay mismatch: '+key)
    if canonical(actual)!=canonical(record): raise ValueError('Complete replay record mismatch')
    return actual
