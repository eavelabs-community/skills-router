from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from collections import Counter
from pathlib import Path
from types import ModuleType
from typing import Any


TEST_ROOT = Path(__file__).resolve().parent
SKILL_ROOT = TEST_ROOT.parent
DEFAULT_CASES = TEST_ROOT / "eval_cases.json"
DEFAULT_REGISTRY = SKILL_ROOT / "registry.json"
ROUTER_SCRIPT = SKILL_ROOT / "scripts" / "skills_router.py"


def load_router() -> ModuleType:
    spec = importlib.util.spec_from_file_location("skills_router_eval", ROUTER_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load router: {ROUTER_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_fixture_registry(cases: list[dict[str, Any]], router: ModuleType) -> dict[str, Any]:
    """Build a minimal offline registry from the skills referenced by eval cases.

    Lets the evaluation run without network access or a pre-existing
    registry.json (e.g. in CI). Descriptions are derived from the terms used
    in the queries of the cases that reference each skill, so the fixture only
    validates the routing/search logic, not real-world data quality.
    """
    referenced: dict[str, list[str]] = {}
    for case in cases:
        skill_ids: set[str] = set()
        for group in case.get("expected_groups", []):
            skill_ids.update(group)
        skill_ids.update(case.get("primary_any", []))
        for skill_id in skill_ids:
            referenced.setdefault(skill_id, []).extend(case["queries"])

    skills: list[dict[str, Any]] = []
    for skill_id, queries in sorted(referenced.items()):
        source_id, _, name = skill_id.partition(":")
        tokens: set[str] = set()
        for query in queries:
            tokens.update(router.terms(query))
        skills.append(
            {
                "id": skill_id,
                "name": name,
                "description": " ".join(sorted(tokens)),
                "source_id": source_id,
                "repo": "fixture",
                "ref": "fixture",
                "commit": "fixture",
                "path": "fixture",
                "priority": 100 if source_id == "anthropic" else 80,
                "trusted": True,
                "has_scripts": False,
                "targets": [],
            }
        )
    return {"generated_at": "fixture", "skills": skills, "errors": [], "fixture": True}


def evaluate(cases: list[dict[str, Any]], registry: dict[str, Any], top_k: int) -> dict[str, Any]:
    router = load_router()
    if len(cases) != 50:
        raise ValueError(f"expected exactly 50 evaluation cases, found {len(cases)}")

    route_count = 0
    coverage_hits = 0
    primary_hits = 0
    no_route_count = 0
    no_route_empty = 0
    category_totals: Counter[str] = Counter()
    category_hits: Counter[str] = Counter()
    failures: list[dict[str, Any]] = []

    for case in cases:
        candidates = router.search_many(registry, case["queries"], top_k)
        candidate_ids = [candidate["id"] for candidate in candidates]
        category = case["category"]
        category_totals[category] += 1

        if not case["should_route"]:
            no_route_count += 1
            if not candidates:
                no_route_empty += 1
                category_hits[category] += 1
            else:
                failures.append(
                    {
                        "id": case["id"],
                        "type": "no-route-false-positive",
                        "request": case["request"],
                        "actual": candidate_ids,
                    }
                )
            continue

        route_count += 1
        expected_groups = case["expected_groups"]
        missing_groups = [
            group for group in expected_groups if not any(candidate_id in group for candidate_id in candidate_ids)
        ]
        coverage_ok = not missing_groups
        primary_ok = bool(candidate_ids) and candidate_ids[0] in case["primary_any"]
        if coverage_ok:
            coverage_hits += 1
            category_hits[category] += 1
        if primary_ok:
            primary_hits += 1
        if not coverage_ok or not primary_ok:
            failures.append(
                {
                    "id": case["id"],
                    "type": "route-miss",
                    "request": case["request"],
                    "primary_ok": primary_ok,
                    "missing_groups": missing_groups,
                    "actual": candidate_ids,
                }
            )

    return {
        "total_cases": len(cases),
        "registry_skills": len(registry.get("skills", [])),
        "top_k": top_k,
        "route_cases": route_count,
        "primary_top1": {"hits": primary_hits, "accuracy": round(primary_hits / route_count, 4)},
        "required_top_k_coverage": {
            "hits": coverage_hits,
            "accuracy": round(coverage_hits / route_count, 4),
        },
        "no_route_cases": no_route_count,
        "no_route_search_rejection": {
            "hits": no_route_empty,
            "accuracy": round(no_route_empty / no_route_count, 4),
        },
        "category_coverage": {
            category: {
                "hits": category_hits[category],
                "total": total,
                "accuracy": round(category_hits[category] / total, 4),
            }
            for category, total in sorted(category_totals.items())
        },
        "failures": failures,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate skill routing against 50 fixed scenarios.")
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()

    router = load_router()
    cases = router.load_json(args.cases)["cases"]

    if args.registry.exists():
        registry = router.load_json(args.registry)
        print(f"evaluate: using registry {args.registry}", file=sys.stderr)
    else:
        print(
            f"evaluate: registry not found at {args.registry}; "
            "building offline fixture registry from eval cases",
            file=sys.stderr,
        )
        registry = build_fixture_registry(cases, router)

    report = evaluate(cases, registry, args.top_k)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
