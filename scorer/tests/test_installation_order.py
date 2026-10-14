"""Installation body lists follow the state map, not prior removal ordering."""
from copy import deepcopy
import unittest
from job_accuracy import removal
from test_source_removal import sample,repin


def two_children(initial=False):
    c,a,f=sample();p=deepcopy(c['geometry']['parts'][1]);p.update(id='another',l1_body_id='another_source')
    c['geometry']['parts'].insert(1,p)
    policy=c['benchmark_removal']['policy'];r=deepcopy(policy['parts'][1]);r['id']='another_source';policy['parts'].append(r)
    policy['parts'][0]['routes'][0]['carried_body_ids'].append('another_source')
    c['benchmark_removal']['source_to_body']['another_source']='another';repin(c)
    a[2]['result']['carried_body_ids']=['member','another']
    a[3]['result']['carried_body_ids']=['another','member']
    f['benchmark_removal']['movements'][0]['carried_body_ids']=['member','another']
    f['benchmark_removal']['movements'][1]['carried_body_ids']=['another','member']
    f['parts']['another']={'location':'assembly'}
    if initial:
        c['initial_conditions']={'values':{'parts':{'member':{},'head':{},'another':{},'base':{}},'bolts':{}}}
        a[3]['result']['carried_body_ids']=['member','another']
        f['benchmark_removal']['movements'][1]['carried_body_ids']=['member','another']
    return c,a,f


class InstallationOrder(unittest.TestCase):
    def test_geometry_state_order_differs_from_removal_route(self):
        r=removal.replay(*two_children());self.assertTrue(r['reassembly_complete']);self.assertTrue(r['trace_consistent'])
        self.assertEqual(r['expected_movements'][1]['carried_body_ids'],['another','member'])

    def test_explicit_initial_state_order_overrides_geometry(self):
        r=removal.replay(*two_children(True));self.assertTrue(r['reassembly_complete'])
        self.assertEqual(r['expected_movements'][1]['carried_body_ids'],['member','another'])

    def test_membership_and_exact_receipt_are_still_checked(self):
        for bad in ([],['another'],['another','another'],['member','another']):
            c,a,f=two_children();a[3]['result']['carried_body_ids']=bad
            with self.subTest(bad=bad):self.assertFalse(removal.replay(c,a,f)['reassembly_complete'])
        c,a,f=two_children();f['benchmark_removal']['movements'][1]['carried_body_ids']=[]
        self.assertFalse(removal.replay(c,a,f)['trace_consistent'])

    def test_only_current_tray_children_of_this_carrier_move(self):
        p={'a':{},'b':{},'c':{},'d':{}};carried={'d':'other','c':'carrier','b':'carrier','a':'carrier'}
        locations={'a':'tray','b':'waste','c':'assembly','d':'tray'}
        self.assertEqual(removal.installation_children({},p,carried,locations,'carrier'),['a'])


if __name__=='__main__':unittest.main()
