"""Validate agreed condition-effect transport; this does not admit a law.

Required paths and source pins are trusted, independently admitted domain inputs.
They cannot be selected by a subject or derived from the producer's response.
The candidate Game uses this helper through private operation admission;
current producer transitions remain held. This helper admits no physical law.
"""
import copy
import math
import re
from .codec import canonical, digest


def pointer(section, body, field):
    def escape(value):
        return value.replace('~', '~0').replace('/', '~1')
    return '/' + '/'.join(escape(value) for value in (section, body, field))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def finite(value):
    try:return type(value) in (int,float) and math.isfinite(value)
    except OverflowError:return False


def apply_effects(before, operation, packet, *, required_paths, allowed_paths, source_pins):
    """Return a copied condition record only after validating the whole packet."""
    require(isinstance(before, dict)
            and set(before) == {'parts', 'bolts', 'surfaces', 'gasket', 'timing'}
            and all(isinstance(row, dict) for row in before.values()),
            'Incomplete preceding conditions')
    canonical(before)
    require(isinstance(required_paths, (set, frozenset)) and bool(required_paths),
            'Unsupported action-condition domain')
    require(isinstance(allowed_paths, (set, frozenset)) and bool(allowed_paths)
            and required_paths <= allowed_paths
            and all(isinstance(path, str) for path in allowed_paths),
            'Invalid authorized operation domain')
    require(isinstance(source_pins, (set, frozenset)) and bool(source_pins)
            and all(isinstance(pin, str) and re.fullmatch('[a-f0-9]{64}', pin)
                    for pin in source_pins), 'Unbound condition-effect sources')
    before_pin = digest(before)
    require(isinstance(operation, dict)
            and operation.get('before_conditions_sha256') == before_pin
            and canonical(operation.get('before_conditions')) == canonical(before),
            'Operation preceding conditions mismatch')
    require(isinstance(packet, dict)
            and set(packet) == {'schema', 'operation_sha256', 'before_conditions_sha256', 'fields'}
            and packet.get('schema') == 'hgj/action-conditions/v1'
            and packet.get('operation_sha256') == digest(operation)
            and packet.get('before_conditions_sha256') == before_pin,
            'Condition effect operation/custody mismatch')
    fields = packet['fields']
    require(isinstance(fields, dict) and required_paths <= set(fields),
            'Missing required source-defined condition effect')
    allowed = {}
    for section, names in (
            ('parts', {'damaged'}),
            ('bolts', {'thread_clean', 'thread_oiled', 'washer_oiled', 'stretch_mm','free_length_mm'}),
            ('surfaces', {'residue_fraction', 'dry', 'debris_count', 'damaged',
                          'warpage_m', 'roughness_ra_um', 'tube_seals_oiled',
                          'cam_holder_corner_sealant'})):
        for body, row in before[section].items():
            require(isinstance(body, str) and isinstance(row, dict), 'Invalid preceding body conditions')
            for name in names & set(row):
                allowed[pointer(section, body, name)] = (section, body, name)
    for section, names in (('gasket', {'condition', 'orientation'}),
                           ('timing', {'cam_phase_deg', 'crank_phase_deg', 'checks'})):
        for name in names & set(before[section]):
            allowed['/' + section + '/' + name] = (section, name)
    require(set(fields) <= set(allowed), 'Effect changes an unknown or forbidden field')
    require(allowed_paths <= set(allowed) and set(fields) <= allowed_paths,
            'Effect exceeds authorized operation domain')
    for body,row in before['bolts'].items():
        if 'free_length_mm' in row and pointer('bolts',body,'stretch_mm') in fields:
            require(pointer('bolts',body,'free_length_mm') in fields,
                    'Stretch effect must also supply the source-defined free length')
    booleans = {'damaged', 'thread_clean', 'thread_oiled', 'washer_oiled', 'dry',
                'tube_seals_oiled', 'cam_holder_corner_sealant'}
    for path, item in fields.items():
        require(isinstance(item, dict)
                and set(item) == {'value', 'source_sha256', 'status', 'note'}
                and isinstance(item.get('source_sha256'), str)
                and item.get('source_sha256') in source_pins
                and item.get('status') in ('measured', 'cited', 'estimated', 'unknown')
                and isinstance(item.get('note'), str) and item['note'].strip(),
                'Invalid condition-effect source provenance')
        value, name = item['value'], allowed[path][-1]
        require((value is None) == (item['status'] == 'unknown'),
                'Unknown condition effect must be an explicit null')
        if value is None:
            continue
        if name in booleans:
            require(type(value) is bool, 'Invalid condition flag effect')
        elif name == 'debris_count':
            require(type(value) is int and value >= 0, 'Invalid debris condition effect')
        elif name == 'orientation':
            require(value in ('up', 'down'), 'Invalid gasket orientation effect')
        elif name == 'condition':
            require(isinstance(value, str) and value.strip(), 'Invalid gasket condition effect')
        elif name == 'checks':
            require(isinstance(value, list) and all(isinstance(row, dict) for row in value),
                    'Invalid source-defined timing evidence')
            canonical(value)
        else:
            require(finite(value),
                    'Invalid numeric condition effect')
            if name not in ('cam_phase_deg', 'crank_phase_deg'):
                require(value >= 0, 'Negative condition effect')
            if name == 'residue_fraction':
                require(value <= 1, 'Residue effect outside fraction domain')
            if name == 'free_length_mm':
                require(value > 0, 'Bolt free length must be positive or explicitly unknown')
    # Never modify the original record, including on a late-field refusal.
    updated = copy.deepcopy(before)
    for path, item in fields.items():
        keys = allowed[path]
        row = updated
        for key in keys[:-1]:
            row = row[key]
        row[keys[-1]] = copy.deepcopy(item['value'])
    canonical(updated)
    return updated
