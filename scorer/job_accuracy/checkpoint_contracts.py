"""Explicit signed-rule versions; recorded runs retain their selected rules."""
from .independent import check,finite,public_body_map

ORIGINAL='signoff-20261009'
AMENDMENT1='amendment-1-20261009'
AMENDMENT2='amendment-2-20261010'
ORDERS=((10,9,8,7,6,5,4,3,2,1),(10,9,8,7,6,3,4,5,2,1))


def selected_revision(value):
    check(type(value) is str and value in (ORIGINAL,AMENDMENT1,AMENDMENT2),'checkpoint-rule-version')
    return value


def documented_loosening(actual,expected,fasteners,same,*,consistent=False):
    """Accept either complete documented order with the reference increments.

    Sequence indices are service positions, not body-name spellings. Each
    reference pass must contain all ten positions exactly once. The reference
    supplies the number of passes and each position's numerical increment.
    The historical per-pass revision permits independent choices. Amendment 2
    requires the same complete documented order for every pass.
    """
    heads={f['sequence_index']:pid for pid,f in fasteners.items()
           if f['group']=='head' and f.get('service_required',True)}
    count=sum(f['group']=='head' and f.get('service_required',True) for f in fasteners.values())
    check(count==10 and set(heads)==set(range(1,11))
          and all(type(f['sequence_index']) is int for f in fasteners.values()
                  if f['group']=='head' and f.get('service_required',True)), 'loosening-service-positions')
    if not expected or len(expected)%10 or len(actual)!=len(expected):return False
    passes=[]
    for start in range(0,len(expected),10):
        rows=expected[start:start+10];by_body={r.get('part_id'):r for r in rows}
        if len(by_body)!=10 or set(by_body)!=set(heads.values()):return False
        if any(set(r)!={'part_id','mode','angle_deg'} or r['mode']!='loosen'
               or not finite(r['angle_deg']) or r['angle_deg']>=0 for r in rows):return False
        passes.append(by_body)
    matching=[{i for i,order in enumerate(ORDERS)
               if same(actual[start:start+10],[group[heads[index]] for index in order])}
              for start,group in zip(range(0,len(actual),10),passes)]
    return bool(set.intersection(*matching)) if consistent else all(matching)


def loosening_step(candidates,rank,position,fasteners,*,consistent=False):
    """Classify one order position without charging a valid incomplete prefix.

    A matching step narrows the candidates. A wrong step is charged but cannot
    silently select an order; the remaining candidates persist for later steps.
    The historical revision resets at each pass; Amendment 2 retains the
    selected order throughout the job.
    Before selection the remaining orders have equal mismatch counts; a match
    selects the closer one, while a mismatch against both keeps the tie.
    The caller retains every earlier mistake and the complete-pass CP04 test.
    """
    if rank==0 or rank%10==0 and not consistent:candidates=tuple(range(len(ORDERS)))
    index=fasteners[position]['sequence_index']
    matches=tuple(i for i in candidates if ORDERS[i][rank%10]==index)
    return (matches or candidates),not bool(matches)


