"""Measured usage envelope separate from deterministic procedure replay."""
import copy
import math
from .codec import digest


def require(condition, message):
    if not condition:
        raise ValueError(message)


def report_for_run(record, wall_time_seconds, *, tokens=None,
                   time_source='MCP server session monotonic clock',
                   token_source='Not supplied by a provider usage receipt', terminal_reason=None):
    """Join measured usage to one exact run without guessing token counts."""
    require(type(wall_time_seconds) in (int, float) and math.isfinite(wall_time_seconds)
            and wall_time_seconds >= 0, 'Measured wall time must be finite and nonnegative')
    require(type(time_source) is str and bool(time_source.strip())
            and type(token_source) is str and bool(token_source.strip()), 'Usage sources must be named')
    if tokens is not None:
        require(type(tokens) is dict and set(tokens) == {'input', 'output'}
                and all(type(value) is int and value >= 0 for value in tokens.values()),
                'Token usage must contain measured nonnegative integer input and output counts')
    score = record.get('score')
    require(type(score) is dict and score.get('schema') == 'hgj/repair-score/v1'
            and record.get('score_sha256') == digest(score), 'Procedure report requires a committed accuracy score')
    actions = record.get('actions')
    require(type(actions) is list and all(type(row) is dict and type(row.get('result')) is dict
            and type(row['result'].get('ok')) is bool for row in actions),
            'Action outcomes must be strict booleans')
    successful = sum(row['result']['ok'] for row in actions)
    refused = sum(not row['result']['ok'] for row in actions)
    require(type(score.get('tool_calls')) is int and score['tool_calls'] == len(actions)
            and len(actions) == successful + refused, 'Reported tool calls differ from the action journal')
    finished = record.get('finished')
    finish_witness = any(row.get('name') == 'finish' and row['result']['ok'] for row in actions)
    require(type(finished) is bool and finished == finish_witness
            and score.get('status') == ('scored' if finished else 'in_progress'),
            'Finished status requires a successful finish action')
    if terminal_reason is None:
        terminal_reason = 'finished' if finished else 'input_ended_without_finish'
    require(terminal_reason in ('finished', 'budget_exhausted', 'tool_call_limit',
            'input_ended_without_finish', 'interrupted', 'transport_error', 'running')
            and (terminal_reason == 'finished') == finished,
            'Terminal reason differs from committed completion status')
    return {
        'schema': 'hgj/repair-run-report/v1', 'run_sha256': digest(record),
        'score_sha256': digest(score),
        'finished': finished,
        'status': 'in_progress' if terminal_reason == 'running' else 'finished' if finished else 'incomplete',
        'terminal_reason': None if terminal_reason == 'running' else terminal_reason,
        'real_time': {'seconds': wall_time_seconds, 'source': time_source},
        'tokens': {'input': None if tokens is None else tokens['input'],
                   'output': None if tokens is None else tokens['output'],
                   'total': None if tokens is None else sum(tokens.values()),
                   'status': 'not_recorded' if tokens is None else 'recorded',
                   'source': token_source},
        'tool_calls': {'attempted': len(actions),
                       'successful': successful, 'refused': refused},
        'human_time': copy.deepcopy(score['human_time']),
        'mistakes': copy.deepcopy(score['mistakes']),
        'bolt_accuracy': copy.deepcopy(score['bolt_accuracy']),
        'checklist_accuracy': copy.deepcopy(score['checklist_accuracy']),
        'coverage': copy.deepcopy(score['coverage']),
        'reference_sha256': score['reference_sha256'],
        'primary_score': copy.deepcopy(score.get('primary_score')),
    }
