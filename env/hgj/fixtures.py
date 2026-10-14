"""Software-only fixtures. All force, damage and failure-time numbers here are synthetic.

They must never be admitted as study physics or reported as a physical control pass.
"""
from .api import DEFINITIONS


def fixture_config():
    parts=[]; fasteners=[]
    def part(pid, role, installed=True, removed=(), supports=(), removable=True):
        parts.append({'id':pid,'role':role,'installed':installed,'removable':removable,
                      'requires_removed':list(removed),'requires_installed':list(supports),'source_id':'fixture'})
    part('block','block',removable=False)
    for group,count,prefix,wp,held,length in [('head',10,'hb','hw','head',140),('cover',5,'cb','cw','cover',40)]:
        for i in range(1,count+1):
            bid,wid=f'{prefix}{i:02}',f'{wp}{i:02}'
            part(bid, 'head_bolt' if group=='head' else 'cover_bolt', removed=('cover','belt') if group=='head' else (), supports=(held,wid))
            part(wid, 'head_washer' if group=='head' else 'cover_washer', removed=(bid,), supports=(held,))
            fasteners.append({'id':bid,'group':group,'sequence_index':i,'washer_id':wid,'holds':[held],
                              'thread':{'diameter_mm':10 if group=='head' else 6,'pitch_mm':1.25 if group=='head' else 1,'length_mm':length},
                              'initial_engagement_turns':1,'spec_ref':'fixture','source_id':'fixture'})
    part('head','head',removed=tuple(f'hb{i:02}' for i in range(1,11))+tuple(f'hw{i:02}' for i in range(1,11))+('cover','belt'), supports=('block',))
    part('cover','valve_cover',removed=tuple(f'cb{i:02}' for i in range(1,6))+tuple(f'cw{i:02}' for i in range(1,6)),supports=('head',))
    part('belt','timing_belt',supports=('head',))
    part('gasket_old','gasket_old',removed=('head',),supports=('block',))
    part('gasket_new','gasket_new',False,supports=('block',))
    part('gasket_wrong','gasket_wrong',False,supports=('block',))
    for p in parts:
        if p['role'] in ('gasket_new','gasket_wrong'):
            p['catalog']={'bore_mm':75.5 if p['role']=='gasket_new' else 78,
                          'compressed_thickness_mm':0.762 if p['role']=='gasket_new' else 1.2,
                          'construction':'multilayer steel','qualification':'software illustration; dimensions are estimates'}
    part('cover_gasket_old','cover_gasket_old',removed=('cover',),supports=('head',))
    part('cover_gasket_new','cover_gasket_new',False,supports=('head',))
    for i in range(1,11):
        part(f'new_hb{i:02}','head_bolt',False,removed=('cover','belt'),supports=('head',f'hw{i:02}'))
        parts[-1]['replacement_for']=f'hb{i:02}'
    return {'schema':'hgj/config/v1','geometry':{'schema':'hgj/geometry/v1','qualification':'software-fixture',
              'engine_sha256':'0'*64,'sources':[{'id':'fixture','sha256':'0'*64,'qualification':'software-fixture'}],
              'parts':parts,'fasteners':fasteners,'edge_evidence':[]},
            'service':{'sources':{'F':{'title':'Synthetic fixture','qualification':'software-fixture'}},
                       'entries':[{'id':'head_torque','title':'Head torque','tags':['head','torque','sequence'],
                                   'body':'Complete ordered passes at 30 then 73 N_m.', 'source_ids':['F'],'qualification':'software-fixture'}]},
            'labor':{'sources':{'F':{'title':'Synthetic unit clock'}},'actions':{n:{'seconds':1,'qualification':'software-fixture','source_ids':['F']} for n,_,_ in DEFINITIONS}},
            'variants':[{'id':'cylinder_2','failed_cylinder':2,'stretched_bolts':{'3':0.2}},
                        {'id':'cylinder_1','failed_cylinder':1,'stretched_bolts':{}},
                        {'id':'cylinder_4','failed_cylinder':4,'stretched_bolts':{'7':0.2}}],
            'variant_id':'cylinder_2', 'factors':{'service_info':True,'feedback':True,'turn_budget':256,
                'turn_budget_unit':'job-tool-action-attempts','tool_call_limit':4096},
            'policy':{'public_observation':'technician-v2','initial_torque_N_m':{'head':73,'cover':10},'timing_tolerance_deg':0.1,
                      'stretch_replace_limit_mm':0.1,'qualification':'software-fixture'}}


class FixtureJoint:
    qualification='software-fixture'
    def initialize(self, config):
        return {'qualification':self.qualification,'bolt_tensions_N':{f['id']:7300 for f in config['geometry']['fasteners'] if f['group']=='head'},
                'head_warpage_m':0.00002,'tightening':[],'loosening':[],'sequence_damage':False}

    def apply(self, state, op):
        if op['kind']=='replace' and op['part_id'] in state['bolt_tensions_N']:
            state['bolt_tensions_N'][op['replacement_id']]=state['bolt_tensions_N'].pop(op['part_id'])
        if op['kind']=='torque' and op['group']=='head':
            pid=op['part_id']
            if op['mode']=='tighten':
                state['tightening'].append({'index':op['sequence_index'],'torque':op['value_N_m']})
                i=(len(state['tightening'])-1)%10+1
                if op['sequence_index']!=i: state['sequence_damage']=True; state['head_warpage_m']=0.00008
                b=op['bolts'][pid]
                factor=0.4 if b['stretch_mm']>0.1 else 1
                if not b['thread_oiled'] or not b['washer_oiled']: factor*=0.6
                state['bolt_tensions_N'][pid]=op['value_N_m']*100*factor
            else:
                state['loosening'].append(op['sequence_index'])
                state['bolt_tensions_N'][pid]=0
        return state


