#!/usr/bin/env python3
"""Build leaderboard/board.json from runs/reference, runs/exploratory and runs/submitted.

    python3 tools/build_board.py            # write leaderboard/board.json
    python3 tools/build_board.py --check    # exit 1 if the file is not what the runs give

One row per run, as recorded; nothing is averaged. Rows are sorted by variant, then
S_partial (highest first), then name. The output is deterministic: the same runs give
the same bytes. This reads saved files only; submissions are checked separately by
tools/validate_submission.py (which replays and rescores them).
"""
import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
FIELDS = ('name', 'model_label', 'client', 'variant', 'points', 's_partial', 's_full', 'penalty_s',
          'productive_s', 'date', 'source', 'exploratory')
BY_TOOLSENABLED = 'run by ToolsEnabled'

# The runs ToolsEnabled collected before submissions opened. Labels follow the paper
# (Table 1): the requested model is a label, not an attested identity.
REFERENCE = {'V1-amended': {'model_label': 'scripted reference (no model)', 'client': 'scripted', 'date': '2026-10-10'}}
EXPLORATORY = {
    'gpt-6.1-sol': {'model_label': 'GPT-6.1-Sol', 'client': 'Codex CLI', 'date': '2026-10-10'},
    'gpt-6-astra': {'model_label': 'GPT-6-Astra', 'client': 'Codex CLI', 'date': '2026-10-10'},
    'gpt-6-luna': {'model_label': 'GPT-6-Luna', 'client': 'Codex CLI', 'date': '2026-10-10'},
    # Low-cost baseline, three runs: Claude Code headless with only the 18 job tools, the server started through
    # tools/claude-code-proxy.py so that look's result reaches the model inline (see each RESULT.md).
    'claude-haiku-5-5-proxy-r1': {'model_label': 'claude-haiku-5-5', 'client': 'Claude Code', 'date': '2026-10-14'},
    'claude-haiku-5-5-proxy-r2': {'model_label': 'claude-haiku-5-5', 'client': 'Claude Code', 'date': '2026-10-14'},
    'claude-haiku-5-5-proxy-r3': {'model_label': 'claude-haiku-5-5', 'client': 'Claude Code', 'date': '2026-10-14'},
}


def load(path):
    return json.loads(Path(path).read_bytes())


def row(name, label, client, variant, points, s_partial, s_full, penalty, productive, date, source, exploratory):
    return {'name': name, 'model_label': label, 'client': client, 'variant': variant, 'points': points,
            's_partial': round(float(s_partial), 6), 's_full': s_full, 'penalty_s': penalty,
            'productive_s': productive, 'date': date, 'source': source, 'exploratory': exploratory}


def from_score(score):
    primary = score['primary_score']
    return (primary['points_earned'], primary['S_partial'], primary['S_full'],
            score['human_time']['penalty_seconds'], score['human_time']['productive_seconds'])


def reference_rows(runs):
    rows = []
    for folder in sorted(p for p in (runs / 'reference').iterdir() if p.is_dir()):
        meta = REFERENCE[folder.name]
        record = load(folder / 'run.json')
        rows.append(row('reference/' + folder.name, meta['model_label'], meta['client'], record['config']['variant_id'],
                        *from_score(record['score']), meta['date'], BY_TOOLSENABLED, True))
    return rows


def exploratory_rows(runs):
    rows = []
    for folder in sorted(p for p in (runs / 'exploratory').iterdir() if p.is_dir()):
        meta = EXPLORATORY[folder.name]
        summary = load(folder / 'environment-score.json')
        rows.append(row('exploratory/' + folder.name, meta['model_label'], meta['client'], summary['variant'],
                        summary['points_earned'], summary['S_partial'], summary['S_full'],
                        summary['technician_seconds']['penalty_seconds'],
                        summary['technician_seconds']['productive_seconds'], meta['date'], BY_TOOLSENABLED, True))
    return rows


def submitted_rows(runs):
    rows = []
    root = runs / 'submitted'
    if not root.is_dir():
        return rows
    for folder in sorted(p for p in root.iterdir() if p.is_dir()):
        declaration = load(folder / 'SUBMISSION.json')
        record = load(folder / 'run.json')
        rows.append(row('submitted/' + folder.name, declaration['model_label'], declaration['client'], record['config']['variant_id'],
                        *from_score(record['score']), declaration['date'],
                        'submitted by ' + declaration['submitter'], False))
    return rows


def build(runs):
    rows = reference_rows(runs) + exploratory_rows(runs) + submitted_rows(runs)
    for item in rows:
        assert tuple(item) == FIELDS
    rows.sort(key=lambda r: (r['variant'], -r['s_partial'], r['name']))
    board = {'schema': 'head-gasket-bench/board/v1',
             'note': ('One row per run, as recorded; nothing is averaged. Exploratory rows are single runs by ToolsEnabled '
                      'that describe behaviour and do not rank models. Model labels are stated, not attested. Technician '
                      'seconds are analyst estimates. ToolsEnabled is not affiliated with or endorsed by Anthropic, OpenAI '
                      'or any other AI provider.'),
             'fields': list(FIELDS), 'rows': rows}
    return (json.dumps(board, indent=2, ensure_ascii=False) + '\n').encode('utf-8')


def main(argv=None):
    parser = argparse.ArgumentParser(description='Build leaderboard/board.json from the runs tree.')
    parser.add_argument('--runs', default=str(REPO / 'runs'))
    parser.add_argument('--out', default=str(REPO / 'leaderboard' / 'board.json'))
    parser.add_argument('--check', action='store_true', help='compare with the existing file instead of writing it')
    args = parser.parse_args(argv)
    data = build(Path(args.runs))
    out = Path(args.out)
    if args.check:
        if not out.is_file() or out.read_bytes() != data:
            print(f'FAIL {out} is not up to date; run python3 tools/build_board.py and commit the result')
            return 1
        print(f'OK {out} is up to date ({len(json.loads(data)["rows"])} rows)')
        return 0
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(data)
    print(f'WROTE {out} ({len(json.loads(data)["rows"])} rows)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
