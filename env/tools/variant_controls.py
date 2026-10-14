"""Five task variants and scripted reference trajectories for study design v2.

Initial wear, surface service results and replacement supplies are declared
benchmark conditions. No joint, native geometry or engine model is invoked.
"""
import copy
import json
from pathlib import Path
from hgj.fixtures import fixture_config
from hgj.game import Game
from tools.repair_controls import actions_for, prepare_config

VARIANTS = ('V1', 'V2', 'V3', 'V4', 'V5')
BAD_VARIANTS = {
    'wrong_torque_sequence':'V1', 'under_torque':'V1', 'skipped_final_stage':'V1',
    'wrong_gasket':'V4', 'reused_stretched_bolt':'V2', 'wrong_timing':'V1',
    'missing_attachment_restoration':'V1',
}


def base_configuration(variant_id='V1', root=None, *, with_removal_policy=False, removal_source_dir=None):
    if variant_id not in VARIANTS:
        raise ValueError('Unknown study variant')
    root=Path(root) if root else Path(__file__).resolve().parents[1]
    config=fixture_config()
    config['variants']=[
        {'id':name, 'failed_cylinder':2, 'stretched_bolts':{'3':0.2} if name=='V2' else {},
         'warpage_m':{'head_face':0.00008 if name=='V3' else 0.00002, 'block_deck':0.00002},
         'worn_timing_belt':name=='V5'} for name in VARIANTS]
    config['variant_id']=variant_id
    config['checkpoint_revision']='amendment-1-20261009'
    config['service']=json.loads((root/'data/service.json').read_bytes())
    config['service']['sources'].setdefault('B1',{
        'title':'Study design v2 selected replacement stock definitions',
        'qualification':'Explicit benchmark definitions; not an independent factory application claim'})
    config['service']['entries']=[row for row in config['service']['entries'] if row['id'] not in ('B01','B02')]
    config['service']['entries'].append({
        'id':'B01', 'title':'Replacement stock identification',
        'tags':['gasket','part','number','bore','thickness','stock'],
        'body':'The selected replacement head gasket is HG-075-0762-MLS: 75 mm bore, 0.762 mm compressed thickness, multilayer steel. Stock HG-078-1200 has 78 mm bore and 1.2 mm thickness and is not the selected replacement. Inspect markings or measure the stock before choosing it.',
        'source_ids':['B1'], 'qualification':'Coordinator-selected benchmark stock dimensions'})
    config['service']['entries'].append({
        'id':'B02','title':'Current benchmark service decisions','tags':['reuse','flatness','machining','head','limit','benchmark'],
        'body':'For this benchmark, compare measured head-bolt extension to 0.10 mm: replace when it exceeds that value; otherwise keep a serviceable bolt. Compare head and block flatness with 0.05 mm. A head beyond the limit may use the configured machine_head service or a distinct replacement head. The configured machining eligibility and result are benchmark assumptions. B01 defines the selected stock for this task and takes precedence over generic application listings elsewhere in this corpus.',
        'source_ids':['B1'],'qualification':'Explicit benchmark policy overlay; numeric reuse rule and machining eligibility are not independently qualified factory specifications'})
    config['labor']=json.loads((root/'data/labor-v2.json').read_bytes())
    retained=json.loads((root/'data/procedure-retained-bodies.json').read_bytes())
    config['geometry']['parts'].extend(copy.deepcopy(retained['parts']))
    config['geometry']['retained_body_source']=retained
    by_id={p['id']:p for p in config['geometry']['parts']}
    for pid, bore, thickness, number in (
        ('gasket_new',75,0.762,'HG-075-0762-MLS'), ('gasket_wrong',78,1.2,'HG-078-1200')):
        by_id[pid]['catalog'].update(bore_mm=bore,compressed_thickness_mm=thickness,part_number=number,
            description='Head gasket stock', qualification='Selected benchmark stock definition')
    by_id['gasket_wrong']['available_in_bin']=variant_id=='V4'
    surface={'residue_fraction':0, 'dry':True, 'debris_count':0, 'damaged':False,
             'warpage_m':0.00002, 'roughness_ra_um':0.5}
    for pid, role, original in (('new_head','head_supply','head'),('new_belt','timing_belt_supply','belt')):
        definition=copy.deepcopy(by_id[original])
        definition.update(id=pid, role=role, installed=False, replacement_for=original,
                          source_id='benchmark-distinct-replacement-stock',
                          available_in_bin=variant_id==('V3' if original=='head' else 'V5'),
                          catalog={'part_number':'HEAD-SERVICE' if original=='head' else 'BELT-SERVICE',
                                   'description':'Replacement head' if original=='head' else 'New timing belt',
                                   'qualification':'Distinct provisional benchmark supply; factory fit unverified'})
        if original=='head':
            definition['replacement_surface']=copy.deepcopy(surface)
        config['geometry']['parts'].append(definition)
    config['policy']['flatness_limit_m']=0.00005
    config['policy']['flatness_limits_m']={'head_face':0.00005,'block_deck':0.00005}
    config['policy']['flatness_limit_source_ids']=['B1']
    config['benchmark_task']={
        'schema':'hgj/study-task/v2', 'variant_id':variant_id,
        'title':{'V1':'Standard head-gasket replacement','V2':'One stretched head bolt',
                 'V3':'Head exceeds the flatness limit','V4':'Incorrect gasket stock is also available',
                 'V5':'Timing belt is worn'}[variant_id],
        'qualification':'Discrete procedure benchmark with explicit starting-condition and service-result stand-ins',
        'machining':{'eligible':True, 'material_removed_m':0.00006, 'result_flatness_m':0.00002,
                     'result_roughness_ra_um':0.5,
                     'basis':{'kind':'provisional_benchmark_rule','service_entry':'E06',
                              'scope':'Configured service eligibility/result; head height and cam-holder geometry are not simulated'}},
        'accepted_head_recovery':['machine_head','replace'],
        'source_removal_policy_status':'L1 provisional policy integration in progress'}
    if with_removal_policy:
        from tools.l1_controls import augment
        augment(config,root,removal_source_dir)
    return config


