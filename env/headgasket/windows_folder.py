"""Native NTFS run-folder custody. Imported only on Windows.

The scientific environment is unchanged. These handles protect its pathname
writes against other accounts; they do not isolate hostile code in this account.
SYSTEM and Administrators remain trusted, as they are by Windows file security.
"""
import ctypes as c
from ctypes import wintypes as w
import os
from pathlib import Path

k = c.WinDLL('kernel32', use_last_error=True)
a = c.WinDLL('advapi32', use_last_error=True)
INVALID = c.c_void_p(-1).value


def api(dll, name, args, result=w.BOOL):
    fn = getattr(dll, name)
    fn.argtypes, fn.restype = args, result
    return fn


class Security(c.Structure):
    _fields_ = [('length', w.DWORD), ('descriptor', c.c_void_p), ('inherit', w.BOOL)]


class FileInfo(c.Structure):
    _fields_ = [('attributes', w.DWORD), ('created', w.FILETIME),
                ('accessed', w.FILETIME), ('written', w.FILETIME),
                ('volume', w.DWORD), ('size_hi', w.DWORD), ('size_lo', w.DWORD),
                ('links', w.DWORD), ('index_hi', w.DWORD), ('index_lo', w.DWORD)]


class AclInfo(c.Structure):
    _fields_ = [('count', w.DWORD), ('used', w.DWORD), ('free', w.DWORD)]


class SidAttr(c.Structure):
    _fields_ = [('sid', c.c_void_p), ('attributes', w.DWORD)]


close = api(k, 'CloseHandle', [w.HANDLE])
free = api(k, 'LocalFree', [c.c_void_p], c.c_void_p)
current = api(k, 'GetCurrentProcess', [], w.HANDLE)
open_token = api(a, 'OpenProcessToken', [w.HANDLE, w.DWORD, c.POINTER(w.HANDLE)])
token_info = api(a, 'GetTokenInformation', [w.HANDLE, c.c_int, c.c_void_p, w.DWORD, c.POINTER(w.DWORD)])
sid_string = api(a, 'ConvertSidToStringSidW', [c.c_void_p, c.POINTER(c.c_void_p)])
sid_equal = api(a, 'EqualSid', [c.c_void_p, c.c_void_p])
sid_parse = api(a, 'ConvertStringSidToSidW', [w.LPCWSTR, c.POINTER(c.c_void_p)])
descriptor_parse = api(a, 'ConvertStringSecurityDescriptorToSecurityDescriptorW',
                       [w.LPCWSTR, w.DWORD, c.POINTER(c.c_void_p), c.c_void_p])
create_dir = api(k, 'CreateDirectoryW', [w.LPCWSTR, c.POINTER(Security)])
open_file = api(k, 'CreateFileW', [w.LPCWSTR, w.DWORD, w.DWORD, c.c_void_p,
                                 w.DWORD, w.DWORD, w.HANDLE], w.HANDLE)
file_info = api(k, 'GetFileInformationByHandle', [w.HANDLE, c.POINTER(FileInfo)])
get_security = api(a, 'GetSecurityInfo', [w.HANDLE, w.DWORD, w.DWORD,
                                       c.POINTER(c.c_void_p), c.c_void_p,
                                       c.POINTER(c.c_void_p), c.c_void_p,
                                       c.POINTER(c.c_void_p)], w.DWORD)
acl_info = api(a, 'GetAclInformation', [c.c_void_p, c.c_void_p, w.DWORD, c.c_int])
get_ace = api(a, 'GetAce', [c.c_void_p, w.DWORD, c.POINTER(c.c_void_p)])
volume_info = api(k, 'GetVolumeInformationByHandleW', [w.HANDLE, w.LPWSTR, w.DWORD,
                                                    c.c_void_p, c.c_void_p, c.c_void_p,
                                                    w.LPWSTR, w.DWORD])


def check(ok):
    if not ok:
        raise c.WinError(c.get_last_error())
    return ok


def user():
    token = w.HANDLE()
    check(open_token(current(), 8, c.byref(token)))
    try:
        size = w.DWORD()
        token_info(token, 1, None, 0, c.byref(size))
        buf = c.create_string_buffer(size.value)
        check(token_info(token, 1, buf, size, c.byref(size)))
        ptr = c.cast(buf, c.POINTER(SidAttr)).contents.sid
        text = c.c_void_p()
        check(sid_string(ptr, c.byref(text)))
        try:
            return c.wstring_at(text)
        finally:
            free(text)
    finally:
        close(token)


def local_path(value):
    raw = Path(value)
    if any(':' in part or part.endswith((' ', '.')) or Path(part).is_reserved()
           for part in raw.parts[1:]):
        raise OSError('run folders refuse alternate streams, reserved names and trailing dots/spaces')
    path = Path(os.path.abspath(value))
    text = str(path)
    if (len(path.drive) != 2 or path.drive[1] != ':' or not path.root
            or text.startswith(('\\\\', '\\??\\')) or len(text) > 240
            or any(':' in part or part.endswith((' ', '.')) or Path(part).is_reserved()
                   for part in path.parts[1:])):
        raise OSError('run folders require an ordinary local drive path of at most 240 characters')
    return path


