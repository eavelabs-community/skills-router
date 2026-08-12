from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "skills_router.py"


class SkillsRouterWorkflowTest(unittest.TestCase):
    def run_search(self, common: list[str], query: str) -> list[dict[str, object]]:
        result = subprocess.run(
            [*common, "search", query], check=True, capture_output=True, text=True
        )
        return json.loads(result.stdout)

    def run_search_many(self, common: list[str], queries: list[str]) -> list[dict[str, object]]:
        result = subprocess.run(
            [*common, "search-many", *queries], check=True, capture_output=True, text=True
        )
        return json.loads(result.stdout)

    def test_refresh_search_and_install(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            repository = root / "catalog"
            skill = repository / "skills" / "webapp-testing"
            skill.mkdir(parents=True)
            (skill / "SKILL.md").write_text(
                "---\nname: webapp-testing\ndescription: >-\n"
                "  Test web applications with Playwright\n"
                "  end-to-end testing.\n---\n",
                encoding="utf-8",
            )
            claude_only_skill = repository / "skills" / "claude-only"
            claude_only_skill.mkdir()
            (claude_only_skill / "SKILL.md").write_text(
                "---\nname: claude-only\ntargets: [claude]\n"
                "description: 'A fixture that only supports Claude.'\n---\n",
                encoding="utf-8",
            )
            unsafe_name_skill = repository / "skills" / "unsafe-name"
            unsafe_name_skill.mkdir()
            (unsafe_name_skill / "SKILL.md").write_text(
                "---\nname: ../outside\n"
                "description: 'A fixture with an unsafe installation name.'\n---\n",
                encoding="utf-8",
            )
            pdf_skill = repository / "skills" / "pdf"
            pdf_skill.mkdir()
            (pdf_skill / "SKILL.md").write_text(
                "---\nname: pdf\n"
                "description: 'Extract text from PDF files.'\n---\n",
                encoding="utf-8",
            )
            docx_skill = repository / "skills" / "docx"
            docx_skill.mkdir()
            (docx_skill / "SKILL.md").write_text(
                "---\nname: docx\n"
                "description: 'Create and edit Word documents.'\n---\n",
                encoding="utf-8",
            )
            subprocess.run(["git", "init", "-b", "main", str(repository)], check=True, capture_output=True)
            subprocess.run(["git", "-C", str(repository), "add", "."], check=True, capture_output=True)
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(repository),
                    "-c",
                    "user.name=Skills Router Test",
                    "-c",
                    "user.email=test@example.invalid",
                    "commit",
                    "-m",
                    "fixture",
                ],
                check=True,
                capture_output=True,
            )
            fixture_commit = subprocess.run(
                ["git", "-C", str(repository), "rev-parse", "HEAD"],
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()

            sources = root / "sources.json"
            registry = root / "registry.json"
            cache = root / "cache"
            workspace = root / "workspace"
            (workspace / ".github").mkdir(parents=True)
            (workspace / ".github" / "copilot-instructions.md").write_text("# Test\n", encoding="utf-8")
            (workspace / ".claude").mkdir()
            (workspace / ".codebuddy").mkdir()
            platforms = root / "platforms.json"
            platforms.write_text(
                json.dumps(
                    {
                        "platforms": {
                            "copilot": {
                                "markers": [".github/copilot-instructions.md"],
                                "install_root": ".github/skills",
                            },
                            "claude": {"markers": [".claude"], "install_root": ".claude/skills"},
                            "codebuddy": {
                                "markers": [".codebuddy"],
                                "install_root": ".codebuddy/skills",
                                "format": "platform-specific",
                                "capabilities": ["mcp", "terminal"],
                            },
                        }
                    }
                ),
                encoding="utf-8",
            )
            sources.write_text(
                json.dumps(
                    {
                        "sources": [
                            {
                                "id": "fixture",
                                "repo": str(repository),
                                "ref": fixture_commit,
                                "skills_path": "skills",
                                "priority": 100,
                                "trusted": True,
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            common = [
                sys.executable,
                str(SCRIPT),
                "--sources",
                str(sources),
                "--registry",
                str(registry),
                "--cache",
                str(cache),
                "--platforms",
                str(platforms),
                "--workspace",
                str(workspace),
            ]
            pre_refresh_detected = subprocess.run(
                [*common, "detect-platform"],
                check=True,
                capture_output=True,
                text=True,
                env={key: value for key, value in os.environ.items() if key != "SKILLS_ROUTER_PLATFORM"},
            )
            self.assertEqual(json.loads(pre_refresh_detected.stdout)["detected"], ["copilot", "claude", "codebuddy"])

            subprocess.run([*common, "refresh"], check=True, capture_output=True, text=True)
            candidates = self.run_search(common, "Playwright web testing")
            self.assertEqual(candidates[0]["id"], "fixture:webapp-testing")

            chinese_candidates = self.run_search(common, "给网站添加端到端测试")
            self.assertEqual(chinese_candidates[0]["id"], "fixture:webapp-testing")

            self.assertEqual(self.run_search(common, "tell me what time it is"), [])

            multi_query_candidates = self.run_search_many(
                common,
                ["给网站添加端到端测试", "Playwright web end-to-end testing", "tell me the time"],
            )
            self.assertEqual(multi_query_candidates[0]["id"], "fixture:webapp-testing")
            self.assertEqual(
                multi_query_candidates[0]["matched_queries"],
                ["给网站添加端到端测试", "Playwright web end-to-end testing"],
            )
            self.assertEqual(len(multi_query_candidates[0]["query_evidence"]), 2)

            document_output_candidates = self.run_search_many(
                common,
                ["extract PDF contract into editable Word document", "pdf extraction", "docx document creation"],
            )
            self.assertEqual(document_output_candidates[0]["id"], "fixture:docx")

            detected = subprocess.run(
                [*common, "detect-platform"],
                check=True,
                capture_output=True,
                text=True,
                env={key: value for key, value in os.environ.items() if key != "SKILLS_ROUTER_PLATFORM"},
            )
            detected_payload = json.loads(detected.stdout)
            self.assertEqual(detected_payload["detected"], ["copilot", "claude", "codebuddy"])
            self.assertIsNone(detected_payload["active"])
            self.assertEqual(detected_payload["active_source"], "unresolved")

            environment = dict(os.environ, SKILLS_ROUTER_PLATFORM="claude")
            active_detected = subprocess.run(
                [*common, "detect-platform"],
                check=True,
                capture_output=True,
                text=True,
                env=environment,
            )
            self.assertEqual(json.loads(active_detected.stdout)["active"], "claude")

            explicit_detected = subprocess.run(
                [*common, "detect-platform", "--active-platform", "copilot"],
                check=True,
                capture_output=True,
                text=True,
                env=environment,
            )
            explicit_payload = json.loads(explicit_detected.stdout)
            self.assertEqual(explicit_payload["active"], "copilot")
            self.assertEqual(explicit_payload["active_source"], "argument")

            generic_github_workspace = root / "generic-github-workspace"
            (generic_github_workspace / ".github").mkdir(parents=True)
            generic_detected = subprocess.run(
                [
                    *common[:-2],
                    "--workspace",
                    str(generic_github_workspace),
                    "detect-platform",
                ],
                check=True,
                capture_output=True,
                text=True,
                env={key: value for key, value in os.environ.items() if key != "SKILLS_ROUTER_PLATFORM"},
            )
            self.assertEqual(json.loads(generic_detected.stdout)["detected"], [])

            plan = subprocess.run(
                [*common, "plan-install", "fixture:webapp-testing", "--platform", "all"],
                check=True,
                capture_output=True,
                text=True,
            )
            plans = {item["platform"]: item for item in json.loads(plan.stdout)["plans"]}
            self.assertEqual(plans["copilot"]["compatibility"], "native")
            self.assertEqual(plans["claude"]["compatibility"], "native")
            self.assertEqual(plans["codebuddy"]["compatibility"], "adaptation-required")

            status = subprocess.run(
                [*common, "status", "fixture:webapp-testing", "--platform", "copilot"],
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertEqual(json.loads(status.stdout)["compatibility"], "native")

            subprocess.run(
                [*common, "install", "fixture:webapp-testing", "--platform", "copilot"],
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertTrue((workspace / ".github" / "skills" / "webapp-testing" / "SKILL.md").is_file())

            unsafe_install = subprocess.run(
                [*common, "install", "fixture:../outside", "--platform", "copilot"],
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(unsafe_install.returncode, 0)
            self.assertIn("invalid skill name", unsafe_install.stderr)
            self.assertFalse((workspace / ".github" / "outside").exists())

            unsupported_status = subprocess.run(
                [*common, "status", "fixture:claude-only", "--platform", "copilot"],
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertEqual(json.loads(unsupported_status.stdout)["compatibility"], "adaptation-required")
            adaptation = subprocess.run(
                [*common, "prepare-adaptation", "fixture:claude-only", "--platform", "copilot"],
                check=True,
                capture_output=True,
                text=True,
            )
            adaptation_payload = json.loads(adaptation.stdout)
            self.assertEqual(adaptation_payload["action"], "adapt-with-current-ai")
            self.assertEqual(adaptation_payload["target_platform"], "copilot")
            blocked_install = subprocess.run(
                [*common, "install", "fixture:claude-only", "--platform", "copilot"],
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(blocked_install.returncode, 0)
            self.assertFalse((workspace / ".github" / "skills" / "claude-only").exists())


if __name__ == "__main__":
    unittest.main()
