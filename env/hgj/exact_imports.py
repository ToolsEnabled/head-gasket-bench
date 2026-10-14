"""Import declared adapter sources from verified bytes, with private module state.

This binds executed project dependencies without trusting timestamp bytecode or
another adapter's sys.modules cache. Installed scientific libraries retain their
normal import mechanism. This is a source binder, not a sandbox for trusted code.
"""
import hashlib
import importlib.abc
import importlib.util
import re
import sys
import threading
from contextlib import contextmanager
from pathlib import Path

_LOCK = threading.RLock()


def pinned_bytes(item):
    data = b'' if item.get('namespace') is True else Path(item['path']).read_bytes()
    if hashlib.sha256(data).hexdigest() != item['sha256']:
        raise ValueError('Backend source/dependency hash mismatch')
    return data


class ExactImports(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    def __init__(self, dependencies):
        self.sources = {}
        self.namespaces = set()
        self.modules = {}
        for item in dependencies:
            name = item.get('module_name')
            namespace=item.get('namespace') is True
            if not namespace and Path(item['path']).suffix == '.py' and not name:
                raise ValueError('Python dependency needs explicit module_name')
            if name:
                if not re.fullmatch(r'[A-Za-z_]\w*(\.[A-Za-z_]\w*)*', name) or name in self.sources or name in self.namespaces:
                    raise ValueError('Invalid or repeated dependency module_name')
                if namespace: pinned_bytes(item); self.namespaces.add(name)
                else: self.sources[name] = item
            elif namespace: raise ValueError('Empty namespace needs module_name')
        self.names=set(self.sources)|self.namespaces
        self.roots={name for name in self.names if '.' not in name}
        for name in self.names:
            parent = name.rpartition('.')[0]
            if parent and parent not in self.names:
                raise ValueError('Project package parent must be source-pinned: ' + parent)

    def find_spec(self, fullname, path=None, target=None):
        if fullname in self.namespaces:
            return importlib.util.spec_from_loader(fullname,self,origin='<empty-pinned-namespace>',is_package=True)
        item = self.sources.get(fullname)
        if item is None:
            if self.owns(fullname):
                raise ModuleNotFoundError('Project dependency is not source-pinned: ' + fullname)
            return None
        package = Path(item['path']).name == '__init__.py'
        return importlib.util.spec_from_loader(fullname, self, origin=item['path'], is_package=package)

    def create_module(self, spec):
        return None

    def exec_module(self, module):
        if module.__name__ in self.namespaces:
            module.__path__=[]
            return
        item = self.sources[module.__name__]
        module.__file__ = item['path']
        if Path(item['path']).name == '__init__.py':
            module.__path__ = []
        exec(compile(pinned_bytes(item), item['path'], 'exec'), module.__dict__)

    def owns(self, name):
        return name.partition('.')[0] in self.roots

    @contextmanager
    def active(self):
        with _LOCK:
            # An unlisted cached child must not bypass the source-pinning finder.
            previous = {name: module for name,module in sys.modules.copy().items() if self.owns(name)}
            for name in previous:
                sys.modules.pop(name, None)
            sys.modules.update(self.modules)
            sys.meta_path.insert(0, self)
            try:
                yield
            finally:
                self.modules = {name: sys.modules[name] for name in self.names if name in sys.modules}
                for name in list(sys.modules):
                    if not self.owns(name):
                        continue
                    sys.modules.pop(name, None)
                sys.modules.update(previous)
                sys.meta_path.remove(self)
