"""Tests for tools/claude-code-proxy.py: tool metadata added, everything else passed through unchanged."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PROXY = REPO / 'tools' / 'claude-code-proxy.py'
SERVER = REPO / 'env' / 'bin' / 'headgasket-mcp'
SESSION = [
    {"jsonrpc": "2.0", "id": 0, "method": "initialize", "params": {"protocolVersion": "2025-11-25"}},
    {"jsonrpc": "2.0", "method": "notifications/initialized"},
    {"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
    {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "look", "arguments": {}}},
    {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "inspect", "arguments": {"target": "no-such-part"}}},
]


def run(cmd, out):
    data = ''.join(json.dumps(m) + '\n' for m in SESSION).encode()
    done = subprocess.run(cmd + ['serve', '--variant', 'V1', '--out', str(out)], input=data,
                          capture_output=True, timeout=300)
    return [json.loads(line) for line in done.stdout.decode().splitlines()]


class ProxyTests(unittest.TestCase):
    def test_metadata_added_and_results_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            direct = run([sys.executable, str(SERVER)], Path(tmp) / 'direct')
            proxied = run([sys.executable, '-I', str(PROXY), '--', sys.executable, str(SERVER)], Path(tmp) / 'proxied')
        self.assertEqual(len(direct), len(proxied))
        by_id = lambda msgs: {m['id']: m for m in msgs}
        d, p = by_id(direct), by_id(proxied)
        tools_d, tools_p = d[1]['result']['tools'], p[1]['result']['tools']
        self.assertEqual(len(tools_p), 18)
        for a, b in zip(tools_d, tools_p):
            self.assertEqual(b['_meta']['anthropic/maxResultSizeChars'], 400000)
            b = dict(b); meta = dict(b.pop('_meta')); meta.pop('anthropic/maxResultSizeChars')
            if meta:
                b['_meta'] = meta
            self.assertEqual(a, b)
        for i in (0, 2, 3):
            self.assertEqual(d[i], p[i])
        self.assertGreater(len(p[2]['result']['content'][0]['text']), 150000)


if __name__ == '__main__':
    unittest.main()
