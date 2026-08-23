"""Run the agent eval set.

    .venv/Scripts/python evals/run.py                       # default model
    .venv/Scripts/python evals/run.py --model gpt-5.5       # one model
    .venv/Scripts/python evals/run.py --compare gpt-4.1 gpt-5.5
    .venv/Scripts/python evals/run.py --case bait_blended_score --verbose

Each case is scored on four checks, and a failure prints the offending text so
it is diagnosable rather than just red.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from evals.cases import CASES, REFUSAL, Case
from respite.agent import openai_model, run


@dataclass
class Result:
    case: Case
    answer: str
    tools: list[str]
    failures: list[str] = field(default_factory=list)
    error: str | None = None
    seconds: float = 0.0

    @property
    def passed(self) -> bool:
        return not self.failures and self.error is None


def check(case: Case, answer: str, tools: list[str]) -> list[str]:
    fails: list[str] = []
    a = answer.lower()

    missing = case.must_call - set(tools)
    if missing:
        fails.append(f"did not call {sorted(missing)} (called {tools})")

    for pat in case.require:
        if not re.search(pat, answer, re.I):
            fails.append(f"missing required pattern /{pat}/")

    for pat in case.forbid:
        m = re.search(pat, answer, re.I)
        if m:
            fails.append(f"forbidden pattern /{pat}/ matched {m.group(0)!r}")

    if case.expect_refusal and not re.search(REFUSAL, a):
        fails.append("expected a refusal, none detected")

    return fails


def run_case(case: Case, model) -> Result:
    t0 = time.time()
    try:
        brief = run(case.question, model)
    except Exception as exc:  # noqa: BLE001
        return Result(case=case, answer="", tools=[], error=f"{type(exc).__name__}: {exc}",
                      seconds=time.time() - t0)
    tools = [s.tool for s in brief.steps]
    return Result(
        case=case,
        answer=brief.answer,
        tools=tools,
        failures=check(case, brief.answer, tools),
        seconds=time.time() - t0,
    )


def run_suite(model_name: str, cases: list[Case], verbose: bool) -> list[Result]:
    model = openai_model(model=model_name)
    results: list[Result] = []
    print(f"\n{'=' * 78}\nMODEL: {model_name}   ({len(cases)} cases)\n{'=' * 78}")
    for c in cases:
        r = run_case(c, model)
        results.append(r)
        mark = "pass" if r.passed else "FAIL"
        print(f"  [{mark}] {c.id:28} {r.seconds:5.1f}s  tools={len(r.tools)}")
        if r.error:
            print(f"          error: {r.error[:140]}")
        for f in r.failures:
            print(f"          {f[:150]}")
        if verbose and r.answer:
            print("          " + r.answer.replace("\n", "\n          ")[:600])
    return results


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=None)
    ap.add_argument("--compare", nargs="+", default=None)
    ap.add_argument("--case", default=None, help="run one case by id")
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--json", default=None, help="write results to this path")
    args = ap.parse_args()

    cases = CASES
    if args.case:
        cases = [c for c in CASES if c.id == args.case]
        if not cases:
            print(f"no case with id {args.case!r}. Available:")
            for c in CASES:
                print(f"  {c.id}")
            return 1

    models = args.compare or [args.model or "gpt-4.1"]
    all_results: dict[str, list[Result]] = {}
    for m in models:
        all_results[m] = run_suite(m, cases, args.verbose)

    print(f"\n{'=' * 78}\nSUMMARY\n{'=' * 78}")
    print(f"  {'model':22} {'pass':>6} {'fail':>6} {'err':>5} {'total s':>9}")
    for m, rs in all_results.items():
        p = sum(1 for r in rs if r.passed)
        e = sum(1 for r in rs if r.error)
        print(f"  {m:22} {p:>6} {len(rs) - p:>6} {e:>5} {sum(r.seconds for r in rs):>9.1f}")

    if len(all_results) > 1:
        print("\n  per-case comparison (. = pass, X = fail, E = error)")
        names = list(all_results)
        width = max(len(c.id) for c in cases) + 2
        print("  " + "case".ljust(width) + "  ".join(n[:12].rjust(12) for n in names))
        for i, c in enumerate(cases):
            row = ""
            for n in names:
                r = all_results[n][i]
                row += ("E" if r.error else "." if r.passed else "X").rjust(12) + "  "
            print("  " + c.id.ljust(width) + row)

    if args.json:
        Path(args.json).write_text(json.dumps({
            m: [{"id": r.case.id, "passed": r.passed, "failures": r.failures,
                 "error": r.error, "tools": r.tools, "answer": r.answer,
                 "seconds": round(r.seconds, 2)} for r in rs]
            for m, rs in all_results.items()
        }, indent=2), encoding="utf-8")
        print(f"\n  wrote {args.json}")

    worst = min(sum(1 for r in rs if r.passed) for rs in all_results.values())
    return 0 if worst == len(cases) else 1


if __name__ == "__main__":
    raise SystemExit(main())
