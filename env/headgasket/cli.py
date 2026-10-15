"""Command-line entry point for the Head Gasket Job environment.

Every subcommand runs the pinned 18-module ``hgj`` runtime through the
source-bound loader in ``tools/source_server.py``: the loader verifies the
source manifest hash and the hash of every module before a single line of the
environment executes, and the identity it computes is written into every run
record (``hgj/run/v2``). Nothing here talks to a network.

Subcommands::

    serve     run the MCP stdio server for one variant and save the run
    replay    re-derive a saved run.json from its actions and compare bytes
    verify    check a run folder (record, journal, report, finish snapshot, chain)
    validate  check run folders: finished, pinned, exact replay (the repository
              validator, tools/validate_submission.py, adds the scorer and the scans)
    prepare   regenerate one variant configuration from the shipped inputs
    family    regenerate the scripted control family (13 cases, 26 replays)
    pins      print or check the pinned hashes
    tools     print the 18 tool definitions
"""
import argparse
import copy
import datetime
import gzip
import hashlib
import importlib
import io
import json
import os
import sys
from pathlib import Path

try:
    import fcntl
except ImportError:  # not POSIX: the folder lock is skipped
    fcntl = None

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

VERSION = '0.1.3'
VARIANTS = ('V1', 'V2', 'V3', 'V4', 'V5')
SOURCE_MANIFEST = ROOT / 'data' / 'environment-source.json'
PINS_PATH = ROOT / 'configs' / 'PINS.json'
REMOVAL_POLICY = ROOT / 'removal-policy'
MAX_RECORD_BYTES = 64 * 1024 * 1024
MAX_CONFIG_BYTES = 16 * 1024 * 1024
RUN_FILES = ('run.json', 'actions.jsonl', 'report.json', 'finish-record.json')
SUBMISSION_FILES = ('run.json', 'actions.jsonl', 'report.json')
# What a server start that made no tool call can leave in --out: the files the
# pinned server writes before or after a session (also when a client kills it,
# for example after a health check) and their temporary *.tmp copies.
UNUSED_START_FILES = ('run.json', 'actions.jsonl', 'report.json', 'launch.json',
                      'run.json.tmp', 'actions.jsonl.tmp', 'report.json.tmp', 'launch.json.tmp')
SERVE_PYTHON = (3, 12)


class Failure(Exception):
    """A named check failed; the message is printed and the exit status is 1."""


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
                       allow_nan=False) + '\n').encode('utf-8')


def digest(value):
    return sha(canonical(value))


def read_bounded(path, limit):
    path = Path(path)
    if path.suffix == '.gz':
        with gzip.open(path, 'rb') as stream:
            raw = stream.read(limit + 1)
    else:
        if not path.is_file() or path.stat().st_size > limit:
            raise Failure(f'{path}: unavailable or larger than {limit} bytes')
        with path.open('rb') as stream:
            raw = stream.read(limit + 1)
    if len(raw) > limit:
        raise Failure(f'{path}: larger than {limit} bytes')
    return raw


def load_pins():
    pins = json.loads(read_bounded(PINS_PATH, 65536))
    if pins.get('schema') != 'headgasket/pins/v1':
        raise Failure('configs/PINS.json has an unknown schema')
    return pins


def source_pin(pins=None):
    pins = pins or load_pins()
    expected = pins['source_manifest_sha256']
    actual = sha(read_bounded(SOURCE_MANIFEST, 131072))
    if actual != expected:
        raise Failure(f'data/environment-source.json hash {actual} differs from the pin {expected}')
    return expected


def resolve_config(args, pins):
    """Return (path, raw_sha256_pin, variant_label) for --variant or --config."""
    if getattr(args, 'config', None):
        path = Path(args.config)
        pin = getattr(args, 'config_pin', None)
        if pin is None:
            raise Failure('--config requires --config-pin <sha256 of the file>')
        return path, pin, getattr(args, 'variant', None) or 'custom'
    variant = getattr(args, 'variant', None)
    if variant not in pins['configurations']:
        raise Failure('choose --variant ' + '|'.join(sorted(pins['configurations'])) + ' or supply --config/--config-pin')
    item = pins['configurations'][variant]
    return ROOT / item['path'], item['sha256'], variant