def actions_for_variant(config, name='correct', *, head_recovery='machine'):
    if head_recovery not in ('machine','replace'):
        raise ValueError('Unknown head recovery route')
    base=copy.deepcopy(config);base.pop('repair_scoring',None)
    metadata=Game(base)
    variant=base['variant_id']
    if name=='missing_attachment_restoration' and not base.get('benchmark_removal'):
        raise ValueError('Missing-attachment control requires a source removal policy')
    original=actions_for(base,'correct' if name=='missing_attachment_restoration' else name)
    actions=[]
    for row in original:
        row=copy.deepcopy(row)
        if row['name']=='inspect' and row['input']['target']==metadata.public_id('gasket_new'):
            actions.append({'name':'parts_bin','input':{}})
            actions.append({'name':'search_service_info','input':{'query':'replacement gasket stock part number'}})
            if variant=='V4':
                actions.append({'name':'inspect','input':{'target':metadata.public_id('gasket_wrong')}})
                actions.append({'name':'measure','input':{'target':metadata.public_id('gasket_wrong'),'kind':'gasket_bore'}})
            actions.append({'name':'measure','input':{'target':metadata.public_id('gasket_new'),'kind':'gasket_bore'}})
        if row['name']=='remove' and row['input']['part_id']=='belt':
            actions.extend([
                {'name':'inspect','input':{'target':'belt'}},
                {'name':'set_timing','input':{'cam_phase_deg':0,'crank_phase_deg':0}},
                {'name':'check_timing','input':{'crank_revolutions':1}},
            ])
        if row['name']=='install':
            pid=row['input']['part_id']
            if pid=='head' and variant=='V3' and head_recovery=='replace':
                row['input']['part_id']=metadata.public_id('new_head')
            if pid=='belt' and variant=='V5':
                row['input']['part_id']=metadata.public_id('new_belt')
        actions.append(row)
        if row['name']=='remove' and row['input']['part_id']=='belt' and variant=='V5':
            actions.append({'name':'replace','input':{'part_id':'belt','replacement_id':metadata.public_id('new_belt')}})
        if row['name']=='measure' and row['input']=={'target':'head_face','kind':'flatness'} and variant=='V3':
            if head_recovery=='machine':
                actions.append({'name':'machine_head','input':{'part_id':'head'}})
            else:
                actions.append({'name':'replace','input':{'part_id':'head','replacement_id':metadata.public_id('new_head')}})
            actions.append({'name':'measure','input':{'target':'head_face','kind':'flatness'}})
        if row['name']=='install' and row['input']['part_id'] in ('belt',metadata.public_id('new_belt')):
            actions.append({'name':'tension_belt','input':{'part_id':row['input']['part_id']}})
    if base.get('benchmark_removal'):
        from tools.l1_controls import expand_actions
        actions=expand_actions(base,actions,Path(__file__).resolve().parents[1])
    if base.get('checkpoint_revision')=='amendment-1-20261009':
        # Exercise both signed orders within the six correct routes.
        order=(10,9,8,7,6,5,4,3,2,1) if head_recovery=='replace' else (10,9,8,7,6,3,4,5,2,1)
        selected=[f for f in base['geometry']['fasteners']
                  if f['group']=='head' and f.get('service_required',True)]
        if (len(selected)!=10 or len({f['id'] for f in selected})!=10
                or any(type(f['sequence_index']) is not int for f in selected)
                or {f['sequence_index'] for f in selected}!=set(range(1,11))):
            raise ValueError('Amended reference head loosening census differs')
        positions={f['sequence_index']:f['id'] for f in selected}
        indexes=[i for i,row in enumerate(actions) if row['name']=='torque'
                 and row['input'].get('mode')=='loosen' and row['input'].get('part_id') in positions.values()]
        if (len(indexes)!=30
                or any({actions[i]['input']['part_id'] for i in indexes[start:start+10]}
                       !=set(positions.values()) for start in (0,10,20))
                or any(actions[i]['input'].get('angle_deg')!=-120 for i in indexes)):
            raise ValueError('Amended reference head loosening census differs')
        for offset,index in enumerate(indexes):
            actions[index]['input']['part_id']=positions[order[offset%10]]
        # V1 demonstrates the inspected-original carrier route. The seal never
        # enters waste and is returned among the cover's explicit carried IDs.
        if variant=='V1':
            transformed=[]
            original_seal=metadata.role('cover_gasket_old')
            new_seal=metadata.role('cover_gasket_new')
            for row in actions:
                args=row['input']
                pid=metadata.public_to_body.get(args.get('part_id'),args.get('part_id'))
                if (row['name'] in ('remove','replace') and pid==original_seal
                        or row['name']=='install' and pid==new_seal):
                    continue
                if row['name']=='clean' and args.get('target')=='cover_face':
                    transformed.append({'name':'inspect','input':{'target':metadata.public_id(original_seal)}})
                transformed.append(row)
            actions=transformed
    if name=='missing_attachment_restoration':
        actions=[row for row in actions if row['name']!='restore_attachment']
    return actions


def configuration(variant_id='V1', root=None, *, with_removal_policy=False, removal_source_dir=None):
    from hgj.human_time import policy_from_variant_labor
    base=base_configuration(variant_id,root,with_removal_policy=with_removal_policy,removal_source_dir=removal_source_dir)
    config=prepare_config(base,reference_actions=actions_for_variant(base),
                          human_time_policy=policy_from_variant_labor(base['labor'],include_attachment_restore=True))
    config['repair_scoring']['lookup_categories']['gasket']=['E09','B01']
    return config
