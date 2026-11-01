"""Offline source-checkout checks. Does not claim corpus or semantic review."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

from novel_workflow import POLICY_SHA256, policy
from translation_knowledge import load_current

ROOT = Path(__file__).resolve().parents[1]
SUITES = [('extractor', 'test_core.py'), ('extractor', 'test_configuration.py'),
          ('extractor', 'test_novel_intake.py'), ('tools', 'test_novel_workflow.py')]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    policy(ROOT)
    records = load_current(ROOT)
    names = json.loads((ROOT / 'translations/ko/names.json').read_bytes())
    if not isinstance(names, dict) or any(not isinstance(k, str) or not k or not isinstance(v, str) or not v for k, v in names.items()):
        raise ValueError('Invalid current Names')
    results = []
    for directory, pattern in SUITES:
        result = subprocess.run([sys.executable, '-X', 'utf8', '-m', 'unittest', 'discover', '-s', directory,
                                 '-p', pattern, '-v'], cwd=ROOT)
        results.append({'directory': directory, 'pattern': pattern, 'exit_code': result.returncode})
        if result.returncode:
            break
    report = {'status': 'PASSED' if all(r['exit_code'] == 0 for r in results) else 'FAILED',
              'policy_sha256': POLICY_SHA256, 'suites': results, 'knowledge_records': len(records),
              'names': len(names), 'corpus_verification': 'NOT_RUN', 'semantic_review': 'NOT_RUN',
              'game_integration': 'NOT_RUN', 'network': 'NOT_RUN'}
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report['status'] == 'PASSED' else 1


if __name__ == '__main__':
    raise SystemExit(main())
