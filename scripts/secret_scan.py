#!/usr/bin/env python3
"""Secret scanner for this PUBLIC repo.

Usage:
  python scripts/secret_scan.py --staged            # scan the staged diff (pre-commit)
  python scripts/secret_scan.py --range A..B        # scan commits about to be pushed (pre-push)

Exit code 1 (and a short report, never the matched value) if anything looks like a secret.
The regexes require key-shaped suffixes so docs that merely *mention* a prefix
(e.g. "sk-" or "-----BEGIN") do not trip the guard.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import PurePosixPath

PATTERNS = [
    ("anthropic key", re.compile(r"sk-ant-[A-Za-z0-9_\-]{8,}")),
    ("generic sk- key", re.compile(r"(?<![A-Za-z0-9])sk-[A-Za-z0-9_\-]{16,}")),
    ("github token", re.compile(r"ghp_[A-Za-z0-9]{20,}")),
    ("github fine-grained token", re.compile(r"github_pat_[A-Za-z0-9_]{20,}")),
    ("aws access key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("pem block", re.compile(r"-----BEGIN [A-Z ]+-----")),
    ("slack token", re.compile(r"xox[abposr]-[A-Za-z0-9\-]{10,}")),
]
# KEY=value assignments with a literal, secret-looking value (not os.getenv / empty / comment).
ASSIGN = re.compile(
    r"(API_KEY|TOKEN|SECRET|PASSWORD)\s*[=:]\s*(?!os\.|getenv|None\b|#|<|\$\{)['\"]?[^\s'\"#,)]{8,}"
)


def _is_env_file(path: str) -> bool:
    name = PurePosixPath(path).name
    return (name == ".env" or name.startswith(".env.")) and name != ".env.example"


def _run(args: list[str]) -> str:
    return subprocess.run(args, capture_output=True, text=True, check=False).stdout


def scan_diff(diff_text: str, names: list[str]) -> list[str]:
    problems = [f"staged env file: {n}" for n in names if _is_env_file(n)]
    current = None
    for line in diff_text.splitlines():
        if line.startswith("+++ "):
            current = line[6:] if line.startswith("+++ b/") else line[4:]
            continue
        if not line.startswith("+") or line.startswith("+++"):
            continue
        body = line[1:]
        for label, rx in PATTERNS:
            if rx.search(body):
                problems.append(f"{current}: looks like a {label}")
        if current and PurePosixPath(current).name != ".env.example" and ASSIGN.search(body):
            problems.append(f"{current}: literal secret-style assignment")
    return problems


def main(argv: list[str]) -> int:
    if len(argv) >= 2 and argv[0] == "--range":
        rng = argv[1]
        names = _run(["git", "diff", "--name-only", rng]).split()
        diff = _run(["git", "diff", "-U0", "--no-color", rng])
    else:
        names = _run(["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"]).split()
        diff = _run(["git", "diff", "--cached", "-U0", "--no-color"])
    problems = scan_diff(diff, names)
    if problems:
        print("SECRET GUARD: blocked. Fix these before committing/pushing:")
        for p in sorted(set(problems)):
            print("  -", p)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
