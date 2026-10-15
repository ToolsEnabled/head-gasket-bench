"""Actual Windows security/lock checks. Never substitutes mocked Unix mode bits."""
import ctypes
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
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

    def test_retained_folder_allows_the_pinned_atomic_writer(self):
        from headgasket.windows_folder import create_run_directory, lock_folder
        from hgj.mcp import atomic_bytes
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / 'run'
            create_run_directory(out)
            lock = lock_folder(out)
            try:
                # Both CREATE and REPLACE must work under the real lifetime
                # lock, without changing the scientific environment's writer.
                for payload in (b'{"native":"first"}\n', b'{"native":"replace"}\n'):
                    atomic_bytes(out / 'run.json', payload)
                    self.assertEqual((out / 'run.json').read_bytes(), payload)
                self.assertFalse((out / 'run.json.tmp').exists())
                with self.assertRaisesRegex(OSError, 'another headgasket server'):
                    lock_folder(out)
            finally:
                lock.close()

    def test_writer_lease_is_released_after_known_child_process_death(self):
        from headgasket import windows_folder as win
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            out, ready, script = base / 'run', base / 'ready.json', base / 'holder.py'
            win.create_run_directory(out)
            script.write_text(
                'import json, os, sys, time\n'
                f'sys.path.insert(0, {str(ROOT)!r})\n'
                'from pathlib import Path\n'
                'from headgasket.windows_folder import lock_folder\n'
                'lock = lock_folder(Path(sys.argv[1]))\n'
                'Path(sys.argv[2]).write_text(json.dumps({"pid": os.getpid()}), encoding="utf-8")\n'
                'time.sleep(60)\n', encoding='utf-8')
            child = subprocess.Popen([sys.executable, '-I', '-S', '-B', str(script), str(out), str(ready)],
                                     stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE, close_fds=True)
            wait = win.api(win.k, 'WaitForSingleObject', [win.w.HANDLE, win.w.DWORD], win.w.DWORD)
            try:
                deadline = time.monotonic() + 10
                while not ready.exists():
                    if child.poll() is not None:
                        _, stderr = child.communicate(timeout=5)
                        self.fail('known holder exited before readiness: ' + stderr.decode('utf-8', errors='replace'))
                    self.assertLess(time.monotonic(), deadline, 'known holder readiness timed out')
                    time.sleep(0.025)
                self.assertEqual(json.loads(ready.read_text(encoding='utf-8')), {'pid': child.pid})
                self.assertEqual(wait(int(child._handle), 0), 258)
                with self.assertRaisesRegex(OSError, 'another headgasket server'):
                    win.lock_folder(out)
                # Popen retains the process HANDLE; this never selects a process
                # by name or a potentially reused PID.
                child.terminate()
                self.assertEqual(wait(int(child._handle), 5000), 0)
                _, stderr = child.communicate(timeout=5)
                self.assertEqual(stderr, b'')
                second = win.lock_folder(out)
                second.close()
                self.assertEqual(list(out.iterdir()), [])
            finally:
                if child.poll() is None:
                    child.kill()
                child.communicate(timeout=5)

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
