"""Run every test in a fresh process: ``python tests/run_all.py [path/to/python-or-blender]``."""

import subprocess
import sys
from pathlib import Path

here = Path(__file__).resolve().parent
runner = sys.argv[1] if len(sys.argv) > 1 else sys.executable
failed = 0
for test in sorted(here.glob("test_*.py")):
    command = [runner, "--background", "--factory-startup", "--python", str(test)] if "blender" in Path(runner).name.lower() else [runner, str(test)]
    result = subprocess.run(command, capture_output=True, text=True)
    passed = result.returncode == 0 and ": PASS" in result.stdout
    print(f"{'PASS' if passed else 'FAIL'}  {test.name}")
    if not passed:
        failed += 1
        print(result.stdout[-2000:], result.stderr[-2000:])
sys.exit(1 if failed else 0)
