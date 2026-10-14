"""Replace file-system citation paths inside a saved run record and recommit it.

Saved records cite benchmark documents by the path they had on the machine
that produced them (an absolute path ending in, say, `STUDY-DESIGN-v2.md`).
This tool replaces every such string leaf by the document's base name and then
recomputes the commitments that depend on the configuration: the configuration
hash, the identity hashes of the initial and final states, the state hashes,
the first and last state links of the action journal and the action chain.

The result is a relabelled copy. It is NOT the sealed record any more: its
hashes differ from the delivery inventory on purpose. Scoring values do not
depend on the citation strings, so the relabelled copy scores identically.
"""
import argparse
import json
import re
from pathlib import Path
from job_accuracy.independent import encoded, fingerprint

PREFIXES = re.compile(r'^/(sandbox|home|mnt|tmp)/')


def relabel(value, replaced):
    if isinstance(value, dict):
        return {k: relabel(v, replaced) for k, v in value.items()}
    if isinstance(value, list):
        return [relabel(v, replaced) for v in value]
    if isinstance(value, str) and PREFIXES.match(value):
        replaced[value] = replaced.get(value, 0) + 1
        return value.rsplit('/', 1)[-1]
    return value


def recommit(record):
    config_sha = fingerprint(record['config'])
    record['config_sha256'] = config_sha
    for key in ('initial_state', 'final_state'):
        state = record.get(key)
        if isinstance(state, dict) and isinstance(state.get('identity'), dict):
            state['identity']['config_sha256'] = config_sha
    if 'initial_state' in record:
        record['initial_state_sha256'] = fingerprint(record['initial_state'])
    record['final_state_sha256'] = fingerprint(record['final_state'])
    actions = record['actions']
    if actions:
        if 'initial_state_sha256' in record:
            actions[0]['pre_state_sha256'] = record['initial_state_sha256']
        actions[-1]['post_state_sha256'] = record['final_state_sha256']
    previous = config_sha
    for row in actions:
        row['previous_action_sha256'] = previous
        previous = fingerprint(row)
    return record


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument('record', type=Path)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    replaced = {}
    record = relabel(json.loads(a.record.read_bytes()), replaced)
    recommit(record)
    a.out.write_bytes(encoded(record))
    print(json.dumps({'replaced': replaced, 'config_sha256': record['config_sha256'],
                      'final_state_sha256': record['final_state_sha256']}, indent=1))


if __name__ == '__main__':
    main()