def original_cover_evidence(config,final,actions):
    """Describe existing inspect/clean/carried-refit observations for Amendment 1.

    Source movement consistency remains a separate requirement. This function
    does not turn a discarded body into an installed body or grant CP12 alone.
    """
    parts={p['id']:p for p in config['geometry']['parts']};aliases=public_body_map(config)
    originals={pid for pid,p in parts.items() if p['role']=='cover_gasket_old' and p['installed'] is True}
    covers={pid for pid,p in parts.items() if p['role']=='valve_cover'}
    old=next(iter(originals)) if len(originals)==1 else None
    rows=[]
    for row in actions:
        if row['result']['ok'] is not True:continue
        args={k:aliases.get(v,v) if k in ('part_id','target') and type(v) is str else v
              for k,v in row['input'].items()}
        rows.append({**row,'input':args})
    refits=[r for r in rows if r['name']=='install' and old is not None and
            (r['input'].get('part_id')==old or r['input'].get('part_id') in covers
             and old in r['result'].get('carried_body_ids',[]))]
    refit=max(refits,key=lambda r:r['seq'],default=None);end=refit['seq'] if refit else None
    inspections=[r for r in rows if r['name']=='inspect' and r['input'].get('target')==old
                 and end is not None and r['seq']<end]
    inspection=max(inspections,key=lambda r:r['seq'],default=None)
    cleanings=[r for r in rows if r['name']=='clean' and r['input'].get('target')=='cover_face'
               and end is not None and r['seq']<end]
    cleaning=max(cleanings,key=lambda r:r['seq'],default=None)
    removed=[r['seq'] for r in rows if r['name']=='remove' and old is not None and
             (r['input'].get('part_id')==old or old in r['result'].get('carried_body_ids',[]))]
    later_inspections=[r for r in rows if r['name']=='inspect' and r['input'].get('target')==old
                       and end is not None and r['seq']>end]
    latest=later_inspections[-1] if later_inspections else inspection
    requirements={
        'one_original_installed':old is not None and final['parts'].get(old,{}).get('location')=='assembly',
        'no_replacement_cover_also_installed':not any(final['parts'].get(pid,{}).get('location')=='assembly'
            for pid,p in parts.items() if p['role']=='cover_gasket_new'),
        'original_condition_observed_serviceable':old is not None and final['parts'].get(old,{}).get('damaged') is False,
        'inspection_before_refit':inspection is not None and inspection['result'].get('observation',{}).get('damaged') is False,
        'latest_inspection_serviceable':latest is not None and latest['result'].get('observation',{}).get('damaged') is False,
        'current_refit_observed':end is not None and bool(removed) and end>max(removed),
        'sealant_before_refit':cleaning is not None and cleaning['input'].get('sealant')=='cam_holder_corners',
        'final_sealant_observed':final.get('surfaces',{}).get('cover_face',{}).get('cam_holder_corner_sealant') is True}
    return {'original_cover_gasket':old,'requirements':requirements,'refit_sequence':end,
            'evidence_sequences':sorted({r['seq'] for r in refits+inspections+cleanings+later_inspections}|set(removed)),
            'scope':'Existing discrete action observations; complete source replay and other reassembly requirements remain separate'}


def cover_service_evidence(config,final,actions):
    """Resolve either permitted body at the one cover-gasket service position."""
    parts={p['id']:p for p in config['geometry']['parts']}
    bodies={pid for pid,p in parts.items() if p['role'] in ('cover_gasket_old','cover_gasket_new')}
    originals={pid for pid in bodies if parts[pid]['role']=='cover_gasket_old' and parts[pid]['installed'] is True}
    active=[pid for pid in bodies if final['parts'].get(pid,{}).get('location')=='assembly']
    body=active[0] if len(active)==1 else None
    original=next(iter(originals)) if len(originals)==1 else None
    aliases=public_body_map(config)
    installed=[r for r in actions if r['result']['ok'] is True and r['name']=='install'
               and aliases.get(r['input'].get('part_id'),r['input'].get('part_id'))==body]
    reused=original_cover_evidence(config,final,actions)
    reuse=body is not None and body==original
    replacement=(body is not None and parts[body]['role']=='cover_gasket_new')
    requirements={
        'one_service_position':original is not None,
        'one_installed_cover_gasket':body is not None,
        'permitted_cover_service':all(reused['requirements'].values()) if reuse else replacement,
        'replaced_original_discarded':reuse or original is not None and final['parts'].get(original,{}).get('location')=='waste',
        'replacement_install_observed':reuse or bool(installed)}
    return {'body_ids':sorted(bodies),'active_body':body,'mode':'inspected_original' if reuse else 'new' if replacement else 'unresolved',
            'requirements':requirements,'reuse_evidence':reused if reuse else None,
            'evidence_sequences':sorted({r['seq'] for r in installed}|(set(reused['evidence_sequences']) if reuse else set()))}
