"""Bounded exact-source loading and StringIO replay; no subject/model process."""
import copy
import hashlib
import importlib
import io
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch
from hgj.codec import canonical, digest
from hgj.fixtures import fixture_config
from tools.source_server import SourceRuntime
from tools import source_server

# The complete closure, listed explicitly so that a drift between this list, the
# loader, the manifest emitter and the shipped manifest fails loudly.
SOURCE_PATHS={
    'hgj':'hgj/__init__.py',
    **{'hgj.'+name:'hgj/'+name+'.py' for name in (
        'codec','api','geometry','initial_conditions','action_conditions',
        'action_domains','game','backends','exact_imports','mcp',
        'repair_scoring','human_time','repair_report','procedure_actions',
        'removal_policy','benchmark_geometry','checkpoints')},
}


class ClosureListTests(unittest.TestCase):
    def test_closure_list_matches_loader_emitter_and_shipped_manifest(self):
        from tools import freeze_environment_source as emitter
        self.assertEqual(SOURCE_PATHS, source_server.SOURCE_PATHS)
        self.assertEqual(SOURCE_PATHS, emitter.SOURCE_PATHS)
        shipped=json.loads((Path(__file__).resolve().parents[1]/'data/environment-source.json').read_bytes())
        self.assertEqual(set(shipped['sources']), set(SOURCE_PATHS))
        self.assertEqual(len(SOURCE_PATHS), 18)

