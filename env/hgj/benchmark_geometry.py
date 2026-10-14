"""Operational L1 benchmark rules with separate source-body identities.

The source evaluator is pure. This adapter owns labelled discrete transitions,
not physical withdrawal or thread-release simulation.
"""
import copy
from .codec import digest
from .removal_policy import validate_policy, evaluate_removal, evaluate_release

TOOLS = frozenset(('prepare_condition','release_attachment','restore_attachment'))


def initialize(game):
    spec = game.config.get('benchmark_removal')
    if spec is None:
        return
    policy = spec['policy']
    if digest(policy) != spec['policy_semantic_sha256']:
        raise ValueError('Benchmark removal policy commitment differs')
    selected=[p['l1_body_id'] for p in game.part_defs.values() if p.get('l1_selected_body')]
    if len(selected)!=len(set(selected)):
        raise ValueError('Duplicate selected L1 body identity')
    bindings = {p['l1_body_id']:p['l1_binding'] for p in game.part_defs.values()
                if p.get('l1_selected_body')}
    game._removal_rows = validate_policy(policy, bindings)
    game._source_to_body = {p['l1_body_id']:p['id'] for p in game.part_defs.values()
                            if p.get('l1_selected_body')}
    game._releases = {row['id']:row for row in policy['release_action_definitions']}
    game.state['benchmark_removal'] = {
        'policy_sha256':spec['policy_sha256'], 'physical_qualification':False,
        'released':{key:False for key in policy['release_actions']},
        'conditions':{key:False for key in policy['condition_ids']},
        'replacements':{}, 'movements':[], 'attachment_history':[]}


def source_id(game, pid):
    original=game.part_defs[pid].get('l1_body_id')
    if original is not None:
        return original
    return next((source for source,current in game.state.get('benchmark_removal',{}).get('replacements',{}).items()
                 if current==pid),None)


def body(game, source):
    state=game.state['benchmark_removal']
    return state['replacements'].get(source,game._source_to_body[source])


def state_for(game):
    current=game.state['benchmark_removal']
    return {'installed':{source:game.state['parts'][body(game,source)]['location']=='assembly'
                         for source in game._source_to_body},
            'released':current['released'], 'conditions':current['conditions']}


def prepare_removal(game,pid,route_id=None):
    source=source_id(game,pid)
    if not source or not game.config.get('benchmark_removal'):
        return None
    decision=evaluate_removal(game._removal_rows[source],state_for(game),route_id)
    game._require(decision['decision']=='ALLOWED_BY_BENCHMARK_RULE',
                  decision['decision']+': source benchmark withdrawal prerequisites are not satisfied')
    selected=decision['allowed_route_ids'][0]
    route=next(row for row in game._removal_rows[source]['routes'] if row['id']==selected)
    return {'source_body_id':source, 'route_id':selected,
            'carried_body_ids':[body(game,child) for child in route.get('carried_body_ids',[])],
            'basis':copy.deepcopy(route['basis']), 'physical_qualification':False}


def record_removal(game,pid,decision):
    if decision is None:
        return
    game.state['benchmark_removal']['movements'].append({
        'seq':len(game.records)+1, 'action':'remove', 'body_id':pid, **copy.deepcopy(decision)})


def carried_for_install(game,pid):
    return [child for child,row in game.state['parts'].items() if row.get('carried_with')==pid
            and row['location']=='tray']


HEAD_RELATIVE_SOURCES = frozenset(('lost_motion_holder', *(f'cam_carrier_{i:02d}' for i in range(1,6))))


def installation_context_allowed(game, pid, carried):
    """Engine-position installation only; no implicit bench assembly transition."""
    if not game.config.get('benchmark_removal'):
        return True
    moving={pid,*carried}
    if not any(source_id(game, child) in HEAD_RELATIVE_SOURCES for child in moving):
        return True
    if 'head_casting' not in game._source_to_body:
        return False
    head=body(game,'head_casting')
    return (head in game.part_defs and game.part_defs[head]['role'] in ('head','head_supply')
            and head in game.state['parts']
            and (game.state['parts'][head]['location']=='assembly' or head in moving))


def exchange(game,old,new):
    if not game.config.get('benchmark_removal'):
        return
    source=source_id(game,old)
    if source:
        game.state['benchmark_removal']['replacements'][source]=new
    for child,row in game.state['parts'].items():
        if row.get('carried_with')==old and row['location']=='tray':
            row['carried_with']=new


def record_install(game,pid,carried):
    if not game.config.get('benchmark_removal'):
        return
    source=source_id(game,pid)
    if source:
        game.state['benchmark_removal']['movements'].append({
            'seq':len(game.records)+1, 'action':'install', 'body_id':pid,
            'source_body_id':source, 'carried_body_ids':list(carried),
            'basis':'Provisional reassembly at the recorded service position',
            'physical_qualification':False})