def load_config(path, pin):
    raw = read_bounded(path, MAX_CONFIG_BYTES)
    actual = sha(raw)
    if actual != pin:
        raise Failure(f'{path}: hash {actual} differs from the pin {pin}')
    config = json.loads(raw)
    if config.get('schema') != 'hgj/config/v1' or config.get('repair_scoring', {}).get('mode') != 'procedure-accuracy-v1':
        raise Failure(f'{path}: not a procedure-scoring configuration')
    return config, actual


def runtime_for(pins, manifest_sha256=None):
    """The source-bound runtime: the current epoch, or the pinned epoch a record names."""
    from tools.source_server import SourceRuntime
    current = source_pin(pins)
    if manifest_sha256 is None or manifest_sha256 == current:
        return SourceRuntime(ROOT, SOURCE_MANIFEST, current)
    for name, epoch in sorted((pins.get('epochs') or {}).items()):
        if epoch['source_manifest_sha256'] == manifest_sha256:
            root = (ROOT / epoch['root']).resolve()
            if ROOT.resolve() not in root.parents and root != ROOT.resolve():
                raise Failure(f'epoch {name}: root outside the environment')
            return SourceRuntime(root, ROOT / epoch['manifest'], manifest_sha256)
    raise Failure('record was produced by an unknown source manifest: ' + str(manifest_sha256))


def utc_now():
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()


def eprint(*values):
    print(*values, file=sys.stderr, flush=True)


# ----------------------------------------------------------------------------- serve

def interpreter():
    return sys.implementation.name, tuple(sys.version_info[:3])


def require_serving_interpreter():
    """A record names the interpreter that made it, and only CPython 3.12 records can be
    replayed by the published tools and submitted: refuse before any model time is spent."""
    name, version = interpreter()
    if name != 'cpython' or version[:2] != SERVE_PYTHON:
        raise Failure(f'serve needs CPython 3.12, and this is {name} {".".join(map(str, version))}. A record made with '
                      'another interpreter cannot be replayed with the published records or submitted. Start the '
                      'server with python3.12 (check with python3 --version).')


def unused_start(out, entries):
    """True when --out holds only what a start without any tool call leaves behind."""
    names = {entry.name for entry in entries}
    if not names <= set(UNUSED_START_FILES):
        return False
    try:
        if 'actions.jsonl' in names and (out / 'actions.jsonl').stat().st_size != 0:
            return False
        for name, count in (('run.json', lambda v: len(v['actions']) if not v['finished'] else None),
                            ('report.json', lambda v: v['tool_calls']['attempted']),
                            ('launch.json', lambda v: v['actions'])):
            if name in names and count(json.loads(read_bounded(out / name, MAX_RECORD_BYTES))) != 0:
                return False
    except (Failure, OSError, ValueError, KeyError, TypeError):
        return False
    return True


def prepare_out(raw):
    """The --out folder, ready for a new run, and the lock held on it.

    A link is refused. A new folder is created readable only by its owner. An existing
    folder must belong to this user and must not be writable by other users (the pinned
    server writes its files by name, so anyone who can write to the folder could plant a
    link there during the run). It is used only when it is empty or holds nothing but
    what a start without any tool call left behind (a client's health check, a listed or
    restarted server); that is removed first, under the lock, so a folder in use by
    another server is never touched."""
    out = Path(os.path.abspath(raw))
    if out.is_symlink():
        raise Failure(f'{out}: --out is a symbolic link; name a real folder')
    created = False
    if not out.exists():
        out.parent.mkdir(parents=True, exist_ok=True)
        try:
            out.mkdir(mode=0o700)
            created = True
        except FileExistsError:
            pass
    if out.is_symlink() or not out.is_dir():
        raise Failure(f'{out}: --out exists and is not a folder')
    lock = open_folder(out)
    try:
        entries = sorted(out.iterdir())
        for entry in entries:
            if entry.is_symlink() or not entry.is_file():
                raise Failure(f'{out}: holds {entry.name!r}, a link or something other than a regular file; '
                              'choose a new, empty folder')
        if entries and unused_start(out, entries):
            for entry in entries:
                entry.unlink()
            eprint(f'headgasket: {out}: removed what an earlier start without any tool call left behind')
        elif any(entry.name in RUN_FILES for entry in entries):
            raise Failure(f'{out}: already holds a run; choose a new folder')
        elif entries:
            raise Failure(f'{out}: holds other files; choose a new, empty folder')
    except BaseException:
        if lock is not None:
            os.close(lock)
        raise
    return out, created, lock


