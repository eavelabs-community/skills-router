"""Generate platform-specific skills-router entries from a single source of truth.

The canonical router core lives in `.skills-router/`. AI platforms only auto-load skills
from their own directories (e.g. `.github/skills`, `.codebuddy/skills`), so this script
distributes a thin `SKILL.md` wrapper — plus any platform-specific init files declared in
`platforms.json` (`init_files`) — into every platform directory that is present in the
current workspace.

Design principle: `.skills-router/` is the only hand-maintained location. Templates live in
`.skills-router/templates/`:

- `SKILL.md.template`      — shared entry template for all platforms (SKILL.md format).
- `overrides/<platform>/`  — platform-specific templates (e.g. Copilot's
                             `copilot-instructions.md`) and any override that replaces
                             the shared template of the same relative path. `init.py`
                             resolves a template to `overrides/<platform>/<rel>` first,
                             falling back to the shared template.

Each generated file is a build artifact — regenerate it with this script instead of
editing by hand.

Usage:
    python .skills-router/init.py                # detect platforms and generate entries
    python .skills-router/init.py --platform codebuddy --platform copilot
    python .skills-router/init.py --all          # generate for every configured platform
    python .skills-router/init.py --dry-run      # print what would be written
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path
from typing import Any

# The router core is platform-agnostic and kept out of package layout, so load it
# by explicit file path instead of relying on import search paths.
ROUTER_CORE = Path(__file__).resolve().parent / "scripts" / "skills_router.py"


def load_router_core() -> Any:
    spec = importlib.util.spec_from_file_location("skills_router", ROUTER_CORE)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load router core: {ROUTER_CORE}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


skills_router = load_router_core()

ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = Path(__file__).resolve().parent
TEMPLATES = SKILL_DIR / "templates"
SKILL_TEMPLATE = TEMPLATES / "SKILL.md.template"
PLATFORMS = SKILL_DIR / "platforms.json"
REGISTRY = SKILL_DIR / "registry.json"


def resolve_template(platform: str, template: Path) -> Path:
    """Resolve a template to a platform override if present, else the shared one.

    Overrides live at `templates/overrides/<platform>/<relative path>`; only files
    that actually differ from the shared template need to be placed there. This keeps
    the default (shared) template as the single source of truth for all platforms.
    """
    if TEMPLATES in template.parents:
        override = TEMPLATES / "overrides" / platform / template.relative_to(TEMPLATES)
        if override.is_file():
            return override
    return template


def render_template(template: Path, context: dict[str, str]) -> str:
    """Render a template by substituting `{{KEY}}` placeholders from context."""
    text = template.read_text(encoding="utf-8")
    for key, value in context.items():
        text = text.replace("{{" + key + "}}", value)
    return text


def build_context(platform: str, install_root: Path, workspace: Path) -> dict[str, str]:
    """Build the placeholder context shared by all templates for a platform."""
    wrapper = install_root / "skills-router" / "SKILL.md"
    try:
        skill_ref = wrapper.resolve().relative_to(workspace.resolve()).as_posix()
    except ValueError:
        skill_ref = wrapper.as_posix()
    return {
        "ROUTER_SCRIPT": str(SKILL_DIR / "scripts" / "skills_router.py"),
        "ROUTER_EVAL": str(SKILL_DIR / "tests" / "evaluate_router.py"),
        "ROUTER_REGISTRY": str(REGISTRY),
        "ROUTER_SKILL": skill_ref,
        "PLATFORM": platform,
    }


def generate(
    platforms: dict[str, dict[str, Any]],
    selected: list[str],
    workspace: Path,
    dry_run: bool,
) -> list[tuple[Path, Path]]:
    """Generate entries; returns (output_path, template_used) for each target."""
    written: list[tuple[Path, Path]] = []
    for platform in selected:
        config = platforms[platform]
        install_root = workspace / str(config["install_root"])
        context = build_context(platform, install_root, workspace)

        # 1) Shared SKILL.md entry wrapper for every platform.
        destination = install_root / "skills-router" / "SKILL.md"
        template = resolve_template(platform, SKILL_TEMPLATE)
        if not dry_run:
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(render_template(template, context), encoding="utf-8")
        written.append((destination, template))

        # 2) Platform-specific init files declared in platforms.json -> init_files.
        init_files = config.get("init_files", {})
        for template_rel, output_rel in init_files.items():
            template = resolve_template(platform, SKILL_DIR / str(template_rel))
            output = workspace / str(output_rel)
            if not dry_run:
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(render_template(template, context), encoding="utf-8")
            written.append((output, template))
    return written


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=ROOT, help="Project root (default: repo root).")
    parser.add_argument("--platform", action="append", dest="platforms", help="Platform to generate for.")
    parser.add_argument("--all", action="store_true", help="Generate for every configured platform.")
    parser.add_argument("--dry-run", action="store_true", help="Print targets without writing.")
    args = parser.parse_args()

    platforms = skills_router.load_platforms(PLATFORMS)
    if args.platforms:
        unknown = [p for p in args.platforms if p not in platforms]
        if unknown:
            print(f"unknown platform(s): {', '.join(unknown)}", file=sys.stderr)
            return 2
        selected = args.platforms
    elif args.all:
        selected = sorted(platforms)
    else:
        selected = skills_router.detect_platform(platforms, args.workspace)
        if not selected:
            print(
                "no configured agent platform detected in workspace; "
                "use --platform <name> or --all",
                file=sys.stderr,
            )
            return 1

    written = generate(platforms, selected, args.workspace, args.dry_run)
    action = "Would write" if args.dry_run else "Wrote"
    for path, template in written:
        source = template.relative_to(SKILL_DIR).as_posix()
        print(f"{action}: {path}  <- {source}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
