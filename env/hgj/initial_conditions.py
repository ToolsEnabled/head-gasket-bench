"""Transport validation for declared initial conditions, never a physics model."""
import copy
import math
import re
from .codec import canonical,digest


def initial_values(config,parts,fasteners,variant):
    packet=config.get('initial_conditions')
    physical=config.get('admission',{}).get('status')=='validated-physics'
    if packet is None:
        if physical or config['geometry']['qualification']=='cad-derived':
            raise ValueError('Source-bound initial conditions required before joint initialization')
        return None
    if not isinstance(packet,dict) or packet.get('schema')!='hgj/initial-conditions/v1' or packet.get('qualification')!='source-defined':
        raise ValueError('Invalid initial conditions source schema')
    geometry_hash=config.get('identity',{}).get('geometry_sha256',digest(config['geometry']))
    if packet.get('geometry_sha256')!=geometry_hash or packet.get('variant_sha256')!=digest(variant):
        raise ValueError('Initial conditions belong to different geometry or variant')
    if physical:
        expected=config.get('identity',{}).get('initial_conditions_sha256',digest(packet))
        if config['admission'].get('initial_conditions_sha256')!=expected:
            raise ValueError('Initial conditions lack independent admission binding')
    canonical(packet)
    v=packet.get('values',{});sources=packet.get('field_sources',{})
    if not isinstance(v,dict) or set(v)!={'parts','bolts','surfaces','gasket','timing'} or not isinstance(sources,dict):
        raise ValueError('Incomplete initial conditions sections')
    leaves={}
    def visit(value,path):
        if isinstance(value,dict):
            for key,item in value.items():visit(item,path+'/'+key.replace('~','~0').replace('/','~1'))
        elif isinstance(value,list):
            for index,item in enumerate(value):visit(item,path+'/'+str(index))
        else:leaves[path]=value
    visit(v,'')
    if set(sources)!=set(leaves):raise ValueError('Every initial scalar requires exact source provenance')
    for path,value in leaves.items():
        source=sources[path]
        if not isinstance(source,dict) or not re.fullmatch('[a-f0-9]{64}',source.get('sha256','')) or source.get('status') not in ('measured','cited','estimated','unknown') or not isinstance(source.get('note'),str) or not source['note'].strip():
            raise ValueError('Invalid initial field source')
        if (value is None)!=(source['status']=='unknown'):raise ValueError('Unknown initial conditions must be explicit nulls')
    def finite(value):
        try:return type(value) in (int,float) and math.isfinite(value)
        except OverflowError:return False
    def number(value,minimum=0,maximum=None,nullable=False):
        if nullable and value is None:return
        if not finite(value) or value<minimum or maximum is not None and value>maximum:
            raise ValueError('Invalid initial numeric condition')
    def boolean(value,nullable=False):
        if type(value) is not bool and not(nullable and value is None):raise ValueError('Invalid initial condition flag')
    if not isinstance(v['parts'],dict) or set(v['parts'])!=set(parts):raise ValueError('Initial conditions must retain every separate body')
    for pid,p in parts.items():
        row=v['parts'][pid]
        if set(row)!={'location','damaged'} or row['location']!=('assembly' if p['installed'] else 'supply'):
            raise ValueError('Initial body location differs from geometry')
        boolean(row['damaged'],nullable=not p['removable'])
    bolt_ids=set(fasteners)|{pid for pid,p in parts.items() if p['role'] in ('head_bolt','cover_bolt')}
    if not isinstance(v['bolts'],dict) or set(v['bolts'])!=bolt_ids:raise ValueError('Initial conditions omit fastener or bolt supply')
    for pid,row in v['bolts'].items():
        retained=pid in fasteners and not fasteners[pid].get('service_required',True)
        required_bolt={'turns','torque_N_m','thread_clean','thread_oiled','washer_oiled','stretch_mm','install_engagement_turns','history'}
        if not required_bolt<=set(row) or set(row)-required_bolt-{'free_length_mm'} or row['history']!=[]:
            raise ValueError('Invalid initial bolt condition or injected history')
        for field in ('turns','torque_N_m','stretch_mm'):number(row[field],nullable=retained)
        if 'free_length_mm' in row:
            number(row['free_length_mm'],nullable=True)
            if row['free_length_mm'] is not None and row['free_length_mm']<=0:
                raise ValueError('Bolt free length must be positive or explicitly unknown')
        number(row['install_engagement_turns'],nullable=retained)
        if not retained and row['install_engagement_turns']<=0:raise ValueError('Installed thread engagement must be explicit and positive')
        for field in ('thread_clean','thread_oiled','washer_oiled'):boolean(row[field],nullable=retained)
        if pid in fasteners and not retained and row['turns']!=fasteners[pid]['initial_engagement_turns']:
            raise ValueError('Initial thread engagement differs from geometry')
        if v['parts'][pid]['location']=='supply' and (row['turns']!=0 or row['torque_N_m']!=0):
            raise ValueError('Supply bolt cannot already be loaded or engaged')
    if not isinstance(v['surfaces'],dict) or set(v['surfaces'])!={'head_face','block_deck','cover_face'}:
        raise ValueError('Initial surface inventory missing')
    required={'residue_fraction','dry','debris_count','damaged','warpage_m','roughness_ra_um'}
    optional={'cam_holder_corner_sealant','tube_seals_oiled'}
    for row in v['surfaces'].values():
        if not required<=set(row) or set(row)-required-optional:raise ValueError('Initial surface fields incomplete')
        number(row['residue_fraction'],maximum=1);number(row['warpage_m'],nullable=True);number(row['roughness_ra_um'],nullable=True)
        if type(row['debris_count']) is not int or row['debris_count']<0:raise ValueError('Invalid initial debris count')
        for field in {'dry','damaged'}|(set(row)&optional):boolean(row[field])
    gasket=v['gasket'];old=next(pid for pid,p in parts.items() if p['role']=='gasket_old')
    required_gasket={'active_id','type','orientation'}
    if not required_gasket<=set(gasket) or set(gasket)-required_gasket-{'condition'} or gasket['active_id']!=old or gasket['type']!='old' or gasket['orientation'] not in ('up','down',None):
        raise ValueError('Initial installed gasket is inconsistent')
    if 'condition' in gasket and gasket['condition'] is not None and not (
            isinstance(gasket['condition'],str) and gasket['condition'].strip()):
        raise ValueError('Invalid initial gasket condition')
    timing=v['timing']
    if set(timing)!={'cam_phase_deg','crank_phase_deg','checks'} or timing['checks']!=[]:raise ValueError('Initial timing history cannot be injected')
    for field in ('cam_phase_deg','crank_phase_deg'):number(timing[field],minimum=-math.inf)
    return copy.deepcopy(v)