def open_folder(out):
    """Open --out without following a link, check who may write to it, and hold an
    exclusive lock on it for the life of this server, so a second start (for example a
    client health check during a session) cannot reuse the folder. Returns the open
    descriptor, or None where there are no POSIX file permissions and locks."""
    if os.name != 'posix':
        return None
    flags = os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0) | getattr(os, 'O_NOFOLLOW', 0)
    try:
        handle = os.open(out, flags)
    except OSError as error:
        raise Failure(f'{out}: cannot open --out ({error.strerror}); name a real folder of your own')
    try:
        info = os.fstat(handle)
        if info.st_uid != os.geteuid():
            raise Failure(f'{out}: --out belongs to another user; name a folder of your own (a new path is created '
                          'readable only by you)')
        if info.st_mode & 0o002:
            raise Failure(f'{out}: other users can write to --out, so they could plant links in it while the server '
                          'runs; name a folder only you can write to (a new path is created readable only by you)')
        if fcntl is not None:
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise Failure(f'{out}: another headgasket server is using this folder; choose a new folder')
            except OSError:
                pass  # a file system without locks: serve without one
    except BaseException:
        os.close(handle)
        raise
    return handle


def remove_unused(out, created):
    """After a session without any tool call: leave nothing behind (the record would have
    no action to score and would only block the next start)."""
    entries = sorted(out.iterdir()) if out.is_dir() else []
    if not all(entry.is_file() and not entry.is_symlink() for entry in entries) or not unused_start(out, entries):
        return False
    for entry in entries:
        entry.unlink()
    if created:
        try:
            out.rmdir()
        except OSError:
            pass
    return True


