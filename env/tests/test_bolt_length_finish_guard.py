"""Local omission gate with a pure fake dispatch seam, never backend admission."""
import unittest
from hgj.game import Game
from tests import test_bolt_length_transport as transport

class BoltLengthFinishGuardTests(unittest.TestCase):
    def gate(self,value):
        c=transport.BoltLengthTransportTests().config()
        if value!='omitted':
            packet=c['initial_conditions']
            for fastener in c['geometry']['fasteners']:
                if fastener['group']=='head':
                    body=fastener['id'];packet['values']['bolts'][body]['free_length_mm']=value
                    packet['field_sources']['/bolts/'+body+'/free_length_mm']={'sha256':'a'*64,
                        'status':'unknown' if value is None else 'estimated','note':'Synthetic local guard control only'}
        game=Game(c);seen=[]
        class Sink:
            def score(self,job):
                seen.append(job)
                return {'schema':'hgj/soak-result/v1','status':'UNQUALIFIED','qualification':'unqualified',
                    'pass':None,'time_to_failure_s':None,'cause':'Synthetic non-scoring sink'}
        # Exercise only the local finish predicate; this seam bypasses constructor
        # backend custody in a fake fixture and supplies no admitted backend.
        game.physical_conditions=True;game.joint_backend=object();game.soak_backend=Sink()
        game._bound_backend=lambda *args:None
        game.state['joint']={'acceptance_eligible':True,'qualification':'validated-physics'}
        return game,seen

    def test_omitted_required_lengths_block_before_soak(self):
        game,seen=self.gate('omitted');result=game.call('finish',{})
        self.assertTrue(result['ok'],result);self.assertEqual(len(seen),0)
        self.assertEqual(result['score']['status'],'INVALID_INPUT')
        self.assertIn('free length',result['score']['cause'])

    def test_explicit_unknown_blocks_and_present_lengths_do_not_supply_physical_credit(self):
        game,seen=self.gate(None);result=game.call('finish',{})
        self.assertTrue(result['ok'],result);self.assertEqual(len(seen),0)
        self.assertEqual(result['score']['status'],'INVALID_INPUT')
        game,seen=self.gate(61.2);result=game.call('finish',{})
        self.assertTrue(result['ok'],result);self.assertEqual(len(seen),1)
        self.assertEqual(result['score']['status'],'UNQUALIFIED');self.assertIsNone(result['score']['pass'])
