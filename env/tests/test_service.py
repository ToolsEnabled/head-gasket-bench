import json
import unittest
from pathlib import Path
from hgj.fixtures import fixture_config
from hgj.game import Game


class ServiceTests(unittest.TestCase):
    def test_technician_queries_find_head_sequence_torque_and_condition(self):
        c=fixture_config(); c['service']=json.loads(Path('data/service.json').read_text()); g=Game(c)
        for query,expected in [('head bolts',['E03','E04']),('tightening sequence',['E03']),
                               ('bolt reuse',['E05']),('deck flatness',['E06'])]:
            result=g.call('search_service_info',{'query':query})
            self.assertTrue(result['ok'])
            found={e['id'] for e in result['entries']}
            self.assertTrue(set(expected)<=found,(query,found))

    def test_all_labor_citations_resolve_and_estimates_are_labeled(self):
        labor=json.loads(Path('data/labor-v2.json').read_text())
        for entry in labor['actions'].values():
            self.assertTrue(set(entry['source_ids'])<=labor['sources'].keys())
            self.assertIn('estimate',entry['qualification'].lower())
