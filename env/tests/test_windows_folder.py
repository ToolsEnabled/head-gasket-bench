"""Actual Windows security/lock checks. Never substitutes mocked Unix mode bits."""
import ctypes
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


@unittest.skipUnless(os.name == 'nt', 'requires native Windows NTFS and token security')
class WindowsFolderTests(unittest.TestCase):
    def test_created_private_folder_accepts_owner_and_excludes_second_writer(self):
        from headgasket.windows_folder import private_mkdir, lock_folder
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / 'run'
            private_mkdir(out)
            first = lock_folder(out)
            try:
                with self.assertRaisesRegex(OSError, 'another headgasket server'):
                    lock_folder(out)
                child = subprocess.run([sys.executable, '-B', str(ROOT / 'bin' / 'headgasket-mcp'),
                                        'serve', '--variant', 'V1', '--out', str(out)], input=b'',
                                       capture_output=True, timeout=30)
                self.assertEqual(child.returncode, 1, child.stderr)
                self.assertIn(b'another headgasket server', child.stderr)
                self.assertEqual(list(out.iterdir()), [])
            finally:
                first.close()
            second = lock_folder(out)
            second.close()

    def test_broad_acl_is_refused_without_repair(self):
        from headgasket import windows_folder as win
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / 'shared'
            win.private_mkdir(out)
            sid = win.user()
            descriptor = ctypes.c_void_p()
            win.check(win.descriptor_parse(f'O:{sid}D:P(A;OICI;FA;;;{sid})(A;OICI;FA;;;WD)',
                                            1, ctypes.byref(descriptor), None))
            setter = win.api(win.a, 'SetFileSecurityW',
                             [win.w.LPCWSTR, win.w.DWORD, ctypes.c_void_p])
            try:
                win.check(setter(str(out), 0x80000004, descriptor))
            finally:
                win.free(descriptor)
            with self.assertRaisesRegex(OSError, 'other users can write'):
                win.lock_folder(out)

    def test_a_different_owner_sid_is_refused(self):
        from headgasket import windows_folder as win
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / 'other-owner'
            win.private_mkdir(out)
            descriptor = ctypes.c_void_p()
            win.check(win.descriptor_parse('O:BA', 1, ctypes.byref(descriptor), None))
            setter = win.api(win.a, 'SetFileSecurityW',
                             [win.w.LPCWSTR, win.w.DWORD, ctypes.c_void_p])
            try:
                if not setter(str(out), 1, descriptor):
                    error = ctypes.get_last_error()
                    if error in (5, 1307, 1314):
                        self.skipTest('fixture needs an administrator to assign the alternate owner SID')
                    raise ctypes.WinError(error)
            finally:
                win.free(descriptor)
            with self.assertRaisesRegex(OSError, 'belongs to another user'):
                win.lock_folder(out)
            # A second attempt still refuses: inspecting did not repair the ACL.
            with self.assertRaisesRegex(OSError, 'other users can write'):
                win.lock_folder(out)

    def test_junction_ancestor_is_refused(self):
        from headgasket.windows_folder import private_mkdir, lock_folder
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            target, link = base / 'target', base / 'link'
            target.mkdir()
            made = subprocess.run(['C:\\Windows\\System32\\cmd.exe', '/d', '/c',
                                   'mklink', '/J', str(link), str(target)],
                                  capture_output=True, timeout=15)
            self.assertEqual(made.returncode, 0, made.stderr)
            try:
                private_mkdir(target / 'run')
                with self.assertRaisesRegex(OSError, 'reparse'):
                    lock_folder(link / 'run')
            finally:
                link.rmdir()

    def test_parent_cannot_be_renamed_until_lock_release(self):
        from headgasket.windows_folder import private_mkdir, lock_folder
        with tempfile.TemporaryDirectory() as temp:
            parent = Path(temp) / 'parent'
            parent.mkdir()
            out = parent / 'run'
            private_mkdir(out)
            lock = lock_folder(out)
            try:
                with self.assertRaises(OSError):
                    parent.rename(Path(temp) / 'changed')
            finally:
                lock.close()
            parent.rename(Path(temp) / 'changed')

    def test_local_path_policy_refuses_namespaces_streams_and_reserved_names(self):
        from headgasket.windows_folder import local_path
        for value in ('\\\\server\\share\\run', '\\\\?\\C:\\run',
                      'C:\\run:stream', 'C:\\NUL', 'C:\\run.'):
            with self.subTest(value=value), self.assertRaises(OSError):
                local_path(value)

    def test_creation_refuses_junction_before_making_any_directory(self):
        from headgasket.windows_folder import create_run_directory
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            target, link = base / 'target', base / 'link'
            target.mkdir()
            made = subprocess.run(['C:\\Windows\\System32\\cmd.exe', '/d', '/c',
                                   'mklink', '/J', str(link), str(target)],
                                  capture_output=True, timeout=15)
            self.assertEqual(made.returncode, 0, made.stderr)
            try:
                with self.assertRaisesRegex(OSError, 'reparse'):
                    create_run_directory(link / 'new-parent' / 'run')
                self.assertEqual(list(target.iterdir()), [])
            finally:
                link.rmdir()


if __name__ == '__main__':
    unittest.main()
