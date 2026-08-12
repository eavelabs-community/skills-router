from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SKILL_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCES = SKILL_ROOT / "sources.json"
DEFAULT_REGISTRY = SKILL_ROOT / "registry.json"
DEFAULT_CACHE = SKILL_ROOT / ".cache"
DEFAULT_PLATFORMS = SKILL_ROOT / "platforms.json"
PLATFORM_ENVIRONMENT_VARIABLE = "SKILLS_ROUTER_PLATFORM"
STOP_WORDS = {
    "a",
    "an",
    "and",
    "after",
    "be",
    "for",
    "from",
    "i",
    "in",
    "is",
    "it",
    "me",
    "of",
    "on",
    "please",
    "tell",
    "the",
    "this",
    "time",
    "to",
    "what",
    "with",
}
QUERY_EXPANSIONS = {
    "ppt": "pptx powerpoint presentation slides deck",
    "powerpoint": "pptx presentation slides deck",
    "幻灯片": "pptx powerpoint presentation slides deck",
    "汇报": "pptx powerpoint presentation slides deck",
    "演示文稿": "pptx powerpoint presentation slides deck",
    "word": "docx word document create edit",
    "excel": "xlsx spreadsheet workbook",
    "表格": "xlsx spreadsheet workbook",
    "电子表格": "xlsx spreadsheet workbook",
    "端到端测试": "end-to-end e2e webapp testing playwright",
    "流水线失败": "failing github actions ci checks debug",
    "构建失败": "failing build ci checks debug",
    "workflow is red": "failing github actions ci checks debug",
    "workflow failed": "failing github actions ci checks debug",
}


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as file:
        return json.load(file)


def parse_scalar(value: str) -> Any:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    if value.startswith("[") and value.endswith("]"):
        return [item.strip().strip("'\"") for item in value[1:-1].split(",") if item.strip()]
    if value.lower() in {"true", "false"}:
        return value.lower() == "true"
    return value


def parse_frontmatter(path: Path) -> dict[str, Any]:
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    if not lines or lines[0].strip() != "---":
        return {}

    metadata: dict[str, Any] = {}
    index = 1
    while index < len(lines):
        line = lines[index]
        if line.strip() == "---":
            break
        match = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", line)
        if match:
            key, raw_value = match.groups()
            if re.fullmatch(r"[>|][+-]?", raw_value.strip()):
                block_lines: list[str] = []
                index += 1
                while index < len(lines) and (not lines[index].strip() or lines[index][0].isspace()):
                    block_lines.append(lines[index].strip())
                    index += 1
                separator = "\n" if raw_value.strip().startswith("|") else " "
                metadata[key] = separator.join(part for part in block_lines if part).strip()
                continue
            metadata[key] = parse_scalar(raw_value)
        index += 1
    return metadata


