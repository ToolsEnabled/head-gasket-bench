#!/usr/bin/env python3
"""Command-line front end for the Head Gasket Job checkpoint scorer.

    python3 hgj_scorer.py score RUN.json [--checkpoint-revision R] [--json OUT] [--markdown OUT]
    python3 hgj_scorer.py compare RUN.json [--checkpoint-revision R]
    python3 hgj_scorer.py verify-family --delivery DIR --inventory-sha256 HEX
                                         --source-root DIR --out DIR [--checkpoint-revision R]

`score` evaluates one saved run record against the reference embedded in its
configuration and prints the twelve checkpoints, points out of 18, S_full,
S_partial, the technician-time estimate and the typed mistakes, followed by a
field-by-field comparison with the score the environment embedded in the
record. `compare` prints only that comparison in detail. `verify-family`
receives a complete thirteen-case scripted family delivery. Nothing here runs
the environment, a model or a physical simulation, and nothing reads the
network.
"""
import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from job_accuracy import checkpoints  # noqa: E402
from job_accuracy.checkpoint_contracts import ORIGINAL, AMENDMENT1, AMENDMENT2  # noqa: E402
from job_accuracy.independent import AssessmentInputError, encoded  # noqa: E402
from job_accuracy.report import run_report, summary  # noqa: E402

REVISIONS = (ORIGINAL, AMENDMENT1, AMENDMENT2)
# The sealed scorer epoch with the CP02 revision of 2026-10-14 (PROVENANCE.md, PINS.json).
SCORER_REVISION = 'refit-preparation-20261010+cp02-20261014'
TIME_LABEL = 'analyst estimates, not measured technician time or a published labour standard'


def load_record(path):
    record = json.loads(Path(path).read_bytes())
    if not isinstance(record, dict) or 'config' not in record or 'actions' not in record:
        raise SystemExit('not a saved run record: ' + str(path))
    return record


def assess(record, revision, terminal_reason):
    settings = record['config']['repair_scoring']
    if terminal_reason is None:
        terminal_reason = 'finished' if record.get('finished') is True else 'partial_record'
    return checkpoints.score(record, settings['reference'], settings['human_time_policy'],
                             terminal_reason=terminal_reason, checkpoint_revision=revision)


def number(value, suffix=''):
    return 'unknown' if not isinstance(value, (int, float)) else f'{value:g}{suffix}'


def print_score(assessment, revision, path):
    primary = assessment['primary_score']
    print('Head Gasket Job: independent checkpoint score')
    print('scorer revision: ' + SCORER_REVISION)
    print('record: ' + str(path))
    print('checkpoint revision: ' + revision)
    print('status: ' + assessment['status'] + '; terminal reason: ' + str(assessment['completion'].get('terminal_reason')))
    print()
    print('  id    w  result  not met')
    for row in primary['checkpoints']:
        print(f"  {row['id']}  {row['weight']}  {'PASS' if row['passed'] else 'FAIL'}    {', '.join(row['not_met']) or '-'}")
        print('             ' + row['title'])
    print()
    print(f"points: {primary['points_earned']}/{primary['total_points']}   S_full: {primary['S_full']}   S_partial: {primary['S_partial']:.6g}")
    h = assessment['human_time']
    print(f"technician seconds ({TIME_LABEL}): productive {number(h['productive_seconds'])}, "
          f"penalty {number(h['penalty_seconds'])}, total {number(h['total_seconds'])}; "
          f"correct reference {number(h['reference_seconds'])}")
    m = assessment['mistakes']
    print('mistakes: ' + (', '.join(f'{k}={v}' for k, v in sorted(m['by_type'].items())) or 'none') + f" (events: {m['count']})")
    calls = assessment['tool_calls']
    print(f"tool calls: {calls['attempted']} attempted, {calls['successful']} successful, {calls['refused']} refused")
    print()
    print_comparison(assessment, brief=True)


def print_comparison(assessment, brief=False):
    c = assessment['primary_comparison']
    print('comparison with the score embedded in the record (primary checkpoints): ' + c['status'])
    if c['status'] in ('unavailable', 'invalid_comparison_input'):
        print('  reason: ' + c['reason'])
    for d in c.get('disagreements', []):
        print(f"  {d['field']}: independent {d['independent']} vs embedded {d['producer']}")
    if not brief:
        for d in c.get('evidence_differences', []):
            print(f"  evidence {d['field']}: independent {d['independent']} vs embedded {d['producer']}")
    s = assessment.get('producer_comparison', {})
    print('comparison of shared secondary fields (bolts, mistakes, time): ' + str(s.get('status')))
    for d in s.get('disagreements', []):
        print(f"  {d.get('field')}: independent {d.get('independent')} vs embedded {d.get('producer')}")
    if not brief:
        for key in ('independent_only_items', 'producer_only_items'):
            if key in s:
                print(f"  {key}: {len(s[key])}")


def cmd_score(a):
    record = load_record(a.record)
    try:
        assessment = assess(record, a.checkpoint_revision, a.terminal_reason)
    except AssessmentInputError as error:
        print('refused: ' + error.code, file=sys.stderr)
        return 2
    print_score(assessment, a.checkpoint_revision, a.record)
    report = run_report(assessment)
    if a.json:
        Path(a.json).write_bytes(encoded(report))
    if a.markdown:
        Path(a.markdown).write_text(summary(report))
    return 0


def cmd_compare(a):
    record = load_record(a.record)
    try:
        assessment = assess(record, a.checkpoint_revision, a.terminal_reason)
    except AssessmentInputError as error:
        print('refused: ' + error.code, file=sys.stderr)
        return 2
    print('scorer revision: ' + SCORER_REVISION)
    print_comparison(assessment)
    agree = assessment['primary_comparison']['status'] == 'agreement'
    return 0 if agree else 1


def cmd_verify_family(a):
    os.chdir(ROOT)
    from tools import receive_current_variants as reader
    try:
        reader.main(Path(a.delivery).resolve(), a.inventory_sha256, Path(a.source_root).resolve(),
                    Path(a.out).resolve(), checkpoint_revision=a.checkpoint_revision)
    except AssessmentInputError as error:
        print('refused: ' + error.code, file=sys.stderr)
        return 2
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest='command', required=True)
    for name, fn in (('score', cmd_score), ('compare', cmd_compare)):
        q = sub.add_parser(name)
        q.add_argument('record')
        q.add_argument('--checkpoint-revision', choices=REVISIONS, default=AMENDMENT2)
        q.add_argument('--terminal-reason', default=None,
                       help="label for how the record ended; default 'finished' or 'partial_record'")
        if name == 'score':
            q.add_argument('--json', help='write the full run report (JSON)')
            q.add_argument('--markdown', help='write the professional summary (Markdown)')
        q.set_defaults(fn=fn)
    q = sub.add_parser('verify-family')
    q.add_argument('--delivery', required=True)
    q.add_argument('--inventory-sha256', required=True)
    q.add_argument('--source-root', required=True)
    q.add_argument('--out', required=True)
    q.add_argument('--checkpoint-revision', choices=REVISIONS, default=AMENDMENT2)
    q.set_defaults(fn=cmd_verify_family)
    a = p.parse_args(argv)
    return a.fn(a)


if __name__ == '__main__':
    sys.exit(main())