def dispatch(game,name,args):
    current=game.state['benchmark_removal']
    ident=args['condition_id'] if name=='prepare_condition' else args['release_id']
    if name=='prepare_condition':
        game._require(ident in current['conditions'],
                      f'Unknown condition_id {ident!r}; expected a preparation ID from look')
        if ident=='timing_marks_recorded':
            timing=game.state['timing']
            checks=timing['checks']
            game._require(timing.get('set_seq') is not None,
                          f'Preparation {ident!r} has no recorded explicit timing setup')
            game._require(any(
                row['seq']>timing['set_seq'] and abs(row.get('phase_error_deg',float('inf'))) <= game.config['policy']['timing_tolerance_deg']
                for row in checks), f'Preparation {ident!r} has no aligned timing observation after the latest setup')
        current['conditions'][ident]=True
        receipt={'seq':len(game.records)+1,'action':name,'condition_id':ident,
                 'basis':'Explicit benchmark preparation action; physical performance is not simulated'}
    else:
        game._require(ident in game._releases,
                      f'Unknown release_id {ident!r}; expected an attachment ID from look')
        if name=='release_attachment':
            decision=evaluate_release(game._releases[ident],state_for(game))
            game._require(decision['decision']=='ALLOWED_BY_BENCHMARK_RULE',
                          decision['decision']+': attachment prerequisites are not satisfied')
            # Scored head and cover threads must actually be loosened in the
            # action record before their source release can be asserted.
            for source,pid in game._source_to_body.items():
                active=body(game,source)
                if ident in ('thread:'+source,'thread:'+source+':block_casting') and active in game.fasteners:
                    game._require(game.state['bolts'][active]['turns'] <= 1e-9,
                                  'Scored fastener must be disengaged before recording thread release')
            current['released'][ident]=True
        else:
            game._require(current['released'][ident] is True,
                          f'Attachment {ident!r} is not currently released')
            installed=state_for(game)['installed']
            game._require(all(installed.values()),
                          f'Attachment {ident!r} cannot be restored: {sum(not value for value in installed.values())} selected service positions are not installed')
            current['released'][ident]=False
        receipt={'seq':len(game.records)+1,'action':name,'release_id':ident,
                 'basis':copy.deepcopy(game._releases[ident]['basis'])}
    receipt['physical_qualification']=False
    current['attachment_history'].append(receipt)
    return {'operation':'completed','receipt':copy.deepcopy(receipt)}


def observation(game,pid=None):
    if not game.config.get('benchmark_removal'):
        return {}
    current=game.state['benchmark_removal']
    if pid is None:
        return {'benchmark_preparations':copy.deepcopy(current['conditions']),
                'benchmark_attachments':[{'id':key,'released':value,
                     'preconditions':copy.deepcopy(game._releases[key]['preconditions']),
                     'basis':copy.deepcopy(game._releases[key]['basis'])}
                    for key,value in current['released'].items()],
                'removal_rule_scope':'Labelled benchmark rules; inspect a source component for its routes'}
    source=source_id(game,pid)
    if source is None:
        return {}
    row=game._removal_rows[source]
    return {'source_body_id':source,'job_disposition':row['mode'],
            'carrier_source_ids':row.get('carrier_ids',[]),
            'benchmark_removal_routes':copy.deepcopy(row['routes']),
            'rule_basis':copy.deepcopy(row['basis']),
            'installation_context':({'target':'engine service position',
                'requires':'compatible head installed or in the same moving set',
                'basis':'L1 authored head-relative receiver/carrier context',
                'bench_assembly_supported':False}
                if source in HEAD_RELATIVE_SOURCES else None),
            'physical_qualification':False}


def can_exchange_carrier(game,old,new):
    if not game.config.get('benchmark_removal'):
        return False
    olddef,newdef=game.part_defs[old],game.part_defs[new]
    origin=olddef.get('replacement_for',old)
    head_exchange=olddef['role'] in ('head','head_supply') and newdef['role']=='head_supply'
    fastener_exchange=(old in game.fasteners and olddef['role'] in ('head_bolt','cover_bolt')
                       and newdef['role']==olddef['role'])
    if not (head_exchange or fastener_exchange) or newdef.get('replacement_for')!=origin:
        return False
    movement=next((row for row in reversed(game.state['benchmark_removal']['movements'])
                   if row['action']=='remove' and row['body_id']==old),None)
    if movement is None:
        return False
    actual={pid for pid,row in game.state['parts'].items() if row.get('carried_with')==old}
    expected=set(movement['carried_body_ids'])
    return actual==expected and all(game.state['parts'][pid]['location']=='tray' for pid in actual)
