"""Discrete study actions with explicit benchmark conditions; no engine model."""
import copy

EXTRA_TOOLS = frozenset(('parts_bin', 'machine_head', 'set_timing', 'tension_belt'))


def effective_role(definition):
    role = definition['role']
    return {'head_supply': 'head', 'timing_belt_supply': 'timing_belt'}.get(role, role)


def initialize(game, variant):
    if not game.config.get('benchmark_task'):
        return
    game.state['service_replacements'] = {}
    game.state['service_receipts'] = []
    for pid, definition in game.part_defs.items():
        if definition.get('available_in_bin') is False:
            game.state['parts'][pid]['location'] = 'unavailable'
    game.state['timing'].update(belt_id=game.role('timing_belt'), tensioned=True, belt_tensioned=True)
    belt = game.role('timing_belt')
    game.state['parts'][belt]['damaged'] = variant.get('worn_timing_belt', False)
    game.state['parts'][belt]['condition_basis'] = 'Explicit benchmark starting condition'


def after_replace(game, old, new):
    role = effective_role(game.part_defs[old])
    if not game.config.get('benchmark_task') or role not in ('head', 'timing_belt'):
        return
    origin = game.part_defs[old].get('replacement_for', old)
    game._require(game.part_defs[new].get('replacement_for') == origin,
                  'Replacement does not match the component service position')
    game.state['service_replacements'][origin] = new
    if role == 'head':
        surface = game.part_defs[new]['replacement_surface']
        game.state['surfaces']['head_face'] = copy.deepcopy(surface)
    else:
        game.state['timing'].update(belt_id=new, tensioned=False, belt_tensioned=False)
    game.state['service_receipts'].append({
        'seq': len(game.records)+1, 'operation':'replace', 'old_body_id':old,
        'new_body_id':new, 'service_position':origin,
        'qualification':'Distinct benchmark supply body; mechanical fit is not validated'})


def dispatch(game, name, args):
    if name == 'parts_bin':
        return {'parts':[
            {'id':game.public_id(pid), 'description':definition.get('catalog', {}).get('description', 'Replacement stock'),
             'catalog':copy.deepcopy(definition.get('catalog', {}))}
            for pid, definition in sorted(game.part_defs.items())
            if game.state['parts'][pid]['location'] == 'supply']}
    if name == 'machine_head':
        pid=args['part_id']; part=game._part(pid)
        game._require(effective_role(game.part_defs[pid]) == 'head' and part['location'] == 'tray',
                      'Machining requires the removed head on the service tray')
        spec=game.config['benchmark_task']['machining']
        game._require(spec.get('eligible') is True,
                      'Head machining eligibility is not established for this benchmark state')
        surface=game.state['surfaces']['head_face']
        game._require(surface['residue_fraction'] == 0 and surface['debris_count'] == 0,
                      'Head face must be cleaned before machining')
        before=copy.deepcopy(surface)
        surface.update(warpage_m=spec['result_flatness_m'], roughness_ra_um=spec['result_roughness_ra_um'],
                       residue_fraction=0, debris_count=0, dry=True, damaged=False)
        receipt={'seq':len(game.records)+1, 'operation':'machine_head', 'body_id':pid,
                 'before':before, 'after':copy.deepcopy(surface),
                 'material_removed_m':spec['material_removed_m'], 'basis':copy.deepcopy(spec['basis']),
                 'qualification':'Configured benchmark service result; no material-removal simulation'}
        game.state['service_receipts'].append(receipt)
        return {'operation':'completed', 'service_receipt':copy.deepcopy(receipt)}
    if name == 'set_timing':
        game._require(game.state['parts'][game.role('timing_belt')]['location'] == 'assembly',
                      'Timing setup requires the fitted drive belt')
        game.state['timing'].update({key:args[key] for key in ('cam_phase_deg','crank_phase_deg')})
        game.state['timing']['set_seq']=len(game.records)+1
        return {'operation':'completed', 'qualification':'Discrete benchmark timing setup'}
    if name == 'tension_belt':
        pid=args['part_id']
        game._require(pid == game.role('timing_belt') and game.state['parts'][pid]['location'] == 'assembly',
                      'Tensioning requires the current fitted timing belt')
        game.state['timing'].update(tensioned=True, belt_tensioned=True, tensioned_seq=len(game.records)+1)
        return {'operation':'completed', 'qualification':'Discrete benchmark tensioned state; numeric tension is not specified'}
    raise ValueError('Unknown procedure operation')