class CallGuard:
    """The client's input as the pinned server reads it, with two kinds of tools/call
    answered here instead. Neither kind reaches the server, so neither is recorded.

    Calls after the attempt budget (0.1.2). The pinned server still records a call made
    after turns_remaining reached 0, and the pinned independent scorer accepts at most
    1,024 attempts, so one such call (a finish, say) made a full-budget run impossible to
    score or submit. Once the game's budget (or its tool-call guard) is spent, a
    well-formed tools/call request gets the refusal the game itself would give
    ({"ok": false, "refusal": "Environment turn budget reached", "turns_remaining": 0}),
    so the record stops at the budget.

    A remove naming a route the part does not have (0.1.3). The pinned game refuses
    such a call, but then its scoring step evaluates the refused call against the
    removal policy and fails on the unknown route; the server answers that call and
    every later one with a JSON-RPC error, so the run cannot go on (the record keeps
    the calls before it). The launcher answers such a call itself, with the part's
    route ids, when route_id is given (not null), the client is initialized (as the
    server requires before it passes a call to the game), and either
      - the part, resolved as the game resolves it (its id or stock label, and the
        removal-policy part it stands for, after a replacement made during the run as
        well), is installed, comes off on its own under the removal policy, and
        route_id is not one of its routes: the game's own refusal
        ("REMOVAL_POLICY_REFUSED: unknown requested route"), or
      - part_id as given (the scoring step reads a refused call's part_id without
        resolving it, so the internal id of a fitted replacement, which the game
        does not know, counts too) is the current body of a removal-policy part,
        route_id is not one of that part's routes, and the pinned scoring step, run
        read-only on the record so far with this call added as a refused attempt,
        fails on it.
    Every other remove reaches the game unchanged, which refuses it itself, if it
    must, and records it as before: a part the game does not know, no route_id, or
    a route that is not the part's but does not stop the run (the part is off, or
    comes off only with its assembly, or stays for the job). The state is only read.

    Every other line, and every line before the budget is spent, is handed on
    unchanged; a line the server will refuse anyway (oversized, not JSON, invalid
    UTF-8) is handed on too. The server answers each request before it reads the next
    line, so the game state read here is current, and a reply written here cannot
    overtake one of the server's."""

    REFUSAL = {'ok': False, 'refusal': 'Environment turn budget reached', 'turns_remaining': 0}

    def __init__(self, stream, game, sink, max_request_bytes):
        self.stream, self.game, self.sink = stream, game, sink
        self.max_request_bytes = max_request_bytes
        self.partial = False  # the last piece handed on was a cut part of an oversized line
        self.answered = 0  # calls after the budget
        self.unknown_routes = 0  # remove calls naming a route the part does not have
        self.initialize_received = self.initialized = False  # the server's session state

    def spent(self):
        budget = self.game.budget()
        limit = self.game.config['factors'].get('tool_call_limit')
        return bool(budget and budget['exhausted']) or (limit is not None and len(self.game.records) >= limit)

    def readline(self, size=-1):
        while True:
            line = self.stream.readline(size)
            continuing = self.partial
            self.partial = bool(line) and not line.endswith('\n') and size is not None and 0 <= size <= len(line)
            if not line or continuing or self.partial:
                return line
            request = self.parse(line)
            reply = self.reply(request)
            if reply is None:
                self.follow(request)
                return line
            self.sink.write(reply)
            self.sink.flush()

    def parse(self, line):
        """The JSON-RPC request the server would read from this line, or None."""
        try:
            if len(line.encode('utf-8')) > self.max_request_bytes:
                return None
            request = json.loads(line)
            canonical(request)
        except (ValueError, TypeError, RecursionError):
            return None
        if not (isinstance(request, dict) and request.get('jsonrpc') == '2.0' and isinstance(request.get('method'), str)):
            return None
        return request

    def follow(self, request):
        """Track the session state as the server does (it passes tools/call to the game
        only after initialize and notifications/initialized)."""
        if request is None:
            return
        if 'id' not in request:
            if request['method'] == 'notifications/initialized' and self.initialize_received:
                self.initialized = True
            return
        params = request.get('params', {})
        if (type(request['id']) in (int, str) and request['method'] == 'initialize'
                and isinstance(params, dict) and isinstance(params.get('protocolVersion'), str)):
            self.initialized, self.initialize_received = False, True

    def reply(self, request):
        """The reply to a tools/call request answered here, or None to hand it on."""
        if not (request is not None and request['method'] == 'tools/call'
                and 'id' in request and type(request['id']) in (int, str)
                and isinstance(request.get('params'), dict) and isinstance(request['params'].get('name'), str)):
            return None
        if self.spent():
            value = self.REFUSAL
            self.answered += 1
        else:
            arguments = request['params'].get('arguments', {})
            try:
                routes = self.undeclared_route(request['params']['name'], arguments) if self.initialized else None
            except Exception:  # never worse than handing the call on, as 0.1.2 did
                routes = None
            if routes is None:
                return None
            value = {'ok': False, 'refusal': (
                f'REMOVAL_POLICY_REFUSED: unknown requested route for part_id {arguments["part_id"]!r}; its routes are '
                + ', '.join(repr(route) for route in routes) + ' (name one as route_id, or leave route_id out)')}
            if self.game.budget() is not None:
                # Nothing was charged: the call never reached the game.
                value['turns_remaining'] = max(0, self.game.config['factors']['turn_budget'] - len(self.game.records))
            self.unknown_routes += 1
        text = canonical(value).decode().strip()
        return canonical({'jsonrpc': '2.0', 'id': request['id'],
                          'result': {'content': [{'type': 'text', 'text': text}], 'isError': True}}).decode()

    def undeclared_route(self, name, arguments):
        """The route ids of the part when this call is a remove that names a route the
        part does not have and would stop the run (see the class); otherwise None."""
        game = self.game
        if (name != 'remove' or not isinstance(arguments, dict) or arguments.get('route_id') is None
                or not isinstance(arguments.get('part_id'), str) or not game.config.get('benchmark_removal')):
            return None
        geometry = importlib.import_module('hgj.benchmark_geometry')
        part, route = arguments['part_id'], arguments['route_id']
        installed = geometry.state_for(game)['installed']

        def routes_of(source):
            return [item['id'] for item in game._removal_rows[source]['routes']]

        # As the game resolves it: the id or stock label, then the policy part it stands for.
        body = game.public_to_body.get(part)
        if body is not None and game.state['parts'][body]['location'] == 'assembly':
            source = geometry.source_id(game, body)
            if (source is not None and game._removal_rows[source]['mode'] == 'individual'
                    and installed.get(source) is True and route not in routes_of(source)):
                return routes_of(source)
        # As the scoring step reads a refused call: part_id as given; the pinned step decides.
        current = {geometry.body(game, source): source for source in game._source_to_body}
        source = current.get(part)
        if source is not None and route not in routes_of(source) and game.procedure_scoring:
            scoring = importlib.import_module('hgj.repair_scoring')
            checkpoints = importlib.import_module('hgj.checkpoints')
            rows = scoring.resolved_actions(game.records, game.state)
            rows.append({'seq': len(game.records) + 1, 'name': 'remove', 'input': copy.deepcopy(arguments),
                         'ok': False, 'result': {'ok': False}})
            try:
                checkpoints.disassembly(game.config, game._repair_initial, rows)
            except ValueError as error:
                if 'unknown requested route' in str(error):
                    return routes_of(source)
        return None


