"""
Test Suite Failure Triage & Categorizer
Runs pytest file-by-file and classifies every single failure.
"""

import os
import sys
import subprocess
import json

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

test_files = [
    f for f in sorted(os.listdir(os.path.join(BASE_DIR, "tests")))
    if f.startswith("test_") and f.endswith(".py")
]

results = []

for tf in test_files:
    cmd = [sys.executable, "-m", "pytest", f"tests/{tf}", "-q", "--tb=line"]
    res = subprocess.run(cmd, cwd=BASE_DIR, capture_output=True, text=True)
    out = res.stdout + "\n" + res.stderr
    passed = 0
    failed = 0
    skipped = 0
    errors = 0
    lines = out.strip().split("\n")
    last_line = lines[-1] if lines else ""
    fail_lines = [l for l in lines if "FAILED " in l or "ERROR " in l]

    results.append({
        "file": tf,
        "exit_code": res.returncode,
        "summary": last_line,
        "failures": fail_lines
    })
    print(f"[{'PASS' if res.returncode == 0 else 'FAIL'}] {tf:<45} | {last_line}")

with open(os.path.join(BASE_DIR, "ml", "evaluation", "test_failure_triage.json"), "w") as f:
    json.dump(results, f, indent=2)
