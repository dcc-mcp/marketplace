import contextlib
import importlib.util
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "validate_marketplace.py"
SPEC = importlib.util.spec_from_file_location("validate_marketplace", SCRIPT_PATH)
validate_marketplace = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(validate_marketplace)


def valid_skill(ref: str = "a" * 40) -> dict:
    return {
        "name": "maya-rig-tools",
        "description": "Rigging helpers for Maya",
        "version": "1.2.3",
        "dcc": ["maya"],
        "tags": ["rigging", "domain"],
        "category": "Skills",
        "maintainer": "dcc-mcp",
        "minCoreVersion": "0.19.0",
        "source": {
            "type": "git",
            "url": "https://github.com/dcc-mcp/maya-rig-tools",
            "ref": ref,
            "skillRoots": ["skill/maya-rig-tools"],
        },
        "policy": {"installation": "available"},
    }


class MarketplaceValidatorTests(unittest.TestCase):
    def test_official_catalog_requires_immutable_git_refs(self) -> None:
        catalog = {"name": "dcc-mcp-official", "schemaVersion": "1", "skills": [valid_skill("main")]}
        original = validate_marketplace.load_marketplace
        validate_marketplace.load_marketplace = lambda: catalog
        try:
            with contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertFalse(validate_marketplace.check_metadata_quality())
        finally:
            validate_marketplace.load_marketplace = original
        self.assertIn("must pin source.ref", output.getvalue())

    def test_custom_catalog_can_use_a_release_tag(self) -> None:
        catalog = {"name": "my-studio-private", "schemaVersion": "1", "skills": [valid_skill("v1.2.3")]}
        original = validate_marketplace.load_marketplace
        validate_marketplace.load_marketplace = lambda: catalog
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertTrue(validate_marketplace.check_metadata_quality())
        finally:
            validate_marketplace.load_marketplace = original

    def test_official_catalog_requires_skill_roots(self) -> None:
        skill = valid_skill()
        del skill["source"]["skillRoots"]
        catalog = {"name": "dcc-mcp-official", "schemaVersion": "1", "skills": [skill]}
        original = validate_marketplace.load_marketplace
        validate_marketplace.load_marketplace = lambda: catalog
        try:
            with contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertFalse(validate_marketplace.check_metadata_quality())
        finally:
            validate_marketplace.load_marketplace = original
        self.assertIn("must declare non-empty source.skillRoots", output.getvalue())

    def test_skill_root_must_contain_a_skill_file(self) -> None:
        paths = {"skill/release/SKILL.md", "examples/demo/SKILL.md"}
        self.assertTrue(validate_marketplace._skill_root_contains_skill(paths, "skill/release"))
        self.assertFalse(validate_marketplace._skill_root_contains_skill(paths, "skill/missing"))

    def test_source_freshness_reports_newer_upstream_commits_without_failing(self) -> None:
        catalog = {"name": "dcc-mcp-official", "schemaVersion": "1", "skills": [valid_skill()]}
        original_load = validate_marketplace.load_marketplace
        original_api = validate_marketplace._github_api_json
        validate_marketplace.load_marketplace = lambda: catalog
        validate_marketplace._github_api_json = lambda path: (
            {"default_branch": "main"} if path.endswith("maya-rig-tools") else {"ahead_by": 2}
        )
        try:
            with contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertTrue(validate_marketplace.check_source_freshness())
        finally:
            validate_marketplace.load_marketplace = original_load
            validate_marketplace._github_api_json = original_api
        self.assertIn("2 commit(s) after pinned", output.getvalue())

    def test_schema_rejects_unknown_entry_fields(self) -> None:
        schema = json.loads((ROOT / "schemas" / "marketplace-v1.schema.json").read_text(encoding="utf-8"))
        catalog = {
            "name": "dcc-mcp-official",
            "schemaVersion": "1",
            "version": "1.0.0",
            "skills": [valid_skill()],
        }
        catalog["skills"][0]["misspelledPolicy"] = True
        from jsonschema import Draft202012Validator

        errors = list(Draft202012Validator(schema).iter_errors(catalog))
        self.assertTrue(errors)
        self.assertIn("Additional properties", errors[0].message)

    def test_catalog_option_validates_custom_catalog(self) -> None:
        catalog = {
            "name": "my-studio-private",
            "schemaVersion": "1",
            "version": "1.0.0",
            "skills": [valid_skill("v1.2.3")],
        }
        with tempfile.TemporaryDirectory() as tmp:
            catalog_path = Path(tmp) / "marketplace.json"
            catalog_path.write_text(json.dumps(catalog), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SCRIPT_PATH), "schema", "--catalog", str(catalog_path)],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Schema validation passed.", result.stdout)


if __name__ == "__main__":
    unittest.main()
