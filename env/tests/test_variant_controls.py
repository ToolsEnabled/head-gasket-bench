"""Small trajectory/report regressions; no engine or provider is invoked."""
import copy
import io
import json
from functools import lru_cache
from pathlib import Path
import tempfile
import unittest

from hgj.codec import canonical, digest
from hgj.game import Game
from hgj.mcp import serve
from hgj.repair_report import report_for_run
from hgj.repair_scoring import score_repair
from tools.repair_controls import example_config


@lru_cache(maxsize=1)
def trusted_configuration():
    return example_config()


def timing_values(early=False):
    """Authored scorer values isolate ordering; these are not run receipts."""
    config = copy.deepcopy(trusted_configuration())
    initial = copy.deepcopy(Game(config).state)
    reference = config['repair_scoring']['reference']
    final = copy.deepcopy(initial)
    final.update(copy.deepcopy(reference['final']))
    rows = [dict(seq=row['seq'], name=row['name'], input=copy.deepcopy(row['input']),
                 result={'ok':True}) for row in reference['actions']]
    ids = sorted({value for values in config['repair_scoring']['lookup_categories'].values()
                  for value in values})
    for row in rows:
        if row['name'] == 'search_service_info':
            row['result']['entries'] = [{'id':value} for value in ids]
    if early:
        check = rows.pop(next(i for i,row in enumerate(rows) if row['name']=='check_timing'))
        belt = next(part['id'] for part in config['geometry']['parts'] if part['role']=='timing_belt')
        index = next(i for i,row in enumerate(rows) if row['name']=='remove' and row['input']['part_id']==belt)
        rows.insert(index,check)
    for sequence,row in enumerate(rows,1):
        row['seq'] = sequence
    final['action_history'] = [dict(seq=row['seq'],name=row['name'],input=copy.deepcopy(row['input'])) for row in rows]
    return config,initial,rows,final


class TimingTrajectoryTests(unittest.TestCase):
    def test_timing_check_must_follow_latest_belt_change(self):
        for early in (False,True):
            with self.subTest(check_before_removal=early):
                report = score_repair(*timing_values(early))
                item = next(row for row in report['checklist_accuracy']['items']
                            if row['item']=='timing/check_completed')
                self.assertIs(item['correct'],not early)
                self.assertIs(item['actual'],not early)


class StrictReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        game = Game(copy.deepcopy(trusted_configuration()))
        game.call('finish',{})
        cls.completed = game.export()

    def record(self):
        return copy.deepcopy(self.completed)

    def test_valid_completed_report_has_exact_census_and_unknown_tokens(self):
        record = self.record()
        report = report_for_run(record,0.5)
        self.assertIs(report['finished'],True)
        self.assertEqual(report['status'],'finished')
        self.assertEqual(report['terminal_reason'],'finished')
        self.assertEqual(report['tool_calls'],{'attempted':1,'successful':1,'refused':0})
        self.assertIsNone(report['tokens']['total'])

    def test_action_result_requires_boolean_not_numeric_alias(self):
        for value in (0,1,0.0,1.0,None):
            with self.subTest(value=value):
                record = self.record()
                record['actions'][0]['result']['ok'] = value
                with self.assertRaises(ValueError):
                    report_for_run(record,0)

    def test_successful_finish_witness_is_required(self):
        record = self.record()
        record['actions'][0]['name'] = 'look'
        with self.assertRaises(ValueError):
            report_for_run(record,0)

    def test_tool_call_census_requires_integer_and_actual_count(self):
        for value in (True,1.0,0,2):
            with self.subTest(census=value):
                record = self.record()
                record['score']['tool_calls'] = value
                record['score_sha256'] = digest(record['score'])
                with self.assertRaises(ValueError):
                    report_for_run(record,0)

    def test_finished_flag_requires_boolean(self):
        for value in (1,0,None):
            with self.subTest(finished=value):
                record = self.record()
                record['finished'] = value
                with self.assertRaises(ValueError):
                    report_for_run(record,0)


