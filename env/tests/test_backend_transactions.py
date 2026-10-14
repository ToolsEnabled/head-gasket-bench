"""Pure stdlib backend serialization controls, no actual model execution."""
import tempfile
import unittest
from pathlib import Path
from hgj.backends import Backend
from hgj.codec import digest,file_digest

class BackendTransactionTests(unittest.TestCase):
    def test_main_and_declared_dependency_globals_do_not_survive_calls_or_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);dep=root/'state.py';dep.write_text('counter=0\n')
            source=root/'facade.py';source.write_text('''import transport_private_state
counter=0
def apply(state,op):
    global counter
    counter+=1;transport_private_state.counter+=1
    if op.get('fail'):raise ValueError('Synthetic failure after module changes')
    return {'main':counter,'dependency':transport_private_state.counter}
''')
            descriptor={'schema':'hgj/backend/v1','kind':'joint','qualification':'validated-physics',
                'module':str(source),'sha256':file_digest(source),'dependencies':[
                {'module_name':'transport_private_state','path':str(dep),'sha256':file_digest(dep)}]}
            admission={'schema':'hgj/admission/v1','status':'validated-physics','geometry_sha256':'a'*64,
                'joint_descriptor_sha256':digest(descriptor),'soak_descriptor_sha256':'b'*64,'validation_sha256':'e'*64}
            backend=Backend(descriptor,admission)
            self.assertEqual(backend.apply({},{}),{'main':1,'dependency':1})
            with self.assertRaises(ValueError):backend.apply({},{'fail':True})
            self.assertEqual(backend.apply({},{}),{'main':1,'dependency':1})