def write_private(path, data):
    """Write a new file without following a link, readable only by its owner."""
    handle = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, 'O_NOFOLLOW', 0), 0o600)
    with os.fdopen(handle, 'wb') as stream:
        stream.write(data)


def cmd_serve(args):
    require_serving_interpreter()
    pins = load_pins()
    path, pin, variant = resolve_config(args, pins)
    config, config_sha = load_config(path, pin)
    runtime = runtime_for(pins)
    out, created, lock = prepare_out(args.out)
    try:
        return serve_in(out, created, variant, path, config, config_sha, runtime)
    finally:
        if lock is not None:
            os.close(lock)


def serve_in(out, created, variant, path, config, config_sha, runtime):
    summary = None
    # Invalid UTF-8 on stdin becomes lone surrogates, which the server answers with a
    # JSON-RPC error (-32602) instead of stopping, whatever the locale. newline='\n'
    # keeps the line splitting of sys.stdin.
    stdin = io.TextIOWrapper(sys.stdin.buffer, encoding='utf-8', errors='surrogateescape', newline='\n')
    try:
        started = utc_now()
        eprint(f'headgasket {VERSION}: serving {variant} ({config_sha[:12]}) -> {out}')
        with runtime.active():
            game = importlib.import_module('hgj.game')
            mcp = importlib.import_module('hgj.mcp')
            identity = runtime.identity
            job = game.Game(config, source_runtime=runtime)
            guard = CallGuard(stdin, job, sys.stdout, mcp.MAX_REQUEST_BYTES)
            summary = mcp.serve(job, guard, sys.stdout, out)
    finally:
        stdin.detach()
        if summary is None or summary['actions'] == 0:
            removed = remove_unused(out, created)
            if summary is not None and removed:
                eprint(f'headgasket: no tool calls, so no run was recorded and nothing was kept in {out}')
    if summary['actions'] == 0:
        return 0
    launch = {'schema': 'headgasket/launch/v1', 'version': VERSION, 'variant': variant,
              'configuration': {'path': str(path.name), 'sha256': config_sha},
              'source_manifest_sha256': identity['source_manifest_sha256'],
              'interpreter': identity['interpreter'], 'started_utc': started, 'ended_utc': utc_now(),
              'actions': summary['actions'], 'finished': summary['finished']}
    write_private(out / 'launch.json', canonical(launch))
    if guard.answered:
        eprint(f'headgasket: the budget was spent; {guard.answered} later tool calls were refused and not recorded')
    if guard.unknown_routes:
        eprint(f'headgasket: {guard.unknown_routes} remove calls named a route the part does not have; they were '
               'refused and not recorded')
    eprint(f'headgasket: {summary["actions"]} actions, finished={summary["finished"]}; record in {out}')
    return 0


# ---------------------------------------------------------------------------- replay

def load_record(path):
    record = json.loads(read_bounded(path, MAX_RECORD_BYTES))
    if record.get('schema') != 'hgj/run/v2':
        raise Failure(f'{path}: schema {record.get("schema")!r} is not hgj/run/v2')
    return record


def check_record_config(record, args, pins):
    """A record must be bound to a pinned configuration unless the caller opts out."""
    config_sha = record.get('config_sha256')
    if digest(record['config']) != config_sha:
        raise Failure('record config_sha256 differs from the embedded configuration')
    known = {item['sha256']: name for name, item in pins['configurations'].items()}
    if getattr(args, 'config', None):
        config, pin = load_config(args.config, args.config_pin)
        if canonical(config) != canonical(record['config']):
            raise Failure('record configuration differs from --config')
        return known.get(config_sha, 'custom')
    if config_sha in known:
        return known[config_sha]
    if getattr(args, 'allow_unlisted_config', False):
        return 'unlisted'
    raise Failure(f'record configuration {config_sha} is not one of the pinned V1-V5 configurations '
                  '(pass --allow-unlisted-config to replay it anyway)')


