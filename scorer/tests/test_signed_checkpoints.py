"""Signed checkpoint interpretations, expressed as authored action values."""
from copy import deepcopy
import unittest
from test_successor_components import benchmark,event,checked
from tools.test_repair_checkpoints import evaluate
from test_checkpoint_chronology import rechain


class SignedCheckpoints(unittest.TestCase):
    def test_later_torque_correction_does_not_change_initial_loosening(self):
        r=benchmark();r['actions'].insert(-1,event('torque',{'part_id':'hb01','mode':'loosen','angle_deg':-120}))
        value=evaluate(rechain(r));rows={x['id']:x for x in value['primary_score']['checkpoints']}
        self.assertTrue(rows['CP04']['passed'])
        self.assertFalse(rows['CP09']['passed']);self.assertFalse(rows['CP10']['passed'])

    def test_initial_wrong_loosening_cannot_be_recovered_by_later_actions(self):
        r=benchmark();first=next(a for a in r['actions'] if a['name']=='torque' and a['input'].get('mode')=='loosen' and a['input'].get('part_id')=='hb10')
        first['input']['angle_deg']=-60
        r['actions'].insert(-1,event('torque',{'part_id':'hb10','mode':'loosen','angle_deg':-120}))
        self.assertFalse(checked(r,'CP04')['passed'])

    def test_cleaning_only_after_current_gasket_placement_still_fails(self):
        r=benchmark();clean=next(a for a in r['actions'] if a['name']=='clean' and a['input'].get('target')=='head_face')
        r['actions'].remove(clean);r['actions'].insert(-1,clean)
        self.assertFalse(checked(r,'CP05')['passed'])

    def test_new_complete_preparation_for_later_placement_can_recover(self):
        r=benchmark();clean=next(a for a in r['actions'] if a['name']=='clean' and a['input'].get('target')=='head_face')
        r['actions'].remove(clean);r['actions'].insert(-1,clean)
        gasket=r['final_state']['gasket']['active_id']
        # Values isolate CP05; these added actions are not claimed executable
        # without the separate bolt-disassembly requirements checked by CP02.
        rows=[event('remove',{'part_id':'head'}),event('remove',{'part_id':gasket}),
              deepcopy(clean),event('clean',{'target':'block_deck','method':'scraper','protect_openings':True}),
              event('install',{'part_id':gasket,'orientation':'up'}),event('install',{'part_id':'head'})]
        r['actions'][-1:-1]=rows
        self.assertTrue(checked(r,'CP05')['passed'])

    def test_replacing_measured_serviceable_bolt_is_wrong_decision(self):
        r=benchmark();row=next(a for a in r['actions'] if a['name']=='measure' and a['input'].get('target')=='hb03')
        row['result']['observation']['value']=0.01
        self.assertFalse(checked(r,'CP07')['passed'])

    def test_stock_role_cannot_substitute_for_specified_dimensions(self):
        for field,bad in [('bore_mm',78),('bore_mm',75.5),('compressed_thickness_mm',1.2),('construction','unverified')]:
            r=benchmark();part=next(p for p in r['config']['geometry']['parts'] if p['role']=='gasket_new');part['catalog'][field]=bad
            self.assertFalse(checked(r,'CP08')['passed'])

    def test_cover_gasket_reuse_fails_even_if_old_reference_requests_it(self):
        r=benchmark();f=r['final_state'];ref=r['config']['repair_scoring']['reference']['final']
        for state in (f,ref):
            state['parts']['cover_gasket_old']['location']='assembly'
            state['parts']['cover_gasket_new']['location']='supply'
        self.assertFalse(checked(r,'CP12')['passed'])

    def test_all_parts_back_without_fasteners_fails_reassembly(self):
        r=benchmark()
        for part in ('hb01','cb01'):
            r['final_state']['parts'][part]['location']='tray'
        self.assertFalse(checked(r,'CP12')['passed'])

if __name__=='__main__':unittest.main()
