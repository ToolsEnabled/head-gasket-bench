import tempfile
import unittest
import sys
import py_compile
import importlib
import os
from pathlib import Path
from hgj.backends import Backend, validate_score
from hgj.codec import file_digest, digest
from hgj.fixtures import FixtureSoak, fixture_config, FixtureJoint, correct_job
from hgj.game import Game
from hgj.exact_imports import ExactImports


class BackendTests(unittest.TestCase):
    def test_unlisted_package_child_cannot_fall_back_to_live_source(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); init=root/'__init__.py';init.write_text('')
            extra=root/'extra.py';extra.write_text('VALUE = "unpinned"\n')
            api=root/'api.py';api.write_text('from hgj_unlisted_parent import extra\nVALUE = extra.VALUE\n')
            binder=ExactImports([{'module_name':'hgj_unlisted_parent','path':str(init),'sha256':file_digest(init)},
                                 {'module_name':'hgj_unlisted_parent.api','path':str(api),'sha256':file_digest(api)}])
            with binder.active():
                with self.assertRaises(ImportError):importlib.import_module('hgj_unlisted_parent.api')
            # A previously imported child must be quarantined too, then restored.
            import types
            cached=types.ModuleType('hgj_unlisted_parent.extra');cached.VALUE='cached unpinned'
            sys.modules[cached.__name__]=cached
            try:
                with binder.active():
                    with self.assertRaises(ImportError):importlib.import_module('hgj_unlisted_parent.api')
                self.assertIs(sys.modules[cached.__name__],cached)
            finally:sys.modules.pop(cached.__name__,None)
    def test_empty_namespace_parent_loads_only_pinned_child_sources(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); dep=root/'api.py'; dep.write_text('VALUE = "pinned namespace child"\n')
            p=root/'adapter.py'; p.write_text('from hgj_test_namespace.api import VALUE\ndef initialize(c): return {"value":VALUE}\n')
            desc={'schema':'hgj/backend/v1','kind':'joint','module':str(p),'sha256':file_digest(p),
                  'qualification':'validated-physics','evidence_sha256':'a'*64,'dependencies':[
                    {'module_name':'hgj_test_namespace','namespace':True,'sha256':__import__('hashlib').sha256(b'').hexdigest()},
                    {'path':str(dep),'sha256':file_digest(dep),'module_name':'hgj_test_namespace.api'}]}
            a={'schema':'hgj/admission/v1','status':'validated-physics','joint_descriptor_sha256':digest(desc),
               'soak_descriptor_sha256':'b'*64,'geometry_sha256':'c'*64,'validation_sha256':'d'*64}
            b=Backend(desc,a); self.assertEqual(b.initialize({}),{'value':'pinned namespace child'})
            self.assertNotIn('hgj_test_namespace',sys.modules)

    def test_dependency_executes_pinned_bytes_despite_stale_pyc_and_module(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); dep=root/'hgj_test_dependency.py'
            dep.write_text('VALUE = "CACHE"\n')
            py_compile.compile(str(dep),doraise=True)
            saved=dep.stat(); sys.path.insert(0,d)
            try:
                importlib.import_module('hgj_test_dependency')
                dep.write_text('VALUE = "SOURCE"\n')
                # Same size and timestamp makes the stale cache an actual risk.
                dep.write_text('VALUE = "BYTES"\n')
                os.utime(dep,ns=(saved.st_atime_ns,saved.st_mtime_ns))
                p=root/'adapter.py'; p.write_text('import hgj_test_dependency\ndef initialize(c): return {"value":hgj_test_dependency.VALUE}\n')
                desc={'schema':'hgj/backend/v1','kind':'joint','module':str(p),'sha256':file_digest(p),
                      'qualification':'validated-physics','evidence_sha256':'a'*64,
                      'dependencies':[{'path':str(dep),'sha256':file_digest(dep),'module_name':'hgj_test_dependency'}]}
                a={'schema':'hgj/admission/v1','status':'validated-physics','joint_descriptor_sha256':digest(desc),
                   'soak_descriptor_sha256':'b'*64,'geometry_sha256':'c'*64,'validation_sha256':'d'*64}
                b=Backend(desc,a); self.assertEqual(b.initialize({}),{'value':'BYTES'})
                self.assertEqual(sys.modules['hgj_test_dependency'].VALUE,'CACHE')
                dep.write_text('VALUE = "WRONG"\n')
                with self.assertRaises(ValueError): b.initialize({})
            finally:
                sys.path.remove(d); sys.modules.pop('hgj_test_dependency',None)

    def test_missing_admission_and_changed_source_refuse(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'trusted.py'; p.write_text('def initialize(config): return {}\n')
            desc={'schema':'hgj/backend/v1','kind':'joint','module':str(p),'sha256':file_digest(p),
                  'qualification':'validated-physics','evidence_sha256':'a'*64,'dependencies':[]}
            with self.assertRaises(ValueError): Backend(desc,{})
            a={'schema':'hgj/admission/v1','status':'validated-physics','joint_descriptor_sha256':digest(desc),
               'soak_descriptor_sha256':'b'*64,'geometry_sha256':'c'*64,'validation_sha256':'d'*64}
            b=Backend(desc,a); self.assertEqual(b.initialize({}),{})
            p.write_text('def initialize(config): return {"altered": True}\n')
            with self.assertRaises(ValueError): b.initialize({})

    def test_non_scores_and_incomplete_soak_cannot_award_pass(self):
        s={'schema':'hgj/soak-result/v1','status':'UNQUALIFIED','qualification':'unqualified',
           'pass':None,'time_to_failure_s':None,'cause':'missing reduced model'}
        validate_score(s,physical=True)
        s['pass']=False
        with self.assertRaises(ValueError): validate_score(s,physical=True)
        g=Game(fixture_config(),joint=FixtureJoint(),soak=FixtureSoak()); correct_job(g)
        for mutation in [('simulated_duration_s',3600),('time_to_failure_s',10),('cause','leak')]:
            s={**g.score,mutation[0]:mutation[1]}
            with self.assertRaises(ValueError): validate_score(s)

    def test_non_score_finish_is_retained_without_failure_credit(self):
        class Unresolved:
            def score(self,job):
                return {'schema':'hgj/soak-result/v1','status':'UNRESOLVED','qualification':'unqualified',
                        'pass':None,'time_to_failure_s':None,'cause':'margin interval spans zero'}
        g=Game(fixture_config(),joint=FixtureJoint(),soak=Unresolved()); correct_job(g)
        self.assertTrue(g.finished); self.assertIsNone(g.score['pass'])
        self.assertEqual(g.export()['scoring_status'],'UNRESOLVED')

    def test_physical_status_and_pinned_holds_refuse_false_success(self):
        g=Game(fixture_config(),joint=FixtureJoint(),soak=FixtureSoak()); correct_job(g)
        s={**g.score,'qualification':'validated-physics','status':'PASS','pass':False,
           'time_to_failure_s':10,'cause':'leak','failure_time_bracket_s':[9,10],'witness':{'margin':-1}}
        with self.assertRaises(ValueError): validate_score(s,physical=True)
        s={**g.score,'qualification':'validated-physics','status':'PASS',
           'protocol':{'main_rpm':3000,'main_duration_s':3600,'idle_hold_s':0.001,'redline_hold_s':0.001,'redline_rpm':1}}
        with self.assertRaises(ValueError): validate_score(s,physical=True)
