"""Full source-role closure is distinct from a runtime hash match."""
from copy import deepcopy
import json,unittest
from tools import receive_current_variants as reader
from job_accuracy.independent import AssessmentInputError


def example():
    roles=json.loads(reader.ROLE_CONTRACT.read_bytes())
    paths=set(roles['runtime_modules'].values())|{roles['bootstrap']}|set(roles['supporting_files'])
    info={'source_files':{p:'0'*64 for p in paths}}
    manifest={'sources':{k:{'path':v,'sha256':'0'*64} for k,v in roles['runtime_modules'].items()},
              'bootstrap':{'path':roles['bootstrap'],'sha256':'0'*64}}
    return info,manifest,roles


def corruptions():
    rows=[]
    for kind in ('only-runtime','missing-builder','extra-file','missing-module','renamed-module','swapped-module-path','wrong-bootstrap'):
        info,manifest,roles=example();gate='batch-complete-source-roles'
        if kind=='only-runtime':
            for p in roles['supporting_files']:info['source_files'].pop(p)
        elif kind=='missing-builder':info['source_files'].pop(roles['supporting_files'][-1])
        elif kind=='extra-file':info['source_files']['unregistered.py']='0'*64
        elif kind=='wrong-bootstrap':manifest['bootstrap']['path']=roles['supporting_files'][0];gate='batch-bootstrap-role'
        else:
            gate='batch-runtime-module-roles';name=next(iter(manifest['sources']))
            if kind=='missing-module':manifest['sources'].pop(name)
            elif kind=='renamed-module':manifest['sources']['renamed']=manifest['sources'].pop(name)
            else:manifest['sources'][name]['path']=roles['supporting_files'][0]
        rows.append((kind,gate,(info,manifest,roles)))
    return rows


class CurrentSourceRoles(unittest.TestCase):
    def test_all_roles_have_distinct_explicit_counts(self):
        self.assertEqual(reader.source_roles(*example()),{'runtime_modules':18,'bootstrap_files':1,'supporting_files':12,'total_files':31})

    def test_incomplete_or_relabelled_closures_are_refused(self):
        for name,gate,args in corruptions():
            with self.subTest(case=name),self.assertRaisesRegex(AssessmentInputError,gate):reader.source_roles(*args)

    def test_source_path_order_has_no_semantic_effect(self):
        args=example();expected=reader.source_roles(*args)
        args[0]['source_files']=dict(reversed(list(args[0]['source_files'].items())))
        args[1]['sources']=dict(reversed(list(args[1]['sources'].items())))
        self.assertEqual(reader.source_roles(*args),expected)
