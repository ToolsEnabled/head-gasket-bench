import math

def obj(props, required=()):
    return {'type': 'object', 'properties': props, 'required': list(required), 'additionalProperties': False}

S = {'type': 'string', 'minLength': 1, 'maxLength': 200}
N = {'type': 'number'}
B = {'type': 'boolean'}
DEFINITIONS = [
    ('look', 'View engine parts, named surface IDs, and the job clock.', obj({})),
    ('inspect', 'Inspect an accessible component or surface using an ID from look.', obj({'target': S}, ['target'])),
    ('measure', 'Measure a surface, fastener, or head-gasket stock using an ID from look or parts_bin.', obj({'target': S, 'kind': {'type': 'string', 'enum': ['flatness', 'bolt_stretch', 'bolt_free_length', 'roughness', 'gasket_bore', 'gasket_thickness']}}, ['target', 'kind'])),
    ('search_service_info', 'Look up procedures, specifications and service diagrams.', obj({'query': S}, ['query'])),
    ('remove', 'Withdraw an accessible, released part to the service tray.', obj({'part_id': S, 'route_id': S}, ['part_id'])),
    ('install', 'Fit one body from the tray or supply. Timing phases are in degrees.', obj({'part_id': S, 'orientation': {'type': 'string', 'enum': ['up', 'down']}, 'cam_phase_deg': N, 'crank_phase_deg': N}, ['part_id'])),
    ('clean', 'Clean a face or prepare a removed fastener. Protect openings and select method; oil applies to fastener threads and washer faces. Cover sealing uses oil and sealant at cam-holder corners.', obj({'target': S, 'method': {'type': 'string', 'enum': ['plastic_scraper', 'solvent', 'abrasive_disc', 'thread_brush']}, 'protect_openings': B, 'oil': B, 'sealant': {'type':'string','enum':['none','cam_holder_corners']}}, ['target', 'method'])),
    ('replace', 'Exchange a removed body for one distinct supply body.', obj({'part_id': S, 'replacement_id': S}, ['part_id', 'replacement_id'])),
    ('torque', 'Apply one fastener operation. Tighten requires started group threads and value_N_m; loosen uses a negative angle_deg. Global order is the actual call order.', obj({'part_id': S, 'mode': {'type': 'string', 'enum': ['tighten', 'loosen']}, 'value_N_m': N, 'angle_deg': N}, ['part_id', 'mode'])),
    ('check_timing', 'Turn the crank by complete revolutions and inspect timing marks.', obj({'crank_revolutions': {'type': 'integer', 'minimum': 1, 'maximum': 6}}, ['crank_revolutions'])),
    ('parts_bin', 'List available replacement stock and part markings.', obj({})),
    ('machine_head', 'Send the cleaned, removed head for the configured bench machining service.', obj({'part_id': S}, ['part_id'])),
    ('set_timing', 'Set crank and cam timing positions before disassembly; angles are in degrees.', obj({'cam_phase_deg': N, 'crank_phase_deg': N}, ['cam_phase_deg', 'crank_phase_deg'])),
    ('tension_belt', 'Complete the benchmark timing-belt tensioning operation.', obj({'part_id': S}, ['part_id'])),
    ('prepare_condition', 'Perform a named benchmark preparation step.', obj({'condition_id':S}, ['condition_id'])),
    ('release_attachment', 'Release a named attachment after checking its benchmark prerequisites.', obj({'release_id':S}, ['release_id'])),
    ('restore_attachment', 'Restore a released attachment after reassembly; torque checks remain separate.', obj({'release_id':S}, ['release_id'])),
    ('finish', 'End the repair and return a compact score summary plus a reference to the full saved record.', obj({})),
]


def validate(name, args):
    definition = next((x for x in DEFINITIONS if x[0] == name), None)
    if definition is None: raise ValueError(f'Unknown tool name: {name!r}; expected a name from tools/list')
    if not isinstance(args, dict): raise ValueError(f'Tool {name!r} arguments must be an object')
    schema = definition[2]
    unexpected=set(args)-set(schema['properties']); missing=set(schema['required'])-set(args)
    if unexpected or missing:
        raise ValueError(f'Tool {name!r} arguments: unexpected={sorted(unexpected)!r}, missing={sorted(missing)!r}')
    for key, value in args.items():
        p = schema['properties'][key]; t = p['type']
        good = ((t == 'string' and isinstance(value, str) and 0 < len(value) <= 200) or
                (t == 'boolean' and type(value) is bool) or
                (t == 'number' and type(value) in (int, float) and math.isfinite(value)) or
                (t == 'integer' and type(value) is int))
        if not good:
            limits=' with length 1..200' if t=='string' else ' (finite)' if t=='number' else ''
            raise ValueError(f'Argument {key!r} for {name!r} must be {t}{limits}')
        if 'enum' in p and value not in p['enum']:
            raise ValueError(f'Argument {key!r} for {name!r} has unsupported value {value!r}; published choices={p["enum"]!r}')
        if 'minimum' in p and value < p['minimum'] or 'maximum' in p and value > p['maximum']:
            raise ValueError(f'Argument {key!r} for {name!r} is outside published range {p.get("minimum")}..{p.get("maximum")}')
    if name == 'torque':
        if args['mode'] == 'tighten' and ('value_N_m' not in args or args['value_N_m'] < 0 or 'angle_deg' in args):
            raise ValueError('Torque mode tighten requires nonnegative value_N_m and forbids angle_deg')
        if args['mode'] == 'loosen' and ('angle_deg' not in args or args['angle_deg'] >= 0 or 'value_N_m' in args):
            raise ValueError('Torque mode loosen requires negative angle_deg and forbids value_N_m')