class SourceRuntimeTests(unittest.TestCase):
    def snapshot(self, mutation=None):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        root=Path(temp.name);project=Path(__file__).resolve().parents[1]
        sources={}
        for name,path in SOURCE_PATHS.items():
            data=(project/path).read_bytes();target=root/path
            target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
            sources[name]={'path':path,'sha256':hashlib.sha256(data).hexdigest()}
        bootstrap='tools/source_server.py';target=root/bootstrap;target.parent.mkdir()
        target.write_bytes((project/bootstrap).read_bytes())
        manifest={'schema':'hgj/environment-source/v1','sources':sources,
                  'bootstrap':{'path':bootstrap,'sha256':hashlib.sha256(target.read_bytes()).hexdigest()}}
        if mutation:mutation(root,manifest)
        raw=json.dumps(manifest,indent=2,ensure_ascii=False).encode()+b'\n'
        path=root/'source.json';path.write_bytes(raw)
        return root,path,hashlib.sha256(raw).hexdigest(),manifest

    def test_exact_snapshot_ignores_cached_modules_and_records_private_source_replay(self):
        root,path,pin,manifest=self.snapshot();runtime=SourceRuntime(root,path,pin)
        old=sys.modules.get('hgj.game');poison=types.ModuleType('hgj.game');poison.Game=object
        sys.modules['hgj.game']=poison
        try:
            with runtime.active():
                mod=importlib.import_module('hgj.mcp');game_mod=importlib.import_module('hgj.game')
                self.assertIsNot(game_mod,poison)
                game=game_mod.Game(fixture_config(),source_runtime=runtime)
                lines=[{'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':'2025-11-25'}},
                       {'jsonrpc':'2.0','method':'notifications/initialized'},
                       {'jsonrpc':'2.0','id':2,'method':'tools/call','params':{'name':'look','arguments':{}}}]
                sink=io.StringIO();mod.serve(game,io.StringIO(''.join(canonical(row).decode() for row in lines)),sink,root/'run')
                record=json.loads((root/'run/run.json').read_text())
                self.assertEqual(record['schema'],'hgj/run/v2')
                self.assertEqual(record['environment_source'],runtime.identity)
                self.assertEqual(record['environment_source_sha256'],digest(runtime.identity))
                self.assertEqual(record['environment_source']['source_manifest_sha256'],pin)
                self.assertNotEqual(pin,record['environment_source']['source_manifest_body_sha256'])
                self.assertNotIn(pin,sink.getvalue())
                self.assertEqual(game_mod.replay(record,source_runtime=runtime),record)
                self.assertEqual(set(runtime.executed_modules),set(SOURCE_PATHS))
            self.assertIs(sys.modules['hgj.game'],poison)
        finally:
            if old is None:sys.modules.pop('hgj.game',None)
            else:sys.modules['hgj.game']=old

    def test_tampered_source_or_manifest_refuses_before_import(self):
        for damaged in ('hgj/game.py','tools/source_server.py'):
            root,path,pin,manifest=self.snapshot();(root/damaged).write_text('# damaged\n')
            with patch('importlib.import_module',side_effect=AssertionError('Import reached')) as spy:
                with self.assertRaisesRegex(ValueError,'source.*hash|bootstrap.*hash'):SourceRuntime(root,path,pin)
                spy.assert_not_called()
        root,path,pin,manifest=self.snapshot();path.write_text('{}\n')
        with self.assertRaisesRegex(ValueError,'manifest.*hash'):SourceRuntime(root,path,pin)

    def test_byte_snapshot_cannot_change_between_validation_and_execution(self):
        root,path,pin,manifest=self.snapshot();runtime=SourceRuntime(root,path,pin)
        (root/'hgj/game.py').write_text('raise AssertionError("unverified later bytes")\n')
        with runtime.active():
            game_mod=importlib.import_module('hgj.game')
            game=game_mod.Game(fixture_config(),source_runtime=runtime)
            self.assertTrue(game.call('look',{})['ok'])
            self.assertEqual(game.export()['environment_source']['sources']['hgj.game'],manifest['sources']['hgj.game'])

    def test_source_closure_is_closed_and_source_identity_mismatch_precedes_game(self):
        mutations=(
            lambda root,m:m['sources'].pop('hgj.codec'),
            lambda root,m:m['sources'].update({'hgj.fixtures':{'path':'hgj/fixtures.py','sha256':'0'*64}}),
            lambda root,m:m['sources']['hgj.game'].update({'path':'../outside.py'}),
            lambda root,m:m['sources']['hgj.game'].update({'sha256':'g'*64}),
            lambda root,m:m.update({'extra':'unapproved'}),
        )
        for mutation in mutations:
            root,path,pin,manifest=self.snapshot(mutation)
            with self.assertRaises(ValueError):SourceRuntime(root,path,pin)
        root,path,pin,manifest=self.snapshot();runtime=SourceRuntime(root,path,pin)
        with runtime.active():
            game_mod=importlib.import_module('hgj.game');record=game_mod.Game(fixture_config(),source_runtime=runtime).export()
            bad=copy.deepcopy(runtime.identity);bad['source_manifest_sha256']='0'*64
            with patch.object(game_mod,'Game',side_effect=AssertionError('Game constructor reached')) as spy:
                for supplied in (None,bad):
                    with self.assertRaisesRegex(ValueError,'environment source'):game_mod.replay(record,environment_source=supplied)
                spy.assert_not_called()
            record['environment_source_sha256']='0'*64
            with self.assertRaisesRegex(ValueError,'environment source'):game_mod.replay(record,source_runtime=runtime)

    def test_direct_entry_hold_and_unbound_stdio_precede_manifest_loading(self):
        with patch('importlib.import_module',side_effect=AssertionError('Import reached')) as imports:
            with self.assertRaisesRegex(RuntimeError,'process control.*unqualified'):source_server.main()
            imports.assert_not_called()
        root,path,pin,manifest=self.snapshot();runtime=SourceRuntime(root,path,pin)
        with runtime.active():
            mcp=importlib.import_module('hgj.mcp')
            with patch.object(mcp,'load_manifest',side_effect=AssertionError('Manifest loader reached')) as loader:
                with self.assertRaisesRegex(ValueError,'Source-bound runtime'):mcp.run_manifest('not-read','not-created',None)
                loader.assert_not_called()

    def test_actual_manifest_and_source_bound_replay_keep_identical_private_record(self):
        root,path,pin,source_manifest=self.snapshot();runtime=SourceRuntime(root,path,pin)
        config=fixture_config();inputs={}
        for name in ('geometry','service','labor','variants','policy'):
            target=root/(name+'.json');target.write_bytes(canonical(config[name]))
            inputs[name]={'path':target.name,'sha256':hashlib.sha256(target.read_bytes()).hexdigest()}
        manifest=root/'job-manifest.json';manifest.write_bytes(canonical({'schema':'hgj/manifest/v1',
            'inputs':inputs,'variant_id':config['variant_id'],'factors':config['factors'],'admission':None}))
        with runtime.active():
            backends=importlib.import_module('hgj.backends');game_mod=importlib.import_module('hgj.game')
            config,joint,soak=backends.load_manifest(manifest)
            game=game_mod.Game(config,joint=joint,soak=soak,source_runtime=runtime)
            self.assertTrue(game.call('look',{})['ok']);record=game.export()
            record_path=root/'run.json';record_path.write_bytes(canonical(record));replay_path=root/'replay.json'
            actual=game_mod.replay(record,source_runtime=runtime)
            with replay_path.open('xb') as stream:stream.write(canonical(actual))
            self.assertEqual(actual,record);self.assertEqual(replay_path.read_bytes(),record_path.read_bytes())
            with patch.object(backends,'load_manifest',side_effect=AssertionError('Deployment loader reached')) as loader:
                with self.assertRaisesRegex(RuntimeError,'process control.*unqualified'):source_server.replay_manifest(record_path,manifest,replay_path,runtime,hashlib.sha256(manifest.read_bytes()).hexdigest())
                loader.assert_not_called()

    def test_source_replay_mismatch_and_legacy_utility_refuse_before_backend_constructor(self):
        root,path,pin,manifest=self.snapshot();runtime=SourceRuntime(root,path,pin)
        with runtime.active():
            backends=importlib.import_module('hgj.backends');game_mod=importlib.import_module('hgj.game')
            record=game_mod.Game(fixture_config(),source_runtime=runtime).export()
            record['environment_source_sha256']='0'*64;record_path=root/'run.json';record_path.write_bytes(canonical(record))
            with patch.object(backends,'load_manifest',side_effect=AssertionError('Manifest load reached')) as loader:
                with self.assertRaisesRegex(ValueError,'(?i)environment source'):source_server.replay_manifest(record_path,'not-read',root/'not-written',runtime.identity,'0'*64)
                loader.assert_not_called()
        # The sandbox-only legacy utility tools/replay.py is not shipped; its refusal
        # check is dropped here. The public replay path is headgasket.cli.

    def test_schema_only_identity_cannot_claim_source_custody_or_reach_manifest_loader(self):
        from hgj import mcp
        with patch.object(mcp,'load_manifest',return_value=(fixture_config(),None,None)) as loader:
            with patch.object(sys,'stdin',io.StringIO('')),patch.object(sys,'stdout',io.StringIO()):
                with self.assertRaisesRegex(ValueError,'source|runtime'):
                    mcp.run_manifest('not-read','not-created',{'schema':'hgj/environment-source-identity/v1'})
            loader.assert_not_called()
        root,path,pin,manifest=self.snapshot();runtime=SourceRuntime(root,path,pin)
        with runtime.active():game_mod=importlib.import_module('hgj.game')
        with self.assertRaisesRegex(ValueError,'source|runtime'):
            game_mod.Game(fixture_config(),source_runtime=runtime)

    def test_source_claimed_game_cannot_continue_after_runtime_context_ends(self):
        root,path,pin,manifest=self.snapshot();runtime=SourceRuntime(root,path,pin)
        with runtime.active():
            game_mod=importlib.import_module('hgj.game');game=game_mod.Game(fixture_config(),source_runtime=runtime)
        with self.assertRaisesRegex(ValueError,'source|runtime'):game.call('look',{})

    def test_verified_runtime_still_holds_physical_backend_and_server_helpers(self):
        from tests.test_game_condition_effects import GameConditionEffectsTests
        helper=GameConditionEffectsTests();self.addCleanup(helper.doCleanups);config,old_backend=helper.fixture()
        root,path,pin,manifest=self.snapshot();runtime=SourceRuntime(root,path,pin)
        with runtime.active():
            backends=importlib.import_module('hgj.backends');game_mod=importlib.import_module('hgj.game');mcp=importlib.import_module('hgj.mcp')
            backend=backends.Backend(old_backend.descriptor,config['admission'])
            with self.assertRaisesRegex(RuntimeError,'process control.*unqualified'):backend.initialize(config)
            with patch.object(backend,'initialize',side_effect=AssertionError('Model initialization reached')) as initializer:
                with self.assertRaisesRegex(RuntimeError,'process control.*unqualified'):game_mod.Game(config,joint=backend,source_runtime=runtime)
                initializer.assert_not_called()
            with patch.object(mcp,'load_manifest',side_effect=AssertionError('Server manifest read reached')) as loader:
                with self.assertRaisesRegex(RuntimeError,'process control.*unqualified'):mcp.run_manifest('not-read','not-created',runtime,'0'*64)
                loader.assert_not_called()
