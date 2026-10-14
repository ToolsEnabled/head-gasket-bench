"""Typed exact replay and scored transport values; no backend or model calls."""
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from hgj.codec import canonical
from hgj.game import Game, replay
from hgj.mcp import serve
from tools.repair_controls import example_config
from tools.repair_demo import requests


class ProcedureTransportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = example_config()

    def short_record(self):
        game = Game(self.config)
        game.call('look', {})
        return game.export()

    def test_complete_short_replay_exact(self):
        record = self.short_record()
        self.assertEqual(canonical(replay(record)), canonical(record))

    def test_boolean_cannot_alias_recorded_integer(self):
        record = self.short_record()
        self.assertEqual(record['actions'][0]['result']['human_time']['action_attempt_seconds'], 0)
        record['actions'][0]['result']['human_time']['action_attempt_seconds'] = False
        with self.assertRaises(ValueError):
            replay(record)

    def test_final_value_type_cannot_alias_integer(self):
        record = self.short_record()
        record['final_state']['human_time']['penalty_seconds'] = False
        with self.assertRaises(ValueError):
            replay(record)

    def test_extra_record_fields_not_silently_dropped(self):
        record = self.short_record()
        record['unrecorded_annotation'] = {'value':1}
        with self.assertRaises(ValueError):
            replay(record)

    def test_report_written_at_finish_with_unknown_provider_usage(self):
        with tempfile.TemporaryDirectory() as folder:
            incoming = ''.join(canonical(row).decode() for row in requests([{'name':'finish','input':{}}]))
            game = Game(self.config)
            sink = io.StringIO()
            result = serve(game, io.StringIO(incoming), sink, folder)
            self.assertTrue(result['finished'])
            report = json.loads((Path(folder)/'report.json').read_bytes())
            self.assertIsNone(report['tokens']['total'])
            self.assertEqual(report['tokens']['status'], 'not_recorded')
            self.assertGreaterEqual(report['real_time']['seconds'], 0)
            self.assertEqual(report['tool_calls']['attempted'], 1)
            self.assertEqual(report['human_time']['total_seconds'], game.score['human_time']['total_seconds'])
            self.assertIn('missing_torque_stage', report['mistakes']['by_type'])
            self.assertEqual(canonical(replay(game.export())), canonical(game.export()))

    def test_existing_report_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'report.json'
            path.write_text('preserved authored report')
            with self.assertRaises(FileExistsError):
                serve(Game(self.config), io.StringIO(''), io.StringIO(), folder)
            self.assertEqual(path.read_text(), 'preserved authored report')

    def test_live_look_does_not_disclose_end_assessment(self):
        game = Game(self.config)
        game.call('remove', {'part_id':game.role('head')})
        result = game.call('look', {})
        self.assertNotIn('penalty_seconds', result['human_time'])
        self.assertNotIn('mistakes', result)
        self.assertGreater(game.state['human_time']['penalty_seconds'], 0)


if __name__ == '__main__':
    unittest.main()
