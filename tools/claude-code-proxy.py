#!/usr/bin/env python3
"""Pass-through stdio proxy for running Head Gasket Bench under Claude Code.

Claude Code saves an MCP tool result that is larger than the tool's declared result
size to a file and shows the model only a short preview. `look` returns about
200,000 characters, so an agent limited to the job tools never sees the part list.
This proxy starts the environment server unchanged and relays every line both ways
unchanged, except that in the reply to tools/list it adds
_meta["anthropic/maxResultSizeChars"] to each tool, so Claude Code passes results
up to that size to the model inline. The environment still writes its own record.

usage: python3 /ABS/REPO/tools/claude-code-proxy.py [--max-chars N] -- python3 /ABS/REPO/env/bin/headgasket-mcp serve ...
"""
import json, subprocess, sys, threading

def main(argv):
    max_chars = 400000
    if argv and argv[0] == '--max-chars':
        max_chars = int(argv[1]); argv = argv[2:]
    if argv and argv[0] == '--':
        argv = argv[1:]
    if not argv:
        sys.exit(__doc__)
    child = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, bufsize=0)
    list_ids = set()
    lock = threading.Lock()

    def upstream():  # client -> server
        for line in sys.stdin.buffer:
            try:
                msg = json.loads(line)
                if isinstance(msg, dict) and msg.get('method') == 'tools/list' and 'id' in msg:
                    with lock:
                        list_ids.add(json.dumps(msg['id']))
            except ValueError:
                pass
            child.stdin.write(line)
            child.stdin.flush()
        child.stdin.close()

    t = threading.Thread(target=upstream, daemon=True)
    t.start()
    for line in child.stdout:  # server -> client
        out = line
        try:
            msg = json.loads(line)
            key = json.dumps(msg.get('id')) if isinstance(msg, dict) else None
            with lock:
                hit = key in list_ids
                if hit:
                    list_ids.discard(key)
            if hit and isinstance(msg.get('result'), dict) and isinstance(msg['result'].get('tools'), list):
                for tool in msg['result']['tools']:
                    meta = dict(tool.get('_meta') or {})
                    meta['anthropic/maxResultSizeChars'] = max_chars
                    tool['_meta'] = meta
                out = (json.dumps(msg, separators=(',', ':')) + '\n').encode()
        except ValueError:
            pass
        sys.stdout.buffer.write(out)
        sys.stdout.buffer.flush()
    sys.exit(child.wait())

if __name__ == '__main__':
    main(sys.argv[1:])
