"""Bind the complete labelled L1 removal inventory to discrete game bodies."""
import copy
import hashlib
import json
from pathlib import Path
from hgj.codec import digest

SCRIPT_ACTIONS_SHA256 = '535dd27f559733a8c1d617b88cc99ad2423012e5fc81a2cd6fbb842c4c9b3572'
POLICY_SHA256 = '1f8c6a752db366b82ab72cf824070449a315c8ff2ecd62e8fbbec5ad13e753b6'
# The public checklist is the sealed cad96-removal-policy-v4 job-checklists.json with its
# 625 basis citations respelled from a machine-local shared-folder path to the neutral
# label benchmark-policy/<document> (STUDY-DESIGN-v2.md, CHECKPOINTS-SIGNOFF.md); no rule,
# body or requirement changed. Sealed raw pin of the original bytes:
# fbc5bdfee625cc84fd2ca29f0bb7970585aad10d3be1994bfb720d202ddee3dd
CHECKLIST_SHA256 = 'f98311db00086a26346ce3c6b8cf4691306ae8f060e71b02720159a42c9b4b69'


def augment(config, root, source_dir=None):
    source_dir=Path(source_dir) if source_dir is not None else None
    raw=((source_dir/'policy.json') if source_dir else (Path(root)/'data/benchmark-removal-policy.json')).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=POLICY_SHA256:
        raise ValueError('L1 source policy bytes differ')
    policy=json.loads(raw)
    aliases={'block':'block_casting','head':'head_casting','cover':'valve_cover',
             'belt':'timing_belt','gasket_old':'gasket_old','cover_gasket_old':'valve_cover_gasket_old',
             'dowel_01':'dowel_01','dowel_02':'dowel_02'}
    for index in range(1,11):
        aliases[f'hb{index:02}']=f'bolt_{index:02}'
        aliases[f'hw{index:02}']=f'washer_{index:02}'
    for index in range(1,6):
        aliases[f'cb{index:02}']=f'cover_fastener_{index:02}'
        aliases[f'cw{index:02}']=f'cover_grommet_{index:02}'
    source_to_body={source:body for body,source in aliases.items()}
    definitions={part['id']:part for part in config['geometry']['parts']}
    for row in policy['parts']:
        source=row['id'];pid=source_to_body.get(source,source)
        if pid not in definitions:
            part={'id':pid,'role':'source_component','installed':True,
                  'removable':row['mode']=='individual','requires_removed':[],
                  'requires_installed':[], 'condition':None,
                  'source_id':'L1-labelled-benchmark-removal-policy'}
            config['geometry']['parts'].append(part);definitions[pid]=part
        part=definitions[pid]
        if pid.startswith('cw') and source.startswith('cover_grommet_'):
            part['legacy_fixture_role']=part['role'];part['role']='cover_grommet'
        part.update(l1_body_id=source,l1_selected_body=True,l1_binding=copy.deepcopy(row['binding']),
                    benchmark_basis=copy.deepcopy(row['basis']))
        # Authored fixed dowels remain retained; source permission is carried in
        # the separate benchmark namespace, not physical precedence fields.
        source_to_body[source]=pid
    script_raw=((source_dir/'removal-fixture.json') if source_dir else (Path(root)/'data/benchmark-removal-script.json')).read_bytes()
    script=json.loads(script_raw)['actions']
    if digest(script)!=SCRIPT_ACTIONS_SHA256:
        raise ValueError('L1 example action commitment differs')
    checklist_raw=((source_dir/'job-checklists.json') if source_dir else (Path(root)/'data/benchmark-reassembly-checklist.json')).read_bytes()
    if hashlib.sha256(checklist_raw).hexdigest()!=CHECKLIST_SHA256:
        raise ValueError('L1 v4 reassembly checklist bytes differ')
    checklist=json.loads(checklist_raw)
    reassembly={
        'source_raw_sha256':CHECKLIST_SHA256, 'source_version':'cad96-removal-policy-v4',
        'requirements':[{k:copy.deepcopy(row[k]) for k in ('original_id','original_may_be_reinstalled',
            'replacement_rule','required_at_completion','basis')}
                         | {'replacement_options':copy.deepcopy(row.get('replacement_options',[]))} for row in checklist['reinstall_requirements']],
        'release_ids':[row['id'] for row in checklist['released_states_to_restore_or_supersede']],
        'physical_qualification':False}
    config['benchmark_removal']={
        'schema':'hgj/benchmark-removal/v1','policy':policy,'script':script,
        'script_raw_sha256':hashlib.sha256(script_raw).hexdigest(),'policy_sha256':POLICY_SHA256,
        'policy_semantic_sha256':digest(policy),'source_to_body':source_to_body,
        'physical_qualification':False,'reassembly':reassembly,
        'qualification':'L1 labelled benchmark rules; physical release and movement are not simulated'}
    config['benchmark_task']['source_removal_policy_status']='L1 labelled benchmark policy integrated'
    config['factors']['turn_budget']=1024
    config['factors']['tool_call_limit']=1024
    return config


