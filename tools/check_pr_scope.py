#!/usr/bin/env python3
"""Check what a pull request changes, and list its submissions.

    python3 tools/check_pr_scope.py --base BASE_REV --head HEAD_REV [--github-output FILE]

Run from a git checkout that holds both revisions. The pull-request check
(.github/workflows/validate.yml) runs this file from the base branch on every pull
request; it reads the pull request's commits with git only (git merge-base, git
merge-tree, git diff --raw, git cat-file) and executes nothing from them.

What is checked is what merging the pull request would change on the base branch:
git merge-tree computes the merge result, and that tree is compared with the base
revision. (A diff against one merge base can hide changes: in a criss-cross history,
with two merge bases, a pull request can delete an accepted submission while the diff
against either base shows only its new folder.) Refused, each with an error line:

  * a history with more than one merge base with the base branch, or none (rebase
    the pull request on the current base branch);
  * a pull request that does not merge cleanly;

and, for a pull request that changes anything under runs/ or leaderboard/ (a
submission pull request), which may only add new folders runs/submitted/<name>/ of
regular files and change leaderboard/board.json:

  * any other changed path (code, docs, published records, runs/submitted/<file>);
  * a folder name the validator would refuse (spaces and newlines included; git's
    NUL-separated output is used, so no name is split or hidden);
  * a link, a submodule or a nested folder inside a submission;
  * a change to, or the removal of, a submission that is already on the base branch
    (that is for a maintainer to review, not for this check);
  * more than MAX_SUBMISSIONS new submissions in one pull request.

A pull request that changes nothing under runs/ or leaderboard/ is a code change: it
passes this check (kind=code) and is reviewed by a maintainer.

Writes kind=submission|code, matrix={"include": [{"name": ..., "python": "3.12.x"}, ...]}
and any=true|false to FILE (the job outputs) and exits 0, or prints the errors and
exits 1.
"""
import argparse
import json
import re
import subprocess
import sys

NAME_RE = re.compile(r'[a-z0-9][a-z0-9._-]{2,99}')  # the validator's folder-name rule
BOARD = 'leaderboard/board.json'
FILE_MODES = ('100644', '100755')
DEFAULT_PYTHON = '3.12.3'
MAX_RUN_BYTES = 64 * 1024 * 1024
# Each submission starts a validator job of up to 90 minutes; this caps what one pull
# request can queue. Larger batches go in several pull requests.
MAX_SUBMISSIONS = 10
SUBMISSION_AREAS = ('runs/', 'leaderboard/')


def git(*args):
    return subprocess.run(['git', *args], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True).stdout


class Refused(Exception):
    """The pull request cannot be checked as it stands; the message says why."""


