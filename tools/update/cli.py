"""Shared operator entry point, following the gctrans command layout."""
import argparse
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))


def main(arguments=None):
    args = list(sys.argv[1:] if arguments is None else arguments)
    if not args or args[0] in {'-h', '--help'}:
        print('Usage: python tools/update/cli.py {novel|intake|ui-intake|ui|manifests|crawl|inventory|extract|classify|verify-extraction|preflight|mod-package} ...')
        print('Novel: init, prepare, checkpoint, review, check, apply, status, verify, recover')
        print('UI: check, apply, verify, status; manifests --check verifies public descriptors')
        print('Use novel <action> --help for authoring options; --repo selects the workspace.')
        return 0
    command, *rest = args
    if command == 'novel':
        import novel_workflow
        parser = argparse.ArgumentParser(add_help=False)
        parser.add_argument('--repo', type=Path, default=ROOT)
        known, forwarded = parser.parse_known_args(rest)
        return novel_workflow.main(['--root', str(known.repo.resolve()), *forwarded])
    scripts = {'intake': ('extractor/novel_intake.py', []), 'crawl': ('extractor/crawl.py', []),
               'inventory': ('extractor/run.py', ['inventory']), 'extract': ('extractor/run.py', ['extract']),
               'classify': ('extractor/classify_output.py', []), 'verify-extraction': ('extractor/verify.py', []),
               'preflight': ('tools/preflight.py', []), 'mod-package': ('tools/mod_package.py', []),
               'ui-intake': ('tools/ui_intake.py', []), 'ui': ('tools/ui_workflow.py', []),
               'manifests': ('tools/build_manifests.py', [])}
    if command not in scripts:
        raise SystemExit('Unknown command: ' + command)
    script, fixed = scripts[command]
    return subprocess.run([sys.executable, '-X', 'utf8', str(ROOT / script), *fixed, *rest], cwd=ROOT).returncode


if __name__ == '__main__':
    raise SystemExit(main())
