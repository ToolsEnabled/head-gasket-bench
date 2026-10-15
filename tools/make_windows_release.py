"""Deterministic native ZIP from committed HEAD plus the pinned PSF runtime.

Builds only. Never tags, pushes, registers clients or publishes a release.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path
import subprocess
import zipfile

PIN = '38b265fc0612027a126ae54d2485101f041b61893e41ef4f421dee6ac618a99e'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--python-archive', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if subprocess.check_output(['git', 'status', '--porcelain'], cwd=root).strip():
        raise SystemExit('Commit the candidate before packaging; working tree is dirty.')
    archive = Path(args.python_archive).read_bytes()
    if hashlib.sha256(archive).hexdigest() != PIN:
        raise SystemExit('CPython 3.12.3 embeddable archive hash mismatch')
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()
    source = subprocess.check_output(['git', 'archive', '--format=zip', 'HEAD'], cwd=root)
    files = {}
    with zipfile.ZipFile(io.BytesIO(source)) as z:
        for entry in z.infolist():
            if not entry.is_dir():
                files[entry.filename] = z.read(entry)
    with zipfile.ZipFile(io.BytesIO(archive)) as z:
        for entry in z.infolist():
            if not entry.is_dir():
                files['python/' + entry.filename] = z.read(entry)
    # Git uses the host interpreter on Linux. The native Windows distribution
    # has its own pinned interpreter and a documented plugin-root launch path.
    plugin_path = '.codex-plugin/plugin.json'
    plugin_source = files[plugin_path]
    plugin = json.loads(plugin_source)
    entry = plugin['mcpServers']['headgasket']
    if (entry['command'] != 'python3' or entry['args'] != ['./tools/codex-mcp.py']
            or entry['cwd'] != './'):
        raise SystemExit('Review changed Codex source entry before deriving the Windows manifest')
    entry.update(command='${PLUGIN_ROOT}/python/python.exe',
                 args=['-B', '${PLUGIN_ROOT}/tools/codex-mcp.py'], cwd='${PLUGIN_ROOT}')
    files[plugin_path] = (json.dumps(plugin, indent=2) + '\n').encode('utf-8')
    manifest = {'schema': 'headgasket/windows-payload/v1', 'version': '0.1.4',
                'sourceCommit': commit, 'pythonArchiveSha256': PIN,
                'derivedFiles': [{'path': plugin_path,
                                  'sourceSha256': hashlib.sha256(plugin_source).hexdigest(),
                                  'reason': 'Windows Codex stdio uses bundled CPython via PLUGIN_ROOT'}],
                'files': [{'path': name, 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
                          for name, raw in sorted(files.items())]}
    files['WINDOWS-MANIFEST.json'] = (json.dumps(manifest, indent=2) + '\n').encode()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('xb') as stream, zipfile.ZipFile(stream, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for name, raw in sorted(files.items()):
            entry = zipfile.ZipInfo(name, date_time=(2024, 4, 9, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.external_attr = 0o100644 << 16
            z.writestr(entry, raw)
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_suffix(output.suffix + '.sha256').write_text(f'{digest}  {output.name}\n')
    print(json.dumps({'sourceCommit': commit, 'file': str(output), 'bytes': output.stat().st_size, 'sha256': digest}))


if __name__ == '__main__':
    main()