def merge_result(base, head):
    """The tree that merging head into base gives, or Refused."""
    found = subprocess.run(['git', 'merge-base', '--all', base, head], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           check=False)
    if found.returncode not in (0, 1):  # 1: no common ancestor
        raise subprocess.CalledProcessError(found.returncode, 'git merge-base', found.stdout, found.stderr)
    bases = found.stdout.decode().split()
    if len(bases) != 1:
        raise Refused(f'the pull request has {len(bases)} merge bases with the base branch (a criss-cross or '
                      'unrelated history), so what it changes is ambiguous; rebase it on the current base branch')
    done = subprocess.run(['git', 'merge-tree', '--write-tree', '--no-messages', base, head],
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if done.returncode == 1:
        raise Refused('the pull request does not merge cleanly into the base branch; rebase it on the current '
                      'base branch and rebuild leaderboard/board.json')
    if done.returncode != 0:
        raise subprocess.CalledProcessError(done.returncode, 'git merge-tree', done.stdout, done.stderr)
    return done.stdout.decode().split()[0]


def changes(base, head):
    """(status, new mode, path) for every path that merging the pull request would change on base."""
    tree = merge_result(base, head)
    fields = git('diff', '--raw', '-z', '--no-renames', '--no-abbrev', base, tree).split(b'\0')
    rows = []
    for meta, path in zip(fields[0::2], fields[1::2]):
        if not meta:
            continue
        _old_mode, new_mode, _old, _new, status = meta.decode().lstrip(':').split(' ')
        rows.append((status[0], new_mode, path.decode('utf-8', 'surrogateescape')))
    return rows


def exists(rev, path):
    return subprocess.run(['git', 'cat-file', '-e', f'{rev}:{path}'], stdout=subprocess.DEVNULL,
                          stderr=subprocess.DEVNULL).returncode == 0


def python_version(head, name):
    """The CPython 3.12 version the record names; the validator reports any other problem."""
    path = f'{head}:runs/submitted/{name}/run.json'
    try:
        if int(git('cat-file', '-s', path)) > MAX_RUN_BYTES:
            return DEFAULT_PYTHON
        found = json.loads(git('cat-file', 'blob', path))['environment_source']['interpreter']['version']
        if isinstance(found, list) and len(found) == 3 and found[:2] == [3, 12] and all(type(v) is int for v in found):
            return '.'.join(map(str, found))
    except Exception:
        pass
    return DEFAULT_PYTHON


def check(base, head):
    """(errors, kind, matrix) for the pull request."""
    try:
        rows = changes(base, head)
    except Refused as refused:
        return [str(refused)], 'submission', []
    if not any(path.startswith(SUBMISSION_AREAS) for _status, _mode, path in rows):
        return [], 'code', []
    errors, names = [], set()
    for status, mode, path in rows:
        if path == BOARD:
            if status == 'D' or mode not in FILE_MODES:
                errors.append(f'{BOARD} must stay a regular file')
            continue
        parts = path.split('/')
        if path.startswith('runs/submitted/'):
            if len(parts) != 4 or not parts[3]:
                errors.append(f'{path!r}: a submission is one folder runs/submitted/<name>/ holding its files')
                continue
            if not NAME_RE.fullmatch(parts[2]):
                errors.append(f'{path!r}: the folder name must be 3-100 characters: a-z, 0-9, ".", "_" or "-", '
                              'starting with a letter or digit')
                continue
            if status == 'D':
                errors.append(f'{path!r}: removes a file of a submission')
            elif mode not in FILE_MODES:
                errors.append(f'{path!r}: is a link or a submodule, not a regular file')
            names.add(parts[2])
            continue
        errors.append(f'{path!r}: outside runs/submitted/<name>/ and {BOARD}')
    for name in sorted(names):
        if exists(base, f'runs/submitted/{name}'):
            errors.append(f'runs/submitted/{name}/ is already on the base branch; changing or removing a submission '
                          'is reviewed by a maintainer, not by this check')
    if len(names) > MAX_SUBMISSIONS:
        errors.append(f'the pull request adds {len(names)} submissions; at most {MAX_SUBMISSIONS} per pull request '
                      '(open several pull requests)')
    matrix = [{'name': name, 'python': python_version(head, name)} for name in sorted(names)]
    return errors, 'submission', matrix


def main(argv=None):
    parser = argparse.ArgumentParser(description='Check the scope of a pull request.')
    parser.add_argument('--base', required=True, help='the base branch revision (trusted)')
    parser.add_argument('--head', required=True, help="the pull request's head revision")
    parser.add_argument('--github-output', help='append kind=, matrix= and any= to this file')
    args = parser.parse_args(argv)
    errors, kind, matrix = check(args.base, args.head)
    if errors:
        print('::error::A submission pull request may only add new folders runs/submitted/<name>/ and change '
              f'{BOARD}. Anything else is a code change and is reviewed as one.')
        for line in errors:
            print('::error::' + line)
        return 1
    if kind == 'code':
        print('Not a submission pull request: nothing under runs/ or leaderboard/ changes. A maintainer reviews it '
              'as a code change.')
    lines = (f'kind={kind}\n' + 'matrix=' + json.dumps({'include': matrix}) + '\n'
             + 'any=' + ('true' if matrix else 'false') + '\n')
    if args.github_output:
        with open(args.github_output, 'a') as out:
            out.write(lines)
    print(lines, end='')
    return 0


if __name__ == '__main__':
    sys.exit(main())