class FixtureSoak:
    qualification='software-fixture'
    def score(self, job):
        j=job['joint']; cause=None
        if job['timing']['cam_phase_deg']-job['timing']['crank_phase_deg']/2!=0: cause='timing_error'
        elif job['gasket']['type']!='correct' or job['gasket']['orientation']!='up': cause='fire_ring_leak'
        elif any(s['damaged'] or s['debris_count'] or s['residue_fraction'] or not s['dry'] for s in job['surfaces'].values()): cause='surface_leak'
        elif j['sequence_damage']: cause='joint_distortion'
        elif any(b['stretch_mm'] is not None and b['stretch_mm']>0.1 and job['parts'][pid]['location']=='assembly' for pid,b in job['bolts'].items()): cause='bolt_relaxation'
        elif min(j['bolt_tensions_N'].values())<7000: cause='insufficient_contact'
        elif any(job['parts'][pid]['location']!='assembly' for pid in ('head','cover','belt')): cause='missing_component'
        return {'schema':'hgj/soak-result/v1','qualification':self.qualification,'pass':cause is None,
                'time_to_failure_s':None if cause is None else 10,'cause':cause,
                'simulated_duration_s':3720 if cause is None else 10,
                'protocol':{'main_rpm':3000,'main_duration_s':3600,'idle_hold_s':60,'redline_hold_s':60,'redline_rpm':6500},
                'model_sha256':'0'*64,'evidence_sha256':'0'*64,
                'idealizations':['Entire fixture is synthetic; no physical score or study admission.']}


def correct_job(game, bad=None, through=None):
    def act(name, **args):
        args={k:game.public_id(v) if k in ('part_id','replacement_id','target') and v in game.part_defs else v for k,v in args.items()}
        r=game.call(name,args)
        if not r['ok']: raise RuntimeError(f'{name} {args}: {r}')
    geometry=game.config['geometry']; fast=geometry['fasteners']
    # Controls go through the same public API as subjects.
    for group in ('cover','head'):
        rows=sorted((f for f in fast if f['group']==group and f.get('service_required',True)),key=lambda f:f['sequence_index'],reverse=True)
        if group=='head': act('remove',part_id=game.role('timing_belt'))
        import math
        passes={f['id']:math.ceil(f['initial_engagement_turns']*3-1e-9) for f in rows}
        for stage in range(max(passes.values())):
            for f in rows:
                if stage<passes[f['id']]:act('torque',part_id=f['id'],mode='loosen',angle_deg=-120)
        for f in rows:
            act('remove',part_id=f['id']); act('remove',part_id=f['washer_id'])
        act('remove',part_id=game.role('valve_cover' if group=='cover' else 'head'))
    act('remove',part_id=game.role('gasket_old'))
    if through=='service': return
    for target in ('head_face','block_deck'):
        act('clean',target=target,method='plastic_scraper',protect_openings=True)
        act('measure',target=target,kind='flatness')
    current=[]
    for f in sorted((f for f in fast if f['group']=='head'),key=lambda f:f['sequence_index']):
        bid=f['id']
        stretch=game.variant['stretched_bolts'].get(str(f['sequence_index']),0)
        act('measure',target=bid,kind='bolt_stretch')
        if stretch>game.config['policy']['stretch_replace_limit_mm'] and bad!='reused_stretched_bolt':
            matches=[p['id'] for p in geometry['parts'] if p.get('replacement_for')==bid]
            if len(matches)!=1: raise ValueError('Control lacks unique mapped replacement')
            new=matches[0]
            act('replace',part_id=bid,replacement_id=new); bid=new
        act('clean',target=bid,method='thread_brush',oil=True)
        current.append((f,bid))
    selected=game.role('gasket_wrong' if bad=='wrong_gasket' else 'gasket_new')
    act('replace',part_id=game.role('gasket_old'),replacement_id=selected)
    act('install',part_id=selected,orientation='up'); act('install',part_id=game.role('head'))
    for f,bid in current:
        act('install',part_id=f['washer_id']); act('install',part_id=bid)
    order=current[::-1] if bad=='wrong_torque_sequence' else current
    for value in ([30] if bad=='skipped_retorque' else [30, 50 if bad=='under_torque' else 73]):
        for f,bid in order: act('torque',part_id=bid,mode='tighten',value_N_m=value)
    act('install',part_id=game.role('timing_belt'),cam_phase_deg=15 if bad=='wrong_timing' else 0,crank_phase_deg=0)
    act('check_timing',crank_revolutions=4)
    if any(p['role']=='cover_gasket_old' for p in geometry['parts']):
        act('remove',part_id=game.role('cover_gasket_old'))
        act('clean',target='cover_face',method='plastic_scraper',protect_openings=True,oil=True,sealant='cam_holder_corners')
        act('replace',part_id=game.role('cover_gasket_old'),replacement_id=game.role('cover_gasket_new'))
        act('install',part_id=game.role('cover_gasket_new'))
    act('install',part_id=game.role('valve_cover'))
    for f in sorted((f for f in fast if f['group']=='cover'),key=lambda f:f['sequence_index']):
        act('install',part_id=f['washer_id']); act('install',part_id=f['id'])
    for value in (3,6,10):
        for f in sorted((f for f in fast if f['group']=='cover'),key=lambda f:f['sequence_index']):
            act('torque',part_id=f['id'],mode='tighten',value_N_m=value)
    act('finish')
