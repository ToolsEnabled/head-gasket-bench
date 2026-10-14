import re


def validate_geometry(g):
    if g.get('schema') != 'hgj/geometry/v1' or g.get('qualification') not in ('cad-derived', 'software-fixture'):
        raise ValueError('Unqualified geometry schema')
    parts = g['parts']; ids = [p['id'] for p in parts]
    if not ids or len(ids) != len(set(ids)): raise ValueError('Duplicate or empty body inventory')
    by_id = {p['id']: p for p in parts}
    for p in parts:
        if p.get('precedence_status')=='unknown' or p.get('unknown_fields'):
            if p['removable'] or p['role'] in ('head','block','timing_belt'):
                raise ValueError('Required service geometry is unresolved: '+p['id'])
        if type(p['installed']) is not bool or type(p['removable']) is not bool: raise ValueError('Invalid part flags')
        for k in ('requires_removed', 'requires_installed'):
            if len(set(p[k])) != len(p[k]) or any(x not in by_id or x == p['id'] for x in p[k]):
                raise ValueError('Invalid dependency endpoint')
    def visit(pid, trail, visited):
        if pid in trail: raise ValueError('Removal cycle')
        if pid in visited: return
        for other in by_id[pid]['requires_removed']: visit(other, trail | {pid}, visited)
        visited.add(pid)
    visited = set()
    for pid in ids: visit(pid, set(), visited)
    fasteners = g['fasteners']; seen = set(); seq = set()
    for f in fasteners:
        if f['id'] not in by_id or f['id'] in seen: raise ValueError('Invalid fastener body identity')
        seen.add(f['id'])
        if type(f.get('service_required',True)) is not bool: raise ValueError('Invalid service-required flag')
        if f.get('service_required',True) is False:
            if by_id[f['id']]['removable']: raise ValueError('Retained fastener cannot be a removable service part')
            continue
        if f.get('unknown_fields'): raise ValueError('Required fastener fields are unresolved')
        key = (f['group'], f['sequence_index'])
        if key in seq or f['sequence_index'] < 1:
            raise ValueError('Invalid fastener mapping')
        if f['washer_id'] not in by_id or any(x not in by_id for x in f['holds']): raise ValueError('Unknown fastener mate')
        if not all(type(f['thread'][k]) in (int, float) and f['thread'][k] > 0 for k in ('diameter_mm','pitch_mm','length_mm')):
            raise ValueError('Unknown thread dimensions')
        seq.add(key)
    head = [f for f in fasteners if f['group'] == 'head' and f.get('service_required',True)]
    if sorted(f['sequence_index'] for f in head) != list(range(1, 11)): raise ValueError('Incomplete head sequence mapping')
    roles = {p['role'] for p in parts}
    if not {'head','block','gasket_old','gasket_new','gasket_wrong','timing_belt','valve_cover','head_bolt','head_washer'} <= roles:
        raise ValueError('Missing service roles')
    carried_owners={}
    for carrier in parts:
        children=carrier.get('carried_body_ids',[])
        if not isinstance(children,list) or len(children)!=len(set(children)):
            raise ValueError('Invalid carried body list')
        if not children:continue
        if not carrier['removable']:raise ValueError('Carrier is not removable')
        for child in children:
            if child not in by_id or child==carrier['id'] or child in carried_owners or by_id[child].get('carried_body_ids'):
                raise ValueError('Carried bodies require one flat unique carrier')
            if child in carrier['requires_removed'] or by_id[child]['installed']!=carrier['installed']:
                raise ValueError('Carried body contradicts withdrawal or initial location')
            carried_owners[child]=carrier['id']
        if any(f['id'] in children and f['group']=='head' and f.get('service_required',True) for f in fasteners):
            raise ValueError('Required head bolts cannot travel with the head')
        if g['qualification']=='cad-derived':
            e=carrier.get('carried_evidence',{});sources={s['id'] for s in g['sources']}
            if e.get('source_id') not in sources or e.get('qualification')!='cad-derived' or not re.fullmatch('[0-9a-f]{64}',e.get('receipt_sha256','')):
                raise ValueError('Unverified carried-body withdrawal receipt')
    if g['qualification'] == 'cad-derived':
        sources = {s['id']: s for s in g['sources']}
        if not re.fullmatch('[0-9a-f]{64}', g['engine_sha256']): raise ValueError('Missing engine hash')
        for p in parts:
            if p['source_id'] not in sources: raise ValueError('Missing part source')
        evidence = {(e['part_id'],e['blocker_id']):e for e in g.get('edge_evidence', [])}
        for p in parts:
            for blocker in p['requires_removed']:
                e = evidence.get((p['id'], blocker))
                if not e or e['qualification'] != 'cad-derived' or not re.fullmatch('[0-9a-f]{64}', e['receipt_sha256']):
                    raise ValueError('Unverified withdrawal precedence')
    return by_id
