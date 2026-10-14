"""Private operation/field authorization bound by independent admission.

This is a finite exact-command domain. It supplies no numerical law, physical
admission, or permission for a command/state outside the producer's validation.
"""
import copy
import re
from .action_conditions import apply_effects, require
from .codec import canonical,digest
from .api import validate


MECHANICAL = frozenset(('remove','install','clean','replace','torque','check_timing'))


def sha(value):
    return isinstance(value,str) and re.fullmatch('[a-f0-9]{64}',value) is not None


class ActionDomains:
    def __init__(self,config):
        self.config=copy.deepcopy(config)
        self.packet=copy.deepcopy(config.get('action_domains'))
        self.rules=[]
        if self.packet is None:
            return
        p=self.packet;a=config.get('admission',{});identity=config.get('identity',{})
        require(isinstance(a,dict) and isinstance(identity,dict),'Invalid domain admission or identity')
        require(isinstance(p,dict) and set(p)=={'schema','qualification','geometry_sha256',
            'initial_conditions_sha256','variant_sha256','joint_descriptor_sha256','rules','default_reason'}
            and p.get('schema')=='hgj/action-domains/v1' and p.get('qualification')=='source-defined',
            'Invalid source-defined action domain')
        require(a.get('status')=='validated-physics','Action domain lacks independent admission')
        self.body_pin=digest(p)
        self.file_pin=identity.get('action_domains_sha256')
        require(sha(self.file_pin) and a.get('action_domains_sha256')==self.file_pin
                and a.get('action_domains_body_sha256')==self.body_pin,
                'Action domain file/body admission mismatch')
        variant=next((v for v in config['variants'] if v['id']==config['variant_id']),None)
        require(variant is not None and p['variant_sha256']==digest(variant)
            and p['geometry_sha256']==identity.get('geometry_sha256',digest(config['geometry']))
            and p['initial_conditions_sha256']==identity.get('initial_conditions_sha256',digest(config.get('initial_conditions')))
            and sha(p['joint_descriptor_sha256'])
            and p['joint_descriptor_sha256']==a.get('joint_descriptor_sha256'),
            'Action domain belongs to another geometry, initial state, variant or joint')
        require(isinstance(p['default_reason'],str) and p['default_reason'].strip()
                and isinstance(p['rules'],list),'Invalid action-domain default/rules')
        seen_ids=set();seen_commands=set()
        for rule in p['rules']:
            require(isinstance(rule,dict) and set(rule)=={'id','tool','arguments','supported',
                    'required_paths','fields','validation_sha256','reason'}
                    and isinstance(rule['id'],str) and rule['id'].strip()
                    and rule['tool'] in MECHANICAL and isinstance(rule['arguments'],dict)
                    and type(rule['supported']) is bool and isinstance(rule['reason'],str)
                    and rule['reason'].strip(),'Invalid operation-domain rule')
            validate(rule['tool'],rule['arguments'])
            key=(rule['tool'],canonical(rule['arguments']))
            require(rule['id'] not in seen_ids and key not in seen_commands,
                    'Duplicate or ambiguous operation-domain rule')
            seen_ids.add(rule['id']);seen_commands.add(key)
            require(isinstance(rule['required_paths'],list)
                    and all(isinstance(path,str) for path in rule['required_paths'])
                    and len(set(rule['required_paths']))==len(rule['required_paths'])
                    and isinstance(rule['fields'],dict),'Invalid operation-domain paths')
            if not rule['supported']:
                require(rule['required_paths']==[] and rule['fields']=={}
                        and rule['validation_sha256'] is None,'Unsupported rule cannot authorize effects')
            else:
                require(bool(rule['required_paths']) and set(rule['required_paths'])<=set(rule['fields'])
                        and sha(rule['validation_sha256'])
                        and a.get('action_rule_validation_sha256',{}).get(rule['id'])==rule['validation_sha256'],
                        'Supported operation domain lacks independent rule validation')
                for path,source in rule['fields'].items():
                    require(isinstance(path,str) and isinstance(source,dict)
                            and set(source)=={'source_pins','statuses'}
                            and isinstance(source['source_pins'],list) and bool(source['source_pins'])
                            and all(sha(pin) for pin in source['source_pins'])
                            and len(set(source['source_pins']))==len(source['source_pins'])
                            and isinstance(source['statuses'],list) and bool(source['statuses'])
                            and all(status in ('measured','cited','estimated','unknown') for status in source['statuses'])
                            and len(set(source['statuses']))==len(source['statuses']),
                            'Invalid field-specific operation provenance')
            self.rules.append(copy.deepcopy(rule))

    def resolve(self,name,arguments):
        key=canonical(arguments)
        for rule in self.rules:
            if rule['tool']==name and canonical(rule['arguments'])==key:
                return copy.deepcopy(rule) if rule['supported'] else None
        return None

    def apply(self,name,arguments,before,operation,packet,backend_descriptor):
        rule=self.resolve(name,arguments)
        require(rule is not None,'Source-defined physical action effects are not admitted')
        require(digest(backend_descriptor)==self.packet['joint_descriptor_sha256'],
                'Effect facade descriptor differs from admitted domain')
        envelope={'kind','bolts','surfaces','gasket','ordinal','attempt_sequence','before_conditions','before_conditions_sha256'}|set(arguments)
        optional=set()
        if name=='torque':envelope|={'group','sequence_index'}
        if name in ('remove','install'):optional={'carried_body_ids'}
        require(isinstance(operation,dict) and envelope<=set(operation)
                and set(operation)<=envelope|optional
                and all(isinstance(operation[key],dict) for key in ('bolts','surfaces','gasket'))
                and type(operation['ordinal']) is int and operation['ordinal']>=0
                and type(operation['attempt_sequence']) is int and operation['attempt_sequence']>=1,
                'Invalid admitted operation envelope')
        if 'carried_body_ids' in operation:
            bodies=operation['carried_body_ids']
            require(isinstance(bodies,list) and bool(bodies) and all(isinstance(body,str) and body in before['parts'] for body in bodies)
                    and len(set(bodies))==len(bodies),'Invalid carried-body operation envelope')
        if name=='torque':
            require(operation['group'] in ('head','cover') and type(operation['sequence_index']) is int
                    and operation['sequence_index']>=1,'Invalid torque operation envelope')
        require(operation.get('kind')==name
                and all(key in operation and canonical(operation[key])==canonical(value)
                        for key,value in arguments.items()),'Effect operation differs from admitted command')
        fields=packet.get('fields') if isinstance(packet,dict) else None
        require(isinstance(fields,dict) and set(fields)<=set(rule['fields']),
                'Effect exceeds admitted operation field maximum')
        for path,item in fields.items():
            source=rule['fields'][path]
            require(isinstance(item,dict) and item.get('source_sha256') in source['source_pins']
                    and item.get('status') in source['statuses'],'Effect field source/status is outside admitted domain')
        all_pins={pin for source in rule['fields'].values() for pin in source['source_pins']}
        updated=apply_effects(before,operation,packet,required_paths=set(rule['required_paths']),
                             allowed_paths=set(rule['fields']),source_pins=all_pins)
        evidence={'schema':'hgj/authorized-condition-effects/v1','domain_file_sha256':self.file_pin,
            'domain_body_sha256':self.body_pin,'rule_id':rule['id'],'rule_sha256':digest(rule),
            'joint_descriptor_sha256':self.packet['joint_descriptor_sha256'],
            'operation_sha256':digest(operation),'operation':copy.deepcopy(operation),
            'condition_effects':copy.deepcopy(packet)}
        return updated,evidence
