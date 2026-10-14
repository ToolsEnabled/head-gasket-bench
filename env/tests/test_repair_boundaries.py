"""Value-based reference, backend, source-body and replay boundaries."""
import copy
import unittest
from hgj import repair_scoring as scoring
from hgj.game import Game
from hgj.codec import digest
from tools.repair_controls import example_config

REFERENCE_GATES = (
 'Reference must be a completed successful procedure',
 'Reference requires ten head positions and two complete tightening stages',
 'Unknown repair scoring mode', 'Repair reference commitment differs',
 'Repair reference differs from source inputs', 'Lookup categories must be a mapping',
 'Invalid lookup category',
)

def exercise_reference(gate, config, initial):
    config = copy.deepcopy(config)
    settings = config['repair_scoring']
    if gate in REFERENCE_GATES[:2]:
        rows=[]
        for stage in (30,73):
            for f in config['geometry']['fasteners']:
                if f['group']=='head':
                    rows.append({'seq':len(rows)+1,'name':'torque','input':{'part_id':f['id'],'mode':'tighten','value_N_m':stage},'result':{'ok':True}})
        rows.append({'seq':len(rows)+1,'name':'finish','input':{},'result':{'ok':True}})
        if gate==REFERENCE_GATES[0]: rows[-1]['name']='look'
        else: rows.pop(0)
        final=copy.deepcopy(initial);final['action_history']=[]
        return scoring.build_reference(config,initial,rows,final)
    if gate==REFERENCE_GATES[2]: settings['mode']='unregistered'
    elif gate==REFERENCE_GATES[3]: settings['reference_sha256']='0'*64
    elif gate==REFERENCE_GATES[4]: config['service']['qualification']='changed source'
    elif gate==REFERENCE_GATES[5]:
        class Mapping(dict): pass
        settings['lookup_categories']=Mapping()
    else: settings['lookup_categories']={'torque':[]}
    return scoring.validate_reference(config,initial)

class RepairBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config=example_config()
        cls.initial=Game(cls.config).state

    def test_reference_rejects_invalid_values(self):
        for gate in REFERENCE_GATES:
            with self.subTest(gate=gate),self.assertRaises(ValueError):
                exercise_reference(gate,self.config,self.initial)

    def test_backends_rejected_before_any_method_call(self):
        class Sentinel:
            def __getattr__(self,name):
                raise AssertionError('Backend method accessed: '+name)
        for argument in ('joint','soak'):
            with self.subTest(argument=argument),self.assertRaisesRegex(ValueError,'does not accept'):
                Game(self.config,**{argument:Sentinel()})

    def test_retained_dowels_have_unknown_condition_and_no_removal(self):
        game=Game(self.config)
        source=self.config['geometry']['retained_body_source']
        self.assertEqual(len(source['parts']),2)
        for part in source['parts']:
            pid=part['id']
            self.assertEqual(game.part_defs[pid],part)
            self.assertIsNone(game.state['parts'][pid]['damaged'])
            self.assertEqual(game.state['parts'][pid]['location'],'assembly')
            self.assertFalse(game.call('remove',{'part_id':pid})['ok'])
            self.assertEqual(game.state['parts'][pid]['location'],'assembly')
        score=scoring.score_repair(self.config,self.initial,game.records,game.state)
        entries={x['item']:x for x in score['checklist_accuracy']['items']}
        for part in source['parts']:
            key='part/'+part['id']+'/location'
            self.assertTrue(entries[key]['correct'])
        self.assertIn('condition, fit and removal not assessed',score['coverage']['dowels'])

if __name__=='__main__':unittest.main()
