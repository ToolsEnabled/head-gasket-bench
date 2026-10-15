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
    def inspect_fixture(self, path, sddl, own=False):
        from headgasket import windows_folder as win
        descriptor = ctypes.c_void_p()
        win.check(win.descriptor_parse(sddl, 1, ctypes.byref(descriptor), None))
        setter = win.api(win.a, 'SetFileSecurityW',
                         [win.w.LPCWSTR, win.w.DWORD, ctypes.c_void_p])
        try:
            win.check(setter(str(path), 0x80000004, descriptor))
        finally:
            win.free(descriptor)
        handle = win.open_file(str(path), 0x20081, 3, None, 3, 0x02200000, None)
        if handle == win.INVALID:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            return win.inspect(handle, own=own)
        finally:
            win.close(handle)

    def test_real_ancestor_acl_distinguishes_sibling_creation_and_replacement(self):
        from headgasket import windows_folder as win
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp) / 'ancestor'
            win.private_mkdir(folder)
            base = f'O:{win.user()}D:P(A;OICI;FA;;;{win.user()})(A;OICI;FA;;;SY)(A;OICI;FA;;;BA)'
            for mask in (0x2, 0x4, 0x1200a9):
                with self.subTest(allowed=hex(mask)):
                    self.inspect_fixture(folder, base + f'(A;;0x{mask:08x};;;WD)')
            for mask in (0x40, 0x10000, 0x40000, 0x80000, 0x10000000, 0x40000000):
                with self.subTest(refused=hex(mask)), self.assertRaisesRegex(OSError, 'other users can write'):
                    self.inspect_fixture(folder, base + f'(A;;0x{mask:08x};;;WD)')
            # Inherit-only entries do not grant access to this ancestor itself.
            self.inspect_fixture(folder, base + '(A;OICIIO;0x00000040;;;WD)')
            # The same foreign grant is refused on a private run folder.
            with self.assertRaisesRegex(OSError, 'other users can write'):
                self.inspect_fixture(folder, base + '(A;OICIIO;0x00000040;;;WD)', own=True)
            # Windows servicing may own an ancestor, but is never a trusted writer.
            ti = 'S-1-5-80-956008885-3418522649-1831038044-1853292631-2271478464'
            with self.assertRaisesRegex(OSError, 'other users can write'):
                self.inspect_fixture(folder, base + f'(A;;0x00040000;;;{ti})')

    def test_actual_volume_root_has_trusted_ancestor_but_not_private_owner(self):
        from headgasket import windows_folder as win
        root = Path(os.path.abspath(os.environ['TEMP'])).anchor
        handle = win.open_file(root, 0x20081, 3, None, 3, 0x02200000, None)
        if handle == win.INVALID:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            win.inspect(handle)
            # The measured C:\ owner is TrustedInstaller; never accept it as --out.
            with self.assertRaisesRegex(OSError, 'belongs to another user'):
                win.inspect(handle, own=True)
        finally:
            win.close(handle)

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
            # A second attempt still refuses: inspecting did not repair the ACL.
            with self.assertRaisesRegex(OSError, 'other users can write'):
                win.lock_folder(out)

    def test_a_different_owner_sid_is_refused(self):
        from headgasket import windows_folder as win
        prepared = os.environ.get('HG_NATIVE_OTHER_OWNER_FIXTURE')
        if prepared:
            # An elevated preparer can make this fixed, readable fixture before
            # the ordinary-user run. Inspection never repairs its ownership.
            with self.assertRaisesRegex(OSError, 'belongs to another user'):
                win.lock_folder(Path(prepared))
            with self.assertRaisesRegex(OSError, 'belongs to another user'):
                win.lock_folder(Path(prepared))
            return
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
            # Inspection also leaves the alternate owner unchanged.
            with self.assertRaisesRegex(OSError, 'belongs to another user'):
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

    def test_nonexistent_drive_is_refused_before_creation(self):
        from headgasket import windows_folder as win
        for letter in 'ZYXWVUTSRQPONMLKJIHGFED':
            root = letter + ':\\'
            if win.drive_type(root) == 1:  # DRIVE_NO_ROOT_DIR, without changing mappings.
                with self.assertRaisesRegex(OSError, 'fixed local drive'):
                    win.create_run_directory(root + 'te-winport-never-created\\run')
                return
        self.fail('no unused drive exists for the native volume-refusal fixture')

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
