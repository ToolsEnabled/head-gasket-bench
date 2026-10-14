"""Small fixture JSON custody controls; no adapter/model initialization."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from hgj.backends import load_manifest
from hgj.codec import canonical
from hgj.fixtures import fixture_config

class ManifestBytesTests(unittest.TestCase):
    def fixture(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);root=Path(temp.name)
        config=fixture_config();inputs={}
        for name in ('geometry','service','labor','variants','policy'):
            path=root/(name+'.json');path.write_bytes(canonical(config[name]))
            inputs[name]={'path':path.name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
        manifest={'schema':'hgj/manifest/v1','inputs':inputs,'variant_id':config['variant_id'],'factors':config['factors'],'admission':None}
        path=root/'manifest.json';path.write_bytes(canonical(manifest));return root,path,manifest,config

    def test_input_is_parsed_from_the_same_verified_bytes(self):
        root,path,manifest,config=self.fixture();geometry=root/'geometry.json'
        def hash_then_change(target):
            data=target.read_bytes();pin=hashlib.sha256(data).hexdigest()
            if target==geometry:
                altered=json.loads(data);altered['engine_sha256']='b'*64;target.write_bytes(canonical(altered))
            return pin
        with patch('hgj.backends.file_digest',side_effect=hash_then_change):loaded,joint,soak=load_manifest(path)
        self.assertEqual(loaded['geometry'],config['geometry'])

    def test_job_manifest_raw_hash_is_checked_and_retained(self):
        root,path,manifest,config=self.fixture();pin=hashlib.sha256(path.read_bytes()).hexdigest()
        loaded,joint,soak=load_manifest(path,expected_sha256=pin)
        self.assertEqual(loaded['identity']['manifest_sha256'],pin)
        self.assertEqual(loaded['identity']['manifest_body_sha256'],hashlib.sha256(canonical(manifest)).hexdigest())
        path.write_bytes(canonical({**manifest,'variant_id':'changed-after-budget-read'}))
        with self.assertRaisesRegex(ValueError,'manifest.*hash'):load_manifest(path,expected_sha256=pin)