def replay_record(record, pins):
    source = record.get('environment_source') or {}
    runtime = runtime_for(pins, source.get('source_manifest_sha256'))
    if source.get('source_manifest_sha256') != runtime.identity['source_manifest_sha256']:
        raise Failure('record was produced by a different source manifest: '
                      + str(source.get('source_manifest_sha256')))
    recorded = source.get('interpreter')
    if recorded != runtime.identity['interpreter']:
        raise Failure(f'record was made with interpreter {recorded}; this is {runtime.identity["interpreter"]}. '
                      'A record replays exactly only under the CPython version that made it.')
    with runtime.active():
        game = importlib.import_module('hgj.game')
        try:
            actual = game.replay(record, source_runtime=runtime)
        except ValueError as error:
            raise Failure('replay refused: ' + str(error))
    if canonical(actual) != canonical(record):
        raise Failure('replayed record differs from the saved record')
    return actual


def summarize(record, variant):
    score = record.get('score') or {}
    primary = score.get('primary_score') or {}
    return {'variant': variant, 'variant_id': record['config'].get('variant_id'),
            'run_sha256': digest(record), 'config_sha256': record['config_sha256'],
            'finished': record['finished'], 'scoring_status': record.get('scoring_status'),
            'tool_calls': len(record['actions']),
            'points_earned': primary.get('points_earned'), 'total_points': primary.get('total_points'),
            'S_full': primary.get('S_full'), 'S_partial': primary.get('S_partial'),
            'failed_checkpoints': [row['id'] for row in primary.get('checkpoints', []) if not row['passed']],
            'bolt_accuracy_percent': (score.get('bolt_accuracy') or {}).get('accuracy_percent'),
            'checklist_accuracy_percent': (score.get('checklist_accuracy') or {}).get('accuracy_percent'),
            'mistakes_by_type': (score.get('mistakes') or {}).get('by_type'),
            'human_time': {k: (score.get('human_time') or {}).get(k) for k in
                           ('productive_seconds', 'penalty_seconds', 'total_seconds')}}


def cmd_replay(args):
    pins = load_pins()
    record = load_record(args.record)
    variant = check_record_config(record, args, pins)
    actual = replay_record(record, pins)
    if args.out:
        with open(args.out, 'xb') as stream:
            stream.write(canonical(actual))
    result = {'schema': 'headgasket/replay/v1', 'ok': True, 'exact': True, 'record': str(args.record), **summarize(record, variant)}
    print(json.dumps(result, sort_keys=True), flush=True)
    return 0


# ---------------------------------------------------------------------------- verify

def check_chain(record):
    previous = record['config_sha256']
    for index, row in enumerate(record['actions'], 1):
        if row.get('seq') != index:
            raise Failure(f'action {index}: seq is {row.get("seq")}')
        if row.get('previous_action_sha256') != previous:
            raise Failure(f'action {index}: previous_action_sha256 breaks the chain')
        previous = digest(row)
    return previous