class IncompleteRunTests(unittest.TestCase):
    observations = {}

    def execute(self,label,config,requests,game_type=Game,interrupt=False):
        game = game_type(config)
        initial = game.export()
        self.assertIsInstance(initial['score'],dict)
        self.assertEqual(initial['score']['status'],'in_progress')
        self.assertEqual(initial['score']['tool_calls'],0)
        with tempfile.TemporaryDirectory(prefix='partial-') as temporary:
            incoming = io.StringIO(''.join(canonical(row).decode() for row in requests))
            sink = io.StringIO()
            if interrupt:
                with self.assertRaises(KeyboardInterrupt):
                    serve(game,incoming,sink,temporary)
            else:
                serve(game,incoming,sink,temporary)
            out = Path(temporary)
            run = json.loads((out/'run.json').read_bytes())
            report = json.loads((out/'report.json').read_bytes())
            journal = (out/'actions.jsonl').read_bytes()
            self.assertEqual(journal,b''.join(canonical(row) for row in run['actions']))
            self.assertEqual(report['run_sha256'],digest(run))
            self.assertEqual(run['score_sha256'],digest(run['score']))
            self.assertEqual(report['tool_calls']['attempted'],len(run['actions']))
            self.assertEqual(run['score']['tool_calls'],len(run['actions']))
            self.assertIs(run['finished'],False)
            self.assertEqual(run['score']['status'],'in_progress')
            self.assertEqual(report['status'],'incomplete')
            self.assertIsNone(report['tokens']['total'])
            self.observations[label] = {'run':run,'report':report}
            return game,run,report

    @staticmethod
    def requests(calls):
        rows = [dict(jsonrpc='2.0',id=0,method='initialize',params={'protocolVersion':'2025-11-25'}),
                dict(jsonrpc='2.0',method='notifications/initialized')]
        rows += [dict(jsonrpc='2.0',id=i+1,method='tools/call',params={'name':name,'arguments':{}})
                 for i,name in enumerate(calls)]
        return rows

    def test_never_started_job_still_reports_incomplete_zero_attempts(self):
        _,run,report = self.execute('never_started',copy.deepcopy(trusted_configuration()),[])
        self.assertEqual(run['actions'],[])
        self.assertEqual(report['terminal_reason'],'input_ended_without_finish')
        self.assertEqual(report['human_time']['total_seconds'],0)

    def test_eof_after_action_reports_partial_score(self):
        _,run,report = self.execute('input_ended',copy.deepcopy(trusted_configuration()),self.requests(['look']))
        self.assertEqual(len(run['actions']),1)
        self.assertEqual(report['terminal_reason'],'input_ended_without_finish')
        self.assertEqual(report['human_time']['productive_seconds'],10)

    def test_budget_exhaustion_has_named_incomplete_reason(self):
        config = copy.deepcopy(trusted_configuration())
        config['factors']['turn_budget'] = 1
        _,run,report = self.execute('budget_exhausted',config,self.requests(['look']))
        self.assertEqual(len(run['actions']),1)
        self.assertEqual(report['terminal_reason'],'budget_exhausted')

    def test_tool_limit_has_distinct_incomplete_reason(self):
        config = copy.deepcopy(trusted_configuration())
        config['factors']['turn_budget'] = 10
        config['factors']['tool_call_limit'] = 1
        _,run,report = self.execute('tool_limit',config,self.requests(['look']))
        self.assertEqual(len(run['actions']),1)
        self.assertEqual(report['terminal_reason'],'tool_call_limit')

    def test_interrupt_during_action_reports_only_last_committed_snapshot(self):
        class InterruptAfterMutation(Game):
            def call(self,name,args):
                response = super().call(name,args)
                if len(self.records)==2:
                    raise KeyboardInterrupt('Authored interruption after mutable action, before transport commit')
                return response
        game,run,report = self.execute('interrupted',copy.deepcopy(trusted_configuration()),
                                      self.requests(['look','look']),InterruptAfterMutation,True)
        self.assertEqual(len(game.records),2)
        self.assertEqual(len(run['actions']),1)
        self.assertEqual(report['terminal_reason'],'interrupted')
        self.assertEqual(report['human_time']['productive_seconds'],10)


if __name__ == '__main__':
    unittest.main()
