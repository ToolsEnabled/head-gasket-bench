"""Pure private-domain transport fixtures, not admitted physical laws."""
import copy
import hashlib
import json
import unittest
from hgj.codec import canonical,digest
from tests.test_action_conditions import ActionConditionsTests


class ActionDomainTests(unittest.TestCase):
    def repin(self,config):
        domain=config['action_domains']
        raw=json.dumps(domain,indent=2,ensure_ascii=False).encode()
        config['identity']['action_domains_sha256']=hashlib.sha256(raw).hexdigest()
        config['admission']['action_domains_sha256']=config['identity']['action_domains_sha256']
        config['admission']['action_domains_body_sha256']=digest(domain)

    def fixture(self):
        before, operation, packet, path = ActionConditionsTests().fixture()
        args = {'target': 'cover_face', 'method': 'solvent', 'protect_openings': True}
        # Domain matching is about the complete requested arguments, independently
        # of the tiny Unicode pointer transport fixture retained below.
        rule = {'id': 'synthetic-clean', 'tool': 'clean', 'arguments': args,
                'supported': True, 'required_paths': [path],
                'fields': {path: {'source_pins': ['a'*64], 'statuses': ['estimated']}},
                'validation_sha256': 'e'*64, 'reason': 'Synthetic transport test only'}
        variant = {'id': 'transport-only'}
        descriptor = {'kind': 'joint', 'sha256': 'f'*64}
        config = {'geometry': {'qualification': 'cad-derived'}, 'initial_conditions': {'transport': True},
                  'variants': [variant], 'variant_id': variant['id'], 'identity': {}}
        domain = {'schema': 'hgj/action-domains/v1', 'qualification': 'source-defined',
                  'geometry_sha256': digest(config['geometry']),
                  'initial_conditions_sha256': digest(config['initial_conditions']),
                  'variant_sha256': digest(variant), 'joint_descriptor_sha256': digest(descriptor),
                  'rules': [rule], 'default_reason': 'Unsupported command; no law inferred'}
        config['action_domains'] = domain
        config['admission'] = {'status': 'validated-physics',
            'action_domains_sha256': digest(domain), 'action_domains_body_sha256': digest(domain),
            'joint_descriptor_sha256': digest(descriptor),
            'action_rule_validation_sha256': {rule['id']: rule['validation_sha256']}}
        self.repin(config)
        operation = {'kind': 'clean', **args, 'before_conditions': before,
                     'before_conditions_sha256': digest(before),'bolts':copy.deepcopy(before['bolts']),
                     'surfaces':copy.deepcopy(before['surfaces']),'gasket':copy.deepcopy(before['gasket']),
                     'ordinal':0,'attempt_sequence':1}
        packet.update(operation_sha256=digest(operation),before_conditions_sha256=digest(before))
        return config,descriptor,before,operation,packet,path,args

    def test_exact_command_and_field_source_status_binding(self):
        from hgj.action_domains import ActionDomains
        c,d,b,o,p,path,args = self.fixture()
        domains = ActionDomains(c)
        after, evidence = domains.apply('clean', args, b, o, p, d)
        self.assertTrue(after['bolts']['bolt/μ']['thread_clean'])
        self.assertEqual(evidence['operation_sha256'], digest(o))
        self.assertEqual(evidence['domain_body_sha256'], digest(c['action_domains']))
        for kind in ('arguments','source','status','operation'):
            wrong_args = copy.deepcopy(args); wrong_packet = copy.deepcopy(p); wrong_op = copy.deepcopy(o)
            if kind == 'arguments': wrong_args['protect_openings'] = False
            elif kind == 'source': wrong_packet['fields'][path]['source_sha256'] = 'b'*64
            elif kind == 'status': wrong_packet['fields'][path]['status'] = 'measured'
            else: wrong_op['method'] = 'abrasive_disc';wrong_packet['operation_sha256']=digest(wrong_op)
            with self.subTest(kind=kind),self.assertRaises(ValueError):
                domains.apply('clean',wrong_args,b,wrong_op,wrong_packet,d)
        self.assertFalse(b['bolts']['bolt/μ']['thread_clean'])

    def test_missing_or_unsupported_domain_does_not_release_commands(self):
        from hgj.action_domains import ActionDomains
        c,d,b,o,p,path,args = self.fixture();del c['action_domains']
        self.assertIsNone(ActionDomains(c).resolve('clean',args))
        c,d,b,o,p,path,args = self.fixture();rule=c['action_domains']['rules'][0]
        rule.update(supported=False,required_paths=[],fields={},validation_sha256=None)
        self.repin(c)
        self.assertIsNone(ActionDomains(c).resolve('clean',args))

    def test_domain_tampering_and_admission_namespaces_refuse(self):
        from hgj.action_domains import ActionDomains
        for kind in ('body','geometry','initial','variant','validation','duplicate','maximum'):
            c,d,b,o,p,path,args = self.fixture();domain=c['action_domains']
            if kind=='body':domain['rules'][0]['reason']='Changed after independent body pin'
            elif kind in ('geometry','initial','variant'):
                domain[{'geometry':'geometry_sha256','initial':'initial_conditions_sha256','variant':'variant_sha256'}[kind]]='b'*64
            elif kind=='validation':c['admission']['action_rule_validation_sha256']['synthetic-clean']='b'*64
            elif kind=='duplicate':domain['rules'].append(copy.deepcopy(domain['rules'][0]))
            else:domain['rules'][0]['required_paths'].append('/unbound')
            if kind!='body':self.repin(c)
            with self.subTest(kind=kind),self.assertRaises(ValueError):ActionDomains(c)

    def test_receipt_is_not_a_global_source_or_operation_permission(self):
        from hgj.action_domains import ActionDomains
        c,d,b,o,p,path,args = self.fixture();domains=ActionDomains(c)
        wrong=dict(d,sha256='b'*64)
        with self.assertRaises(ValueError):domains.apply('clean',args,b,o,p,wrong)
        self.assertEqual(canonical(b),canonical(o['before_conditions']))

    def test_explicit_raw_pin_is_required(self):
        from hgj.action_domains import ActionDomains
        c,d,b,o,p,path,args=self.fixture()
        raw=c['identity'].pop('action_domains_sha256')
        c['admission']['action_domains_sha256']=digest(c['action_domains'])
        with self.assertRaisesRegex(ValueError,'file/body'):ActionDomains(c)
    def test_exact_operation_envelope_is_required(self):
        from hgj.action_domains import ActionDomains
        c,d,b,o,p,path,args=self.fixture();domains=ActionDomains(c)
        o['unadmitted_option']=True;p['operation_sha256']=digest(o)
        with self.assertRaisesRegex(ValueError,'envelope'):domains.apply('clean',args,b,o,p,d)