def private_mkdir(path):
    """Create an empty folder with its final protected inherited DACL atomically."""
    path = local_path(path)
    sid = user()
    descriptor = c.c_void_p()
    sddl = f'O:{sid}G:{sid}D:P(A;OICI;FA;;;{sid})(A;OICI;FA;;;SY)(A;OICI;FA;;;BA)'
    check(descriptor_parse(sddl, 1, c.byref(descriptor), None))
    try:
        security = Security(c.sizeof(Security), descriptor, False)
        if not create_dir(str(path), c.byref(security)):
            error = c.get_last_error()
            if error == 183:
                raise FileExistsError(str(path))
            raise c.WinError(error)
    finally:
        free(descriptor)


def inspect(handle, own=False):
    """Reject reparse handles and ACLs permitting other accounts to replace data."""
    info = FileInfo()
    check(file_info(handle, c.byref(info)))
    if not info.attributes & 0x10 or info.attributes & 0x400:
        raise OSError('--out and every ancestor must be real directories, without reparse points')
    owner, dacl, descriptor = c.c_void_p(), c.c_void_p(), c.c_void_p()
    error = get_security(handle, 1, 5, c.byref(owner), None, c.byref(dacl), None, c.byref(descriptor))
    if error:
        raise c.WinError(error)
    trusted = []
    try:
        for text in (user(), 'S-1-5-18', 'S-1-5-32-544'):
            ptr = c.c_void_p()
            check(sid_parse(text, c.byref(ptr)))
            trusted.append(ptr)
        if own and not sid_equal(owner, trusted[0]):
            raise OSError('--out belongs to another user; choose a new folder')
        if not own and not any(sid_equal(owner, sid) for sid in trusted):
            raise OSError('a run-folder ancestor belongs to an untrusted account')
        if not dacl:
            raise OSError('--out has a null DACL; other users can write to it')
        details = AclInfo()
        check(acl_info(dacl, c.byref(details), c.sizeof(details), 2))
        for index in range(details.count):
            ace = c.c_void_p()
            check(get_ace(dacl, index, c.byref(ace)))
            kind = c.c_ubyte.from_address(ace.value).value
            flags = c.c_ubyte.from_address(ace.value + 1).value
            if kind == 1:  # Deny ACE cannot grant access.
                continue
            if kind != 0:
                raise OSError('unrecognized run-folder ACL entry; refusing unknown access')
            mask = w.DWORD.from_address(ace.value + 4).value
            principal = c.c_void_p(ace.value + 8)
            if any(sid_equal(principal, sid) for sid in trusted):
                continue
            # Ancestors can be publicly readable and allow sibling creation. They
            # must not allow another account to delete/replace an existing child,
            # change its DACL/owner, or exercise generic write/all privileges.
            dangerous = 0x500D0140
            if own or not flags & 8 and mask & dangerous:
                raise OSError('other users can write to --out or replace a path ancestor; choose a private folder')
        fs_name = c.create_unicode_buffer(32)
        check(volume_info(handle, None, 0, None, None, None, fs_name, len(fs_name)))
        if fs_name.value.upper() != 'NTFS':
            raise OSError('Windows run folders currently require local NTFS')
        return info.volume, info.index_hi, info.index_lo
    finally:
        for ptr in trusted:
            free(ptr)
        free(descriptor)


class FolderLock:
    def __init__(self, handles):
        self.handles = handles

    def close(self):
        handles, self.handles = self.handles, []
        for handle in reversed(handles):
            close(handle)


def lock_folder(value):
    path = local_path(value)
    handles = []
    try:
        for part in [*reversed(path.parents), path]:
            own = part == path
            # FILE_ADD_FILE makes a second writer's open conflict. No delete
            # sharing keeps every path component fixed for the server lifetime.
            desired = 0x20081 | (2 if own else 0)
            handle = open_file(str(part), desired, 1 if own else 3, None, 3,
                               0x02200000, None)
            if handle == INVALID:
                code = c.get_last_error()
                if code == 32:
                    raise OSError('another headgasket server is using this folder, or a path is open for replacement')
                raise c.WinError(code)
            handles.append(handle)
            inspect(handle, own=own)
        return FolderLock(handles)
    except BaseException:
        FolderLock(handles).close()
        raise


def create_run_directory(value):
    """Validate and pin ancestors before creating any missing directory below them."""
    path = local_path(value)
    handles = []
    try:
        for part in reversed(path.parents):
            if not part.exists():
                try:
                    private_mkdir(part)
                except FileExistsError:
                    pass
            handle = open_file(str(part), 0x20081, 3, None, 3, 0x02200000, None)
            if handle == INVALID:
                raise c.WinError(c.get_last_error())
            handles.append(handle)
            inspect(handle)
        try:
            private_mkdir(path)
            return True
        except FileExistsError:
            return False
    finally:
        FolderLock(handles).close()
