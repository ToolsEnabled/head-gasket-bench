"""Bounded stdlib transport probes; no deployment or physical qualification."""
import io
import json
import tempfile
import unittest
from pathlib import Path

from hgj.codec import canonical
from hgj.fixtures import fixture_config
from hgj.game import Game, replay
from hgj.mcp import serve


def request(method, identifier=1, **params):
    return json.dumps({'jsonrpc': '2.0', 'id': identifier,
                       'method': method, 'params': params}) + '\n'


INITIALIZE = request('initialize', 0, protocolVersion='2025-11-25')
READY = json.dumps({'jsonrpc': '2.0', 'method': 'notifications/initialized'}) + '\n'
LOOK = request('tools/call', 2, name='look', arguments={})
FINISH = request('tools/call', 3, name='finish', arguments={})


class BoundedStream(io.StringIO):
    """A stream that refuses any unbounded line allocation."""
    def readline(self, size=-1):
        if size < 0 or size > 65537:
            raise AssertionError('Unbounded transport read')
        return super().readline(size)

    def __next__(self):
        value = self.readline()
        if not value:
            raise StopIteration
        return value


class MCPTransportTests(unittest.TestCase):
    def run_transport(self, text, stream_type=io.StringIO):
        game = Game(fixture_config())
        sink = io.StringIO()
        with tempfile.TemporaryDirectory() as directory:
            summary = serve(game, stream_type(text), sink, directory)
            record = json.loads((Path(directory) / 'run.json').read_bytes())
            journal = (Path(directory) / 'actions.jsonl').read_bytes()
        self.assertEqual(journal, b''.join(canonical(row) for row in record['actions']))
        self.assertEqual(canonical(replay(record)), canonical(record))
        return summary, record, [json.loads(line) for line in sink.getvalue().splitlines()]

    def test_ready_notification_requires_successful_initialize(self):
        summary, record, replies = self.run_transport(READY + LOOK + INITIALIZE + READY + FINISH)
        self.assertEqual(summary, {'actions': 1, 'finished': True})
        self.assertIn('error', replies[0])
        self.assertEqual([row['name'] for row in record['actions']], ['finish'])

    def test_invalid_json_values_never_dispatch_and_session_recovers(self):
        invalid = [
            request('tools/call', 8, name='\ud800', arguments={}),
            request('tools/call', '\ud800', name='look', arguments={}),
            request('tools/call', 8, name='inspect', arguments={'target': '\udfff'}),
            request('tools/call', 8, name='torque', arguments={'value_N_m': float('nan')}),
            request('tools/call', 8, name='torque', arguments={'value_N_m': float('inf')}),
            '[' * 2000 + '0' + ']' * 2000 + '\n',
        ]
        for malformed in invalid:
            with self.subTest(malformed=repr(malformed[:80])):
                summary, record, replies = self.run_transport(INITIALIZE + READY + malformed + LOOK + FINISH)
                self.assertEqual(summary, {'actions': 2, 'finished': True})
                self.assertEqual([row['name'] for row in record['actions']], ['look', 'finish'])
                self.assertIn('error', replies[1])
                self.assertIsNone(replies[1]['id'])

    def test_oversize_line_is_drained_in_bounded_reads_before_next_request(self):
        summary, record, replies = self.run_transport(
            'x' * 200000 + '\n' + INITIALIZE + READY + LOOK + FINISH, BoundedStream)
        self.assertEqual(summary, {'actions': 2, 'finished': True})
        self.assertEqual(len(replies), 4)
        self.assertIn('error', replies[0])
        self.assertEqual(record['budget']['attempted_calls'], 2)

    def test_transport_limit_counts_utf8_bytes(self):
        oversized = json.dumps({'jsonrpc': '2.0', 'id': 9, 'method': 'ping',
                                'params': {'text': '\u03bb' * 40000}}, ensure_ascii=False) + '\n'
        summary, _, replies = self.run_transport(oversized + INITIALIZE + READY + FINISH)
        self.assertIn('error', replies[0])
        self.assertEqual(summary, {'actions': 1, 'finished': True})

    def test_invalid_request_id_is_not_reflected_as_invalid_response_id(self):
        for identifier in ([], {}, True, None, 1.5):
            with self.subTest(identifier=identifier):
                _, _, replies = self.run_transport(request('ping', identifier) + INITIALIZE + READY + FINISH)
                self.assertIn('error', replies[0])
                self.assertIsNone(replies[0]['id'])

    def test_valid_tool_refusals_still_count_and_replay(self):
        refused = request('tools/call', 4, name='look', arguments={'extra': True})
        summary, record, replies = self.run_transport(INITIALIZE + READY + refused + LOOK + FINISH)
        self.assertEqual(summary, {'actions': 3, 'finished': True})
        self.assertTrue(replies[1]['result']['isError'])
        self.assertEqual(record['budget']['attempted_calls'], 3)
        self.assertEqual(record['final_state']['simulated_labor_s'], 2)
