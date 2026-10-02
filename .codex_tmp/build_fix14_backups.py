from pathlib import Path
from datetime import datetime
from zipfile import ZipFile, ZIP_DEFLATED
import subprocess
import hashlib
import json

root = Path('D:/QLHD').resolve()
def git_paths(*args):
    result = subprocess.check_output(['git', *args, '-z'], cwd=root)
    return [entry.decode('utf-8') for entry in result.split(b'\0') if entry]

changed = git_paths('diff', '--name-only', 'HEAD')
assert len(set(changed)) == len(changed) == 17, changed
assert 'CLAUDE.md' not in changed

def allowed(name):
    path = Path(name)
    if any(part in {'venv', '.codex_tmp', 'backups', 'logs', '__pycache__'} or part.startswith('~$') for part in path.parts):
        return False
    if name == '.env' or path.suffix.lower() in {'.db', '.sqlite', '.sqlite3', '.log', '.zip', '.pyc'}:
        return False
    if name.startswith('quanly/document_templates/'):
        return path.suffix.lower() in {'.docx', '.xlsx'}
    if name.startswith('quanly/nhatkycanthiep_phuchoi/'):
        return False  # Source workbooks may contain historical real data.
    if name.startswith('_qa/'):
        return path.suffix == '.py'  # Keep manual source scripts, exclude generated data.
    if name.startswith(('quanly/', 'qlhd/', 'scripts/')):
        return path.suffix.lower() in {'.py', '.html', '.css', '.js', '.json'}
    if name.startswith('docs/'):
        return path.suffix == '.md'
    if name.startswith(('.agents/', '.cursor/', '.codex/agents/')):
        return path.suffix.lower() in {'.md', '.toml'}
    return name in {'.gitignore', 'AGENTS.md', 'README.md', 'manage.py', 'nhap_dulieu.py', 'requirements.txt', 'qlhd-roadmap.canvas.tsx'}

full = sorted({name for name in git_paths('ls-files') + changed if allowed(name)})
assert all(allowed(name) for name in changed)
stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
out = root / 'backups'
out.mkdir(exist_ok=True)
summary = []
for kind, names in [('review', changed), ('full', full)]:
    target = out / f'QLHD_fix14_{stamp}_{kind}.zip'
    with ZipFile(target, 'w', ZIP_DEFLATED) as archive:
        for name in names:
            source = (root / name).resolve()
            assert source.is_relative_to(root) and source.is_file()
            archive.write(source, name)
        archive.writestr('BACKUP_MANIFEST.txt', '\n'.join(names) + '\n')
    with ZipFile(target) as archive:
        assert archive.testzip() is None
        assert all(allowed(name) for name in archive.namelist() if name != 'BACKUP_MANIFEST.txt')
    summary.append({'path': str(target), 'files': len(names), 'sha256': hashlib.sha256(target.read_bytes()).hexdigest()})
(root / '.codex_tmp/fix14-stage.paths').write_bytes(b'\0'.join(name.encode('utf-8') for name in changed) + b'\0')
(root / '.codex_tmp/fix14_qa/backups.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
print(json.dumps(summary, ensure_ascii=False))