def run_git(arguments: list[str]) -> str:
    result = subprocess.run(
        ["git", *arguments],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return result.stdout.strip()


def sync_source(source: dict[str, Any], cache_root: Path) -> tuple[Path, str]:
    checkout = cache_root / source["id"]
    ref = str(source.get("ref", "main"))
    if checkout.exists():
        run_git(["-C", str(checkout), "fetch", "--depth", "1", "origin", ref])
        run_git(["-C", str(checkout), "checkout", "--detach", "FETCH_HEAD"])
    else:
        checkout.parent.mkdir(parents=True, exist_ok=True)
        run_git(["clone", "--no-checkout", "--depth", "1", source["repo"], str(checkout)])
        run_git(["-C", str(checkout), "fetch", "--depth", "1", "origin", ref])
        run_git(["-C", str(checkout), "checkout", "--detach", "FETCH_HEAD"])
    commit = run_git(["-C", str(checkout), "rev-parse", "HEAD"])
    return checkout, commit


def discover_skills(source: dict[str, Any], checkout: Path, commit: str) -> list[dict[str, Any]]:
    catalog_root = (checkout / source.get("skills_path", ".")).resolve()
    if not catalog_root.is_relative_to(checkout.resolve()):
        raise ValueError(f"skills_path escapes checkout for source {source['id']}")

    skills: list[dict[str, Any]] = []
    for skill_file in sorted(catalog_root.glob("*/SKILL.md")):
        metadata = parse_frontmatter(skill_file)
        name = str(metadata.get("name") or skill_file.parent.name)
        description = str(metadata.get("description") or "").strip()
        if not description:
            continue
        relative_path = skill_file.parent.relative_to(checkout).as_posix()
        skills.append(
            {
                "id": f"{source['id']}:{name}",
                "name": name,
                "description": description,
                "source_id": source["id"],
                "repo": source["repo"],
                "ref": source.get("ref", "main"),
                "commit": commit,
                "path": relative_path,
                "priority": int(source.get("priority", 0)),
                "trusted": bool(source.get("trusted", False)),
                "has_scripts": (skill_file.parent / "scripts").is_dir(),
                "targets": metadata.get("targets", []),
            }
        )
    return skills


def refresh(sources_path: Path, registry_path: Path, cache_root: Path) -> dict[str, Any]:
    configured_sources = load_json(sources_path).get("sources", [])
    all_skills: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    for source in configured_sources:
        try:
            checkout, commit = sync_source(source, cache_root)
            all_skills.extend(discover_skills(source, checkout, commit))
        except (OSError, subprocess.CalledProcessError, ValueError) as error:
            errors.append({"source_id": str(source.get("id", "unknown")), "error": str(error)})

    registry = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "skills": all_skills,
        "errors": errors,
    }
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(json.dumps(registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return registry


def expand_query(query: str) -> str:
    normalized = query.casefold()
    additions = [expansion for phrase, expansion in QUERY_EXPANSIONS.items() if phrase in normalized]
    return " ".join([query, *additions])


def terms(text: str) -> set[str]:
    return {term for term in re.findall(r"[\w.+#-]+", text.casefold()) if term not in STOP_WORDS}


def score_skill(query: str, skill: dict[str, Any]) -> tuple[float, list[str]]:
    query_terms = terms(expand_query(query))
    name_terms = terms(skill["name"].replace("-", " "))
    description_terms = terms(skill["description"])
    reasons: list[str] = []
    score = 0.0

    name_hits = query_terms & name_terms
    description_hits = query_terms & description_terms
    if name_hits:
        score += 6 * len(name_hits)
        reasons.append(f"name: {', '.join(sorted(name_hits))}")
        if name_terms <= query_terms:
            score += 4
            reasons.append("complete skill name match")
    if description_hits:
        score += 2 * len(description_hits)
        reasons.append(f"description: {', '.join(sorted(description_hits))}")
    if query.casefold() in skill["description"].casefold():
        score += 5
        reasons.append("exact phrase in description")
    score += min(int(skill.get("priority", 0)), 100) / 100
    if skill.get("trusted"):
        score += 0.5
    return score, reasons


def search(registry: dict[str, Any], query: str, limit: int) -> list[dict[str, Any]]:
    ranked = []
    for skill in registry.get("skills", []):
        score, reasons = score_skill(query, skill)
        if reasons and score >= 4:
            ranked.append({**skill, "score": round(score, 2), "reasons": reasons})
    return sorted(ranked, key=lambda item: (-item["score"], item["id"]))[:limit]


def search_many(registry: dict[str, Any], queries: list[str], limit: int) -> list[dict[str, Any]]:
    candidates: dict[str, dict[str, Any]] = {}
    for query in dict.fromkeys(query.strip() for query in queries if query.strip()):
        for match in search(registry, query, len(registry.get("skills", []))):
            candidate = candidates.setdefault(
                match["id"],
                {
                    **{key: value for key, value in match.items() if key not in {"score", "reasons"}},
                    "best_score": match["score"],
                    "matched_queries": [],
                    "query_evidence": [],
                },
            )
            candidate["best_score"] = max(candidate["best_score"], match["score"])
            candidate["matched_queries"].append(query)
            candidate["query_evidence"].append(
                {"query": query, "score": match["score"], "reasons": match["reasons"]}
            )

    for candidate in candidates.values():
        supporting_query_count = len(candidate["matched_queries"]) - 1
        candidate["score"] = round(candidate.pop("best_score") + 1.5 * supporting_query_count, 2)
    return sorted(candidates.values(), key=lambda item: (-item["score"], item["id"]))[:limit]


def get_candidate(registry: dict[str, Any], candidate_id: str) -> dict[str, Any]:
    matches = [skill for skill in registry.get("skills", []) if skill["id"] == candidate_id]
    if len(matches) != 1:
        raise ValueError(f"candidate not found: {candidate_id}")
    return matches[0]


def load_platforms(path: Path) -> dict[str, dict[str, Any]]:
    return load_json(path).get("platforms", {})


def detect_platform(platforms: dict[str, dict[str, Any]], workspace: Path) -> list[str]:
    detected = []
    for platform, config in platforms.items():
        if any((workspace / marker).exists() for marker in config.get("markers", [])):
            detected.append(platform)
    return detected


def select_platform(
    requested_platform: str, platforms: dict[str, dict[str, Any]], workspace: Path
) -> str:
    platform, _ = resolve_active_platform(requested_platform, platforms, workspace)
    if platform is None:
        detected = detect_platform(platforms, workspace)
        detail = ", ".join(detected) if detected else "none"
        raise ValueError(f"cannot select platform automatically; detected: {detail}")
    return platform


def resolve_active_platform(
    requested_platform: str, platforms: dict[str, dict[str, Any]], workspace: Path
) -> tuple[str | None, str]:
    if requested_platform != "auto":
        if requested_platform not in platforms:
            raise ValueError(f"unknown platform: {requested_platform}")
        return requested_platform, "argument"
    environment_platform = os.environ.get(PLATFORM_ENVIRONMENT_VARIABLE, "").strip()
    if environment_platform:
        if environment_platform not in platforms:
            raise ValueError(
                f"unknown platform in {PLATFORM_ENVIRONMENT_VARIABLE}: {environment_platform}"
            )
        return environment_platform, "environment"
    detected = detect_platform(platforms, workspace)
    if len(detected) == 1:
        return detected[0], "single-marker"
    return None, "unresolved"


def normalized_targets(candidate: dict[str, Any]) -> list[str]:
    targets = candidate.get("targets", [])
    if isinstance(targets, str):
        return [targets]
    return [str(target) for target in targets]


def platform_compatibility(
    candidate: dict[str, Any], platform: str, platforms: dict[str, dict[str, Any]]
) -> str:
    config = platforms[platform]
    if "skills" not in config.get("capabilities", ["skills"]):
        return "adaptation-required"
    if config.get("format", "SKILL.md") != "SKILL.md":
        return "adaptation-required"
    targets = normalized_targets(candidate)
    if not targets or platform in targets:
        return "native"
    return "adaptation-required"


def platform_install_root(platforms: dict[str, dict[str, Any]], platform: str, workspace: Path) -> Path:
    return workspace / platforms[platform]["install_root"]


def skill_destination(install_root: Path, skill_name: str) -> Path:
    if not skill_name or skill_name in {".", ".."} or "/" in skill_name or "\\" in skill_name:
        raise ValueError(f"invalid skill name: {skill_name!r}")
    if Path(skill_name).is_absolute():
        raise ValueError(f"invalid skill name: {skill_name!r}")

    root = install_root.resolve()
    destination = (root / skill_name).resolve()
    if not destination.is_relative_to(root):
        raise ValueError(f"skill destination escapes install root: {skill_name!r}")
    return destination


def platform_plan(
    candidate: dict[str, Any], platform: str, platforms: dict[str, dict[str, Any]], workspace: Path
) -> dict[str, Any]:
    config = platforms[platform]
    install_root = platform_install_root(platforms, platform, workspace)
    destination = skill_destination(install_root, candidate["name"])
    status = platform_compatibility(candidate, platform, platforms)
    return {
        "platform": platform,
        "format": config.get("format", "SKILL.md"),
        "capabilities": config.get("capabilities", ["skills"]),
        "compatibility": status,
        "destination": str(destination),
        "installed": destination.is_dir(),
        "action": "install" if status == "native" else "adapt-with-current-ai",
        "notes": config.get("notes"),
    }


def install_candidate(
    candidate: dict[str, Any], cache_root: Path, install_root: Path, force: bool = False
) -> Path:
    if not candidate.get("trusted"):
        raise ValueError("refusing automatic installation from an untrusted source")
    source = (cache_root / candidate["source_id"] / candidate["path"]).resolve()
    cache_source_root = (cache_root / candidate["source_id"]).resolve()
    if not source.is_relative_to(cache_source_root) or not (source / "SKILL.md").is_file():
        raise ValueError("cached skill path is invalid; refresh the registry")

    destination = skill_destination(install_root, candidate["name"])
    if destination.exists() and not force:
        raise FileExistsError(f"already installed: {destination}")
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source, destination)
    return destination


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Index, search, and install configured agent skills.")
    parser.add_argument("--sources", type=Path, default=DEFAULT_SOURCES)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--cache", type=Path, default=DEFAULT_CACHE)
    parser.add_argument("--platforms", type=Path, default=DEFAULT_PLATFORMS)
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("refresh")
    detect_parser = commands.add_parser("detect-platform")
    detect_parser.add_argument("--active-platform", default="auto")
    search_parser = commands.add_parser("search")
    search_parser.add_argument("query")
    search_parser.add_argument("--limit", type=int, default=3)
    search_many_parser = commands.add_parser("search-many")
    search_many_parser.add_argument("queries", nargs="+")
    search_many_parser.add_argument("--limit", type=int, default=5)
    status_parser = commands.add_parser("status")
    status_parser.add_argument("candidate_id")
    status_parser.add_argument("--platform", default="auto")
    install_parser = commands.add_parser("install")
    install_parser.add_argument("candidate_id")
    install_parser.add_argument("--platform", default="auto")
    install_parser.add_argument("--force", action="store_true")
    adapt_parser = commands.add_parser("prepare-adaptation")
    adapt_parser.add_argument("candidate_id")
    adapt_parser.add_argument("--platform", default="auto")
    plan_parser = commands.add_parser("plan-install")
    plan_parser.add_argument("candidate_id")
    plan_parser.add_argument("--platform", default="all")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.command == "refresh":
        result = refresh(args.sources, args.registry, args.cache)
        print(json.dumps({"skills": len(result["skills"]), "errors": result["errors"]}, ensure_ascii=False))
        return 1 if result["errors"] and not result["skills"] else 0

    platforms = load_platforms(args.platforms)
    if args.command == "detect-platform":
        detected = detect_platform(platforms, args.workspace)
        active, active_source = resolve_active_platform(
            args.active_platform, platforms, args.workspace
        )
        print(
            json.dumps(
                {
                    "detected": detected,
                    "active": active,
                    "active_source": active_source,
                    "override": PLATFORM_ENVIRONMENT_VARIABLE,
                    "platforms": [
                        {
                            "platform": platform,
                            "format": platforms[platform].get("format", "SKILL.md"),
                            "capabilities": platforms[platform].get("capabilities", ["skills"]),
                            "install_root": str(platform_install_root(platforms, platform, args.workspace)),
                            "notes": platforms[platform].get("notes"),
                        }
                        for platform in detected
                    ],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    if not args.registry.exists():
        print("Registry not found. Run refresh first.", file=sys.stderr)
        return 2
    registry = load_json(args.registry)
    if args.command == "search":
        print(json.dumps(search(registry, args.query, args.limit), ensure_ascii=False, indent=2))
        return 0
    if args.command == "search-many":
        print(json.dumps(search_many(registry, args.queries, args.limit), ensure_ascii=False, indent=2))
        return 0

    try:
        candidate = get_candidate(registry, args.candidate_id)
        if args.command == "plan-install":
            if args.platform == "all":
                selected_platforms = detect_platform(platforms, args.workspace)
                if not selected_platforms:
                    raise ValueError("no configured agent platform detected")
            else:
                selected_platforms = [select_platform(args.platform, platforms, args.workspace)]
            print(
                json.dumps(
                    {
                        "candidate": candidate["id"],
                        "source_targets": normalized_targets(candidate),
                        "plans": [
                            platform_plan(candidate, platform, platforms, args.workspace)
                            for platform in selected_platforms
                        ],
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 0
        platform = select_platform(getattr(args, "platform", "auto"), platforms, args.workspace)
        install_root = platform_install_root(platforms, platform, args.workspace)
        destination = skill_destination(install_root, candidate["name"])
        if args.command == "status":
            print(
                json.dumps(
                    {
                        "id": candidate["id"],
                        "platform": platform,
                        "compatibility": platform_compatibility(candidate, platform, platforms),
                        "installed": destination.is_dir(),
                        "path": str(destination),
                    }
                )
            )
        elif args.command == "install":
            if platform_compatibility(candidate, platform, platforms) != "native":
                raise ValueError(
                    "skill is not declared compatible with this platform; run prepare-adaptation and let the "
                    "current AI create a reviewed adapted Skill"
                )
            installed_path = install_candidate(candidate, args.cache, install_root, args.force)
            print(json.dumps({"id": candidate["id"], "platform": platform, "installed": True, "path": str(installed_path)}))
        elif args.command == "prepare-adaptation":
            source = args.cache / candidate["source_id"] / candidate["path"]
            print(
                json.dumps(
                    {
                        "action": "adapt-with-current-ai",
                        "candidate": candidate["id"],
                        "source_skill": str(source / "SKILL.md"),
                        "source_targets": normalized_targets(candidate),
                        "target_platform": platform,
                        "destination": str(destination),
                        "requirements": [
                            "Read the source SKILL.md and preserve its purpose, scope, exclusions, and attribution.",
                            "Replace source-specific tool calls, hooks, and paths with supported target-platform equivalents.",
                            "Do not copy or execute source scripts unless their behavior and dependencies are reviewed.",
                            "Write an adapted SKILL.md with metadata.source and metadata.adapted_for.",
                            "Validate the adapted frontmatter and target-platform resource paths before use.",
                        ],
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
    except (FileExistsError, OSError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