def verify_folder(folder, args, pins):
    folder = Path(folder)
    checks = {}
    record_path = folder / 'run.json'
    if not record_path.is_file():
        raise Failure(f'{folder}: no run.json')
    record = load_record(record_path)
    variant = check_record_config(record, args, pins)
    checks['config_pinned'] = variant
    checks['chain_last_action_sha256'] = check_chain(record)
    checks['final_state_sha256'] = digest(record['final_state']) == record['final_state_sha256']
    checks['score_sha256'] = digest(record['score']) == record['score_sha256']
    if not (checks['final_state_sha256'] and checks['score_sha256']):
        raise Failure('final_state_sha256 or score_sha256 differs from the record')
    journal = folder / 'actions.jsonl'
    if journal.is_file():
        checks['actions_jsonl'] = read_bounded(journal, MAX_RECORD_BYTES) == b''.join(canonical(r) for r in record['actions'])
        if not checks['actions_jsonl']:
            raise Failure('actions.jsonl differs from the record journal')
    else:
        checks['actions_jsonl'] = 'absent'
    report_path = folder / 'report.json'
    if report_path.is_file():
        report = json.loads(read_bounded(report_path, 16 * 1024 * 1024))
        expected = {'schema': 'hgj/repair-run-report/v1', 'run_sha256': digest(record),
                    'score_sha256': record['score_sha256'], 'finished': record['finished'],
                    'attempted': len(record['actions'])}
        actual = {'schema': report.get('schema'), 'run_sha256': report.get('run_sha256'),
                  'score_sha256': report.get('score_sha256'), 'finished': report.get('finished'),
                  'attempted': (report.get('tool_calls') or {}).get('attempted')}
        if actual != expected:
            raise Failure(f'report.json does not describe this record: {actual} != {expected}')
        if (report.get('terminal_reason') == 'finished') != bool(record['finished']):
            raise Failure('report.json terminal_reason disagrees with the record')
        checks['report_json'] = True
        checks['terminal_reason'] = report.get('terminal_reason')
        checks['real_time_seconds'] = (report.get('real_time') or {}).get('seconds')
    else:
        checks['report_json'] = 'absent'
    snapshot = folder / 'finish-record.json'
    if not record['finished']:
        checks['finish_record_json'] = 'not finished'
    elif snapshot.is_file():
        checks['finish_record_json'] = read_bounded(snapshot, MAX_RECORD_BYTES) == canonical(record)
        if not checks['finish_record_json']:
            raise Failure('finish-record.json differs from the finished record')
    else:
        # The published records omit this copy: for a finished run it is the record itself.
        checks['finish_record_json'] = 'absent'
    replay_record(record, pins)
    checks['exact_replay'] = True
    return {'schema': 'headgasket/verify/v1', 'ok': True, 'folder': str(folder), 'checks': checks, **summarize(record, variant)}


def cmd_verify(args):
    pins = load_pins()
    result = verify_folder(args.run, args, pins)
    print(json.dumps(result, sort_keys=True), flush=True)
    return 0


def cmd_validate(args):
    """Repository validator: every case folder must be finished and pinned."""
    pins = load_pins()
    root = Path(args.submission)
    folders = [root] if (root / 'run.json').is_file() else sorted(p for p in root.iterdir() if (p / 'run.json').is_file())
    if not folders:
        raise Failure(f'{root}: no run folders (a run folder holds run.json)')
    rows = []
    for folder in folders:
        for name in SUBMISSION_FILES:
            if not (folder / name).is_file():
                raise Failure(f'{folder}: submission folders need {", ".join(SUBMISSION_FILES)}')
        result = verify_folder(folder, args, pins)
        if not result['finished']:
            raise Failure(f'{folder}: the run did not finish; `headgasket validate` checks finished runs only. '
                          'A run that stopped without finish can still be submitted: check it with '
                          'tools/validate_submission.py from the repository root')
        rows.append(result)
    print(json.dumps({'schema': 'headgasket/validation/v1', 'ok': True, 'cases': rows}, sort_keys=True), flush=True)
    return 0


# --------------------------------------------------------------------------- prepare

def cmd_prepare(args):
    from tools.variant_controls import configuration
    config = configuration(args.variant, with_removal_policy=True,
                           removal_source_dir=args.removal_source or REMOVAL_POLICY)
    raw = canonical(config)
    with open(args.out, 'xb') as stream:
        stream.write(raw)
    print(json.dumps({'variant': args.variant, 'path': args.out, 'sha256': sha(raw), 'bytes': len(raw)}), flush=True)
    return 0


def cmd_family(args):
    from tools.variant_demo import run
    run(args.out, args.removal_source or REMOVAL_POLICY)
    return 0


# ------------------------------------------------------------------------------ pins

