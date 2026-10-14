import io
import json
import tempfile
import unittest
from pathlib import Path
from hgj.codec import canonical
from hgj.fixtures import fixture_config
from hgj.game import Game
from hgj.mcp import serve


class MCPTests(unittest.TestCase):
    def test_planted_host_file_not_reachable_by_real_stdio_dispatch(self):
        with tempfile.TemporaryDirectory() as d:
            plant=Path(d)/'answers.txt'; marker='PLANTED_FILE_4ecad8f95c'; plant.write_text(marker)
            lines=[{'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':'2025-11-25'}},
                   {'jsonrpc':'2.0','method':'notifications/initialized'},
                   {'jsonrpc':'2.0','id':2,'method':'tools/list'},
                   {'jsonrpc':'2.0','id':3,'method':'resources/read','params':{'uri':str(plant)}},
                   {'jsonrpc':'2.0','id':4,'method':'tools/call','params':{'name':'read_file','arguments':{'path':str(plant)}}},
                   {'jsonrpc':'2.0','id':5,'method':'tools/call','params':{'name':'search_service_info','arguments':{'query':str(plant)}}},
                   {'jsonrpc':'2.0','id':6,'method':'tools/call','params':{'name':'look','arguments':{'path':str(plant)}}},
                   {'jsonrpc':'2.0','id':7,'method':'tools/call','params':{'name':'finish','arguments':{'state':{'pass':True}}}}]
            inp=io.StringIO(''.join(canonical(x).decode() for x in lines)); out=io.StringIO()
            serve(Game(fixture_config()),inp,out,Path(d)/'run')
            self.assertNotIn(marker,out.getvalue()); self.assertEqual(plant.read_text(),marker)
            response=[json.loads(x) for x in out.getvalue().splitlines()]
            self.assertEqual(response[2]['error']['code'],-32601)
            for i in (3,5,6): self.assertTrue(response[i]['result']['isError'])
            saved=json.loads((Path(d)/'run/run.json').read_text()); self.assertEqual(len(saved['actions']),4)
            self.assertIsNone(saved['score'])

    def test_invalid_request_and_initialization_refuse(self):
        with tempfile.TemporaryDirectory() as d:
            sink=io.StringIO()
            serve(Game(fixture_config()),io.StringIO('{bad}\n'+json.dumps({'jsonrpc':'2.0','id':1,'method':'tools/call','params':{'name':'look'}})+'\n'),sink,d)
            self.assertEqual(len(sink.getvalue().splitlines()),2)
            self.assertTrue(all('error' in json.loads(x) for x in sink.getvalue().splitlines()))