def expand_actions(config, original, root):
    """Merge actual technician operations into the L1 removal example.

    The producer example supplies transitions, not a repair solution or time.
    All service work remains explicit public calls and is charged separately.
    """
    source=config['benchmark_removal']['source_to_body']
    script=config['benchmark_removal']['script']
    from hgj.game import Game
    metadata=Game(config)
    public=metadata.public_id
    first_remove=next(i for i,row in enumerate(original) if row['name']=='torque' and row['input'].get('mode')=='loosen')
    old_gasket=next(i for i,row in enumerate(original) if row['name']=='remove' and row['input']['part_id']=='gasket_old')
    # Keep look/stock/search observations, and explicitly establish TDC before
    # any release fixture tries to record that preparation.
    preamble=original[:first_remove]
    timing_setup=[row for row in original[:old_gasket] if row['name'] in ('set_timing','check_timing')
                  or row['name']=='inspect' and row['input'].get('target')=='belt']
    loosen={group:[row for row in original if row['name']=='torque' and row['input'].get('mode')=='loosen'
                   and metadata.fasteners[row['input']['part_id']]['group']==group] for group in ('head','cover')}
    actions=copy.deepcopy(preamble+timing_setup+loosen['cover'])
    groups=[]
    head_loosened=False
    belt_exchange=[row for row in original[:old_gasket] if row['name']=='replace' and row['input'].get('part_id')=='belt']
    for row in script:
        name=row['action']
        if name=='establish_condition':
            actions.append({'name':'prepare_condition','input':{'condition_id':row['id']}})
        elif name=='release_attachment':
            if row['id'].startswith('thread:bolt_') and not head_loosened:
                actions.extend(copy.deepcopy(loosen['head']));head_loosened=True
            actions.append({'name':'release_attachment','input':{'release_id':row['id']}})
        else:
            pid=source[row['part_id']]
            actions.append({'name':'remove','input':{'part_id':public(pid),'route_id':row['route_id']}})
            groups.append((pid,[source[x] for x in row['moving_body_ids']]))
            if pid=='belt':
                actions.extend(copy.deepcopy(belt_exchange))
    # After the head and gasket are off, reuse the explicit service script.
    # Washers/grommets travel with their fasteners. The removed cover gasket is
    # already on its carrier tray and must be replaced rather than removed twice.
    tail=copy.deepcopy(original[old_gasket+1:])
    carried={child for pid,members in groups for child in members if child!=pid}
    installed_main=set()
    for row in tail:
        name,args=row['name'],row['input']
        pid=metadata.public_to_body.get(args.get('part_id'))
        if name=='install' and pid in carried:
            continue
        if name=='finish':
            for leader,members in reversed(groups):
                if leader in installed_main or leader in ('gasket_old','cover_gasket_old'):
                    continue
                if leader in ('head','belt') and leader in installed_main:
                    continue
                actions.append({'name':'install','input':{'part_id':public(leader)}})
            for release in reversed([x['id'] for x in script if x['action']=='release_attachment']):
                actions.append({'name':'restore_attachment','input':{'release_id':release}})
        actions.append(row)
        if name=='install':
            origin=metadata.part_defs[pid].get('replacement_for',pid)
            if metadata.part_defs[pid]['role'].startswith('gasket_'):
                origin='gasket_old'
            if metadata.part_defs[pid]['role'].startswith('cover_gasket_'):
                origin='cover_gasket_old'
            installed_main.add(origin)
    return actions