def cmd_pins(args):
    pins = load_pins()
    manifest = json.loads(read_bounded(SOURCE_MANIFEST, 131072))
    result = {'source_manifest_sha256': source_pin(pins), 'configurations': pins['configurations'], 'files': {}}
    ok = True
    items = list(manifest['sources'].values()) + [manifest['bootstrap']]
    for item in items:
        actual = sha(read_bounded(ROOT / item['path'], 131072))
        result['files'][item['path']] = {'expected': item['sha256'], 'ok': actual == item['sha256']}
        ok = ok and actual == item['sha256']
    result['epochs'] = {}
    for name, epoch in sorted((pins.get('epochs') or {}).items()):
        root = ROOT / epoch['root']
        raw = read_bounded(ROOT / epoch['manifest'], 131072)
        files = {}
        epoch_ok = sha(raw) == epoch['source_manifest_sha256']
        body = json.loads(raw)
        for item in list(body['sources'].values()) + [body['bootstrap']]:
            match = sha(read_bounded(root / item['path'], 131072)) == item['sha256']
            files[item['path']] = match
            epoch_ok = epoch_ok and match
        result['epochs'][name] = {'source_manifest_sha256': epoch['source_manifest_sha256'], 'ok': epoch_ok,
                                  'files_ok': sum(files.values()), 'files': len(files)}
        ok = ok and epoch_ok
    for name, item in pins['configurations'].items():
        path = ROOT / item['path']
        present = path.is_file()
        match = present and sha(read_bounded(path, MAX_CONFIG_BYTES)) == item['sha256']
        result['configurations'][name] = {**item, 'present': present, 'ok': match}
        if args.check:
            ok = ok and match
    result['ok'] = ok
    print(json.dumps(result, indent=2 if args.pretty else None, sort_keys=True), flush=True)
    return 0 if ok else 1


def cmd_tools(args):
    from hgj.api import DEFINITIONS
    for name, description, schema in DEFINITIONS:
        if args.json:
            print(json.dumps({'name': name, 'description': description, 'inputSchema': schema}))
        else:
            fields = ', '.join(sorted(schema['properties'])) or '-'
            print(f'{name:22s} {description}\n{"":22s} arguments: {fields}')
    return 0


# ------------------------------------------------------------------------------ main

def build_parser():
    parser = argparse.ArgumentParser(prog='headgasket', description=__doc__.split('\n\n')[0])
    parser.add_argument('--version', action='version', version='headgasket ' + VERSION)
    sub = parser.add_subparsers(dest='command', required=True)

    def config_options(p):
        p.add_argument('--variant', choices=VARIANTS, help='one of the five pinned configurations')
        p.add_argument('--config', help='a configuration file instead of --variant')
        p.add_argument('--config-pin', help='sha256 of that file')

    p = sub.add_parser('serve', help='run the MCP stdio server for one variant')
    config_options(p)
    p.add_argument('--out', required=True, help='a new folder, or an empty one of yours that other users cannot write '
                   'to, for run.json, actions.jsonl, report.json, finish-record.json and launch.json (a start without any '
                   'tool call records nothing)')
    p.set_defaults(func=cmd_serve)

    p = sub.add_parser('replay', help='re-derive a run.json and compare it byte for byte')
    p.add_argument('--record', required=True, help='run.json (or run.json.gz)')
    p.add_argument('--out', help='write the replayed record here (must not exist)')
    config_options(p)
    p.add_argument('--allow-unlisted-config', action='store_true', help='replay a record whose configuration is not pinned')
    p.set_defaults(func=cmd_replay)

    p = sub.add_parser('verify', help='check a run folder')
    p.add_argument('--run', required=True, help='folder holding run.json and its companions')
    config_options(p)
    p.add_argument('--allow-unlisted-config', action='store_true')
    p.set_defaults(func=cmd_verify)

    p = sub.add_parser('validate', help='check a submission folder like the repository validator')
    p.add_argument('submission', help='a run folder, or a folder of run folders')
    p.set_defaults(func=cmd_validate, config=None, allow_unlisted_config=False)

    p = sub.add_parser('prepare', help='regenerate one variant configuration')
    p.add_argument('--variant', choices=VARIANTS, required=True)
    p.add_argument('--out', required=True)
    p.add_argument('--removal-source', help='removal-policy directory (default: removal-policy/)')
    p.set_defaults(func=cmd_prepare)

    p = sub.add_parser('family', help='regenerate the scripted control family')
    p.add_argument('--out', required=True, help='new folder')
    p.add_argument('--removal-source')
    p.set_defaults(func=cmd_family)

    p = sub.add_parser('pins', help='print the pinned hashes and check the files')
    p.add_argument('--check', action='store_true', help='fail if a pinned configuration is missing or differs')
    p.add_argument('--pretty', action='store_true')
    p.set_defaults(func=cmd_pins)

    p = sub.add_parser('tools', help='print the 18 tool definitions')
    p.add_argument('--json', action='store_true')
    p.set_defaults(func=cmd_tools)
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except Failure as error:
        eprint('headgasket: ' + str(error))
        return 1
    except BrokenPipeError:
        return 1
