"""Retain the seal evidence at each recorded successful cover refit.

Only a small discrete projection is needed. Later inspection, cleaning or
replacement cannot retrospectively make an earlier refit correct. No producer
score or producer validity flag participates in this calculation.
"""
from copy import deepcopy
from .independent import finite, public_body_map


def cover_refits(config, initial, actions):
    if initial is None:
        return {'available': False, 'reason': 'initial_state_missing', 'refits': {}}
    definitions = {p['id']: p for p in config['geometry']['parts']}
    originals = {p for p, d in definitions.items() if d['role'] == 'cover_gasket_old'}
    replacements = {p for p, d in definitions.items() if d['role'] == 'cover_gasket_new'}
    covers = {p for p, d in definitions.items() if d['role'] == 'valve_cover'}
    tracked = originals | replacements | covers
    original = next(iter(originals)) if len(originals) == 1 else None
    aliases = public_body_map(config)
    bodies = {p: deepcopy(initial['parts'][p]) for p in tracked}
    face = deepcopy(initial['surfaces']['cover_face'])
    source_original = config.get('benchmark_removal', {}).get('source_to_body', {}).get('valve_cover_gasket_old')
    binding = initial.get('benchmark_removal', {}).get('replacements', {}).get('valve_cover_gasket_old', source_original)
    removed, inspected, treated, exchanged = None, None, None, None
    output = {}
    for row in actions:
        if row['result']['ok'] is not True:
            continue
        args = {key: aliases.get(value, value) if key in ('part_id', 'replacement_id', 'target') and type(value) is str else value
                for key, value in row['input'].items()}
        name, seq = row['name'], row['seq']
        pid = args.get('part_id')
        carried = row['result'].get('carried_body_ids', [])
        carried = carried if type(carried) is list else []
        moving = {p for p in [pid, *carried] if type(p) is str and p in tracked}
        if name in ('remove', 'install'):
            for body in moving:
                bodies[body]['location'] = 'assembly' if name == 'install' else 'tray'
            if name == 'remove' and pid == original:
                bodies[pid]['location'] = 'waste'
            if name == 'remove' and original in moving:
                removed = seq
        elif name == 'replace' and pid in originals:
            new = args.get('replacement_id')
            if new in replacements:
                bodies[pid]['location'], bodies[new]['location'] = 'waste', 'tray'
                binding, exchanged = new, (seq, pid, new)
        elif name == 'inspect' and args.get('target') == original:
            inspected = (seq, row['result'].get('observation', {}).get('damaged') is False)
        elif name == 'clean' and args.get('target') == 'cover_face':
            face.update(residue_fraction=0, dry=True,
                        tube_seals_oiled=args.get('oil', False),
                        cam_holder_corner_sealant=args.get('sealant') == 'cam_holder_corners')
            if args.get('protect_openings') is not True:
                count = face.get('debris_count')
                face['debris_count'] = count + 1 if type(count) is int else None
            if args.get('method') == 'abrasive_disc':
                face['damaged'] = True
            treated = (seq, args)
        if name != 'install' or not (moving & (originals | replacements)):
            continue
        active = [p for p in originals | replacements if bodies[p].get('location') == 'assembly']
        body = active[0] if len(active) == 1 else None
        route = 'inspected_original' if body == original and body is not None else 'new' if body in replacements else 'unresolved'
        inspection_valid = bool(inspected and removed is not None and removed < inspected[0] < seq and inspected[1])
        treatment_valid = bool(treated and removed is not None and removed < treated[0] < seq
            and treated[1].get('protect_openings') is True and treated[1].get('oil') is True
            and treated[1].get('sealant') == 'cam_holder_corners'
            and face.get('tube_seals_oiled') is True and face.get('cam_holder_corner_sealant') is True
            and finite(face.get('residue_fraction')) and face['residue_fraction'] == 0
            and face.get('dry') is True and face.get('damaged') is False
            and type(face.get('debris_count')) is int and face['debris_count'] == 0)
        new_valid = bool(route == 'new' and exchanged and removed is not None
            and removed < exchanged[0] < seq and exchanged[1:] == (original, body)
            and bodies[original].get('location') == 'waste')
        requirements = {
            'one_active_seal': body is not None,
            'source_position_binding': original is not None and source_original == original and binding == body,
            'refit_after_removal': removed is not None and removed < seq,
            'serviceable_seal': body is not None and bodies[body].get('damaged') is False,
            'current_cycle_treatment': treatment_valid,
            'permitted_route': inspection_valid if route == 'inspected_original' else new_valid}
        evidence = [seq] + [value for value in (removed, inspected[0] if inspected else None,
                    treated[0] if treated else None, exchanged[0] if exchanged else None) if value is not None]
        output[seq] = {'passed': all(requirements.values()), 'requirements': requirements,
                       'route': route, 'active_body': body, 'cycle_start': removed,
                       'evidence_sequences': sorted(set(evidence)),
                       'scope': 'Recorded discrete seal/body/face transitions at this refit only'}
    return {'available': True, 'refits': output}
