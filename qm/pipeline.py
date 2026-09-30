"""Pipeline wiring + CLI.

    python -m qm.pipeline --check-ollama      # connectivity + JSON smoke test (Quentin's PC)
    python -m qm.pipeline --warm demo/rfqs    # pre-fill cache/llm for every demo RFQ
"""
from __future__ import annotations

import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m qm.pipeline")
    ap.add_argument("--check-ollama", action="store_true", help="smoke-test the local Ollama model")
    ap.add_argument("--warm", metavar="RFQ_DIR", help="warm the LLM cache for all RFQs in a folder")
    args = ap.parse_args(argv)
    if args.check_ollama:
        from qm.llm import check_ollama
        return 0 if check_ollama() else 1
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
