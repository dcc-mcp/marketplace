import contextlib
import base64
import importlib.util
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace


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
    def test_modeling_spec_is_installable_for_supported_hosts(self) -> None:
        catalog = json.loads((ROOT / "marketplace.json").read_text(encoding="utf-8"))

        modeling_spec = next(
            skill for skill in catalog["skills"] if skill["name"] == "dcc-modeling-spec"
        )

        self.assertEqual(
            modeling_spec["dcc"],
            ["maya", "blender", "houdini", "3dsmax"],
        )
        self.assertEqual(modeling_spec["source"]["skillRoots"], ["skill/modeling-spec"])
        self.assertIn("domain", modeling_spec["tags"])
        self.assertEqual(modeling_spec["policy"]["installation"], "available")

    def test_kenney_provider_is_installable_for_supported_hosts(self) -> None:
        catalog = json.loads((ROOT / "marketplace.json").read_text(encoding="utf-8"))
        kenney = next(skill for skill in catalog["skills"] if skill["name"] == "dcc-asset-kenney")

        self.assertTrue({"godot", "unreal", "unity", "zbrush"}.issubset(set(kenney["dcc"])))

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

    def test_custom_catalog_release_tag_passes_source_revision_check(self) -> None:
        catalog = {"name": "my-studio-private", "schemaVersion": "1", "skills": [valid_skill("v1.2.3")]}
        original_load = validate_marketplace.load_marketplace
        original_run = validate_marketplace.subprocess.run
        validate_marketplace.load_marketplace = lambda: catalog
        validate_marketplace.subprocess.run = lambda *args, **kwargs: SimpleNamespace(
            returncode=0,
            stdout="a" * 40 + "\trefs/tags/v1.2.3\n",
            stderr="",
        )
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertTrue(validate_marketplace.check_source_revisions())
        finally:
            validate_marketplace.load_marketplace = original_load
            validate_marketplace.subprocess.run = original_run

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

    def test_bundle_skills_must_match_declared_roots(self) -> None:
        skill = valid_skill()
        skill["package"] = {"format": "skill-bundle", "skills": ["other", "second"]}
        catalog = {"name": "dcc-mcp-official", "schemaVersion": "1", "skills": [skill]}
        original = validate_marketplace.load_marketplace
        validate_marketplace.load_marketplace = lambda: catalog
        try:
            with contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertFalse(validate_marketplace.check_metadata_quality())
        finally:
            validate_marketplace.load_marketplace = original
        self.assertIn("skills must match source.skillRoots", output.getvalue())

    def test_deprecated_skill_requires_a_known_successor(self) -> None:
        deprecated = valid_skill()
        deprecated["lifecycle"] = "deprecated"
        successor = valid_skill()
        successor["name"] = "maya-rig-tools-v2"
        catalog = {"name": "dcc-mcp-official", "schemaVersion": "1", "skills": [deprecated, successor]}
        original = validate_marketplace.load_marketplace
        validate_marketplace.load_marketplace = lambda: catalog
        try:
            with contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertFalse(validate_marketplace.check_metadata_quality())
            self.assertIn("must declare replacedBy", output.getvalue())

            deprecated["replacedBy"] = "missing-skill"
            with contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertFalse(validate_marketplace.check_metadata_quality())
            self.assertIn("replaces unknown skill", output.getvalue())

            deprecated["replacedBy"] = successor["name"]
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertTrue(validate_marketplace.check_metadata_quality())
        finally:
            validate_marketplace.load_marketplace = original

    def test_skill_root_must_contain_a_skill_file(self) -> None:
        paths = {"skill/release/SKILL.md", "examples/demo/SKILL.md"}
        self.assertTrue(validate_marketplace._skill_root_contains_skill(paths, "skill/release"))
        self.assertFalse(validate_marketplace._skill_root_contains_skill(paths, "skill/missing"))

    def test_custom_github_catalog_checks_declared_skill_roots(self) -> None:
        catalog = {"name": "my-studio-private", "schemaVersion": "1", "skills": [valid_skill("v1.2.3")]}
        original_load = validate_marketplace.load_marketplace
        original_tree_paths = validate_marketplace._github_tree_paths
        validate_marketplace.load_marketplace = lambda: catalog
        validate_marketplace._github_tree_paths = lambda repo, ref: {"skill/maya-rig-tools/SKILL.md"}
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertTrue(validate_marketplace.check_skill_layout())
        finally:
            validate_marketplace.load_marketplace = original_load
            validate_marketplace._github_tree_paths = original_tree_paths

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

    def test_asset_contract_requires_descriptor_source_and_license_fields(self) -> None:
        skill = valid_skill()
        skill["assetContract"] = "descriptor-v1"
        catalog = {"name": "dcc-mcp-official", "schemaVersion": "1", "skills": [skill]}
        original_load = validate_marketplace.load_marketplace
        original_api = validate_marketplace._github_api_json
        tools = "asset_descriptor:\n  source_url: example\n  license_spdx: CC0-1.0\n"
        validate_marketplace.load_marketplace = lambda: catalog
        validate_marketplace._github_api_json = lambda path: {
            "encoding": "base64",
            "content": base64.b64encode(tools.encode()).decode(),
        }
        try:
            with contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertTrue(validate_marketplace.check_asset_contract())
        finally:
            validate_marketplace.load_marketplace = original_load
            validate_marketplace._github_api_json = original_api
        self.assertIn("descriptor-v1", output.getvalue())

    def test_asset_contract_rejects_missing_license_field(self) -> None:
        skill = valid_skill()
        skill["assetContract"] = "descriptor-v1"
        catalog = {"name": "dcc-mcp-official", "schemaVersion": "1", "skills": [skill]}
        original_load = validate_marketplace.load_marketplace
        original_api = validate_marketplace._github_api_json
        tools = "asset_descriptor:\n  source_url: example\n"
        validate_marketplace.load_marketplace = lambda: catalog
        validate_marketplace._github_api_json = lambda path: {
            "encoding": "base64",
            "content": base64.b64encode(tools.encode()).decode(),
        }
        try:
            with contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertFalse(validate_marketplace.check_asset_contract())
        finally:
            validate_marketplace.load_marketplace = original_load
            validate_marketplace._github_api_json = original_api
        self.assertIn("license_spdx or license_text", output.getvalue())

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

    def test_schema_accepts_safe_repository_showcase_path(self) -> None:
        schema = json.loads((ROOT / "schemas" / "marketplace-v1.schema.json").read_text(encoding="utf-8"))
        catalog = {
            "name": "dcc-mcp-official",
            "schemaVersion": "1",
            "version": "1.0.0",
            "skills": [dict(valid_skill(), showcase="docs/images/example-showcase.webp")],
        }
        from jsonschema import Draft202012Validator

        self.assertEqual(list(Draft202012Validator(schema).iter_errors(catalog)), [])

    def test_schema_accepts_animated_gif_showcase_path(self) -> None:
        schema = json.loads((ROOT / "schemas" / "marketplace-v1.schema.json").read_text(encoding="utf-8"))
        catalog = {
            "name": "dcc-mcp-official",
            "schemaVersion": "1",
            "version": "1.0.0",
            "skills": [dict(valid_skill(), showcase="docs/showcase/procedural-demo.gif")],
        }
        from jsonschema import Draft202012Validator

        self.assertEqual(list(Draft202012Validator(schema).iter_errors(catalog)), [])

    def test_schema_accepts_adapter_style_dcc_identifier(self) -> None:
        schema = json.loads((ROOT / "schemas" / "marketplace-v1.schema.json").read_text(encoding="utf-8"))
        skill = valid_skill()
        skill["dcc"] = ["substance3d_designer"]
        catalog = {
            "name": "dcc-mcp-official",
            "schemaVersion": "1",
            "version": "1.0.0",
            "skills": [skill],
        }
        from jsonschema import Draft202012Validator

        self.assertEqual(list(Draft202012Validator(schema).iter_errors(catalog)), [])

    def test_schema_rejects_single_skill_bundle(self) -> None:
        schema = json.loads((ROOT / "schemas" / "marketplace-v1.schema.json").read_text(encoding="utf-8"))
        skill = valid_skill()
        skill["package"] = {"format": "skill-bundle", "skills": ["maya-rig-tools"]}
        catalog = {
            "name": "dcc-mcp-official",
            "schemaVersion": "1",
            "version": "1.0.0",
            "skills": [skill],
        }
        from jsonschema import Draft202012Validator

        self.assertTrue(list(Draft202012Validator(schema).iter_errors(catalog)))

    def test_schema_rejects_showcase_parent_traversal(self) -> None:
        schema = json.loads((ROOT / "schemas" / "marketplace-v1.schema.json").read_text(encoding="utf-8"))
        catalog = {
            "name": "dcc-mcp-official",
            "schemaVersion": "1",
            "version": "1.0.0",
            "skills": [dict(valid_skill(), showcase="../outside.png")],
        }
        from jsonschema import Draft202012Validator

        self.assertTrue(list(Draft202012Validator(schema).iter_errors(catalog)))

    def test_skill_layout_rejects_missing_showcase_at_pinned_ref(self) -> None:
        skill = dict(valid_skill(), showcase="docs/images/missing.webp")
        catalog = {"name": "dcc-mcp-official", "schemaVersion": "1", "skills": [skill]}
        original_load = validate_marketplace.load_marketplace
        original_tree_paths = validate_marketplace._github_tree_paths
        validate_marketplace.load_marketplace = lambda: catalog
        validate_marketplace._github_tree_paths = lambda repo, ref: {"skill/maya-rig-tools/SKILL.md"}
        try:
            with contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertFalse(validate_marketplace.check_skill_layout())
        finally:
            validate_marketplace.load_marketplace = original_load
            validate_marketplace._github_tree_paths = original_tree_paths
        self.assertIn("showcase does not exist", output.getvalue())

    def test_schema_requires_replacement_for_deprecated_skill(self) -> None:
        schema = json.loads((ROOT / "schemas" / "marketplace-v1.schema.json").read_text(encoding="utf-8"))
        catalog = {
            "name": "dcc-mcp-official",
            "schemaVersion": "1",
            "version": "1.0.0",
            "skills": [dict(valid_skill(), lifecycle="deprecated")],
        }
        from jsonschema import Draft202012Validator

        errors = list(Draft202012Validator(schema).iter_errors(catalog))
        self.assertTrue(errors)
        self.assertIn("replacedBy", errors[0].message)

    def test_official_catalog_declares_the_full_prompt_contract(self) -> None:
        catalog = json.loads((ROOT / "marketplace.json").read_text(encoding="utf-8"))

        covered = [skill for skill in catalog["skills"] if skill.get("examplePrompts")]
        self.assertEqual(len(covered), len(catalog["skills"]))
        for skill in covered:
            with self.subTest(skill=skill["name"]):
                self.assertGreaterEqual(len(skill["examplePrompts"]), 1)

        gated = {"Skills", "Studio", "Infrastructure"}
        required = [s for s in catalog["skills"] if s["category"] in gated]
        for skill in required:
            with self.subTest(skill=skill["name"]):
                self.assertTrue(skill.get("recovery"))
                self.assertIn(skill.get("undo"), ("single-step", "none", "manual"))

    def test_prompt_contract_runs_as_part_of_all(self) -> None:
        self.assertIn("prompt-contract", validate_marketplace.COMMANDS)

    def test_prompt_contract_accepts_a_complete_official_entry(self) -> None:
        skill = valid_skill()
        skill["examplePrompts"] = [
            "Build a biped rig from the current Maya guide and report every control",
            "Inspect which rigging modules are loaded in this Maya session",
        ]
        skill["recovery"] = [
            {
                "on": "mGear is not importable in the running Maya interpreter",
                "next": "dcc-mcp-cli marketplace inspect dcc-mcp-maya-mgear",
            },
            {
                "on": "a partially built rig is left in the scene",
                "next": "undo the build and delete the leftover rig group, then rebuild",
            },
        ]
        skill["undo"] = "single-step"
        catalog = {"name": "dcc-mcp-official", "schemaVersion": "1", "skills": [skill]}
        original = validate_marketplace.load_marketplace
        validate_marketplace.load_marketplace = lambda: catalog
        try:
            with contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertTrue(validate_marketplace.check_prompt_contract())
        finally:
            validate_marketplace.load_marketplace = original
        self.assertIn("Prompt contract check passed", output.getvalue())

    def test_prompt_contract_rejects_missing_example_prompts(self) -> None:
        skill = valid_skill()
        skill["undo"] = "single-step"
        skill["recovery"] = [{"on": "anything fails", "next": "dcc-mcp-cli marketplace list"}]
        catalog = {"name": "dcc-mcp-official", "schemaVersion": "1", "skills": [skill]}
        original = validate_marketplace.load_marketplace
        validate_marketplace.load_marketplace = lambda: catalog
        try:
            with contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertFalse(validate_marketplace.check_prompt_contract())
        finally:
            validate_marketplace.load_marketplace = original
        self.assertIn("must declare a non-empty examplePrompts array", output.getvalue())

    def test_prompt_contract_rejects_identifier_lists_and_duplicates(self) -> None:
        skill = valid_skill()
        skill["undo"] = "single-step"
        skill["recovery"] = [{"on": "anything fails", "next": "dcc-mcp-cli marketplace list"}]
        catalog = {"name": "dcc-mcp-official", "schemaVersion": "1", "skills": [skill]}
        original = validate_marketplace.load_marketplace
        validate_marketplace.load_marketplace = lambda: catalog
        try:
            skill["examplePrompts"] = ["maya-rig-tools, maya-render"]
            with contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertFalse(validate_marketplace.check_prompt_contract())
            self.assertIn("lists identifiers instead of a prompt", output.getvalue())

            skill["examplePrompts"] = ["rig the character now", "rig the character now"]
            with contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertFalse(validate_marketplace.check_prompt_contract())
            self.assertIn("duplicate examplePrompts entry", output.getvalue())

            skill["examplePrompts"] = ["rig"]
            with contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertFalse(validate_marketplace.check_prompt_contract())
            self.assertIn("too short", output.getvalue())
        finally:
            validate_marketplace.load_marketplace = original

    def test_prompt_contract_rejects_empty_recovery_next(self) -> None:
        skill = valid_skill()
        skill["examplePrompts"] = ["Build a biped rig from the current Maya guide"]
        skill["undo"] = "single-step"
        skill["recovery"] = [{"on": "the guide is invalid", "next": "   "}]
        catalog = {"name": "dcc-mcp-official", "schemaVersion": "1", "skills": [skill]}
        original = validate_marketplace.load_marketplace
        validate_marketplace.load_marketplace = lambda: catalog
        try:
            with contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertFalse(validate_marketplace.check_prompt_contract())
        finally:
            validate_marketplace.load_marketplace = original
        self.assertIn("has an empty 'next'", output.getvalue())

    def test_prompt_contract_rejects_no_op_recovery_next(self) -> None:
        skill = valid_skill()
        skill["examplePrompts"] = ["Build a biped rig from the current Maya guide"]
        skill["undo"] = "single-step"
        skill["recovery"] = [{"on": "the guide is invalid", "next": "retry"}]
        catalog = {"name": "dcc-mcp-official", "schemaVersion": "1", "skills": [skill]}
        original = validate_marketplace.load_marketplace
        validate_marketplace.load_marketplace = lambda: catalog
        try:
            with contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertFalse(validate_marketplace.check_prompt_contract())
        finally:
            validate_marketplace.load_marketplace = original
        self.assertIn("non-actionable 'next'", output.getvalue())

    def test_prompt_contract_requires_rollback_steps_for_manual_undo(self) -> None:
        skill = valid_skill()
        skill["examplePrompts"] = ["Build a biped rig from the current Maya guide"]
        skill["undo"] = "manual"
        skill["recovery"] = [
            {"on": "the guide is invalid", "next": "ask the user to fix the guide"}
        ]
        catalog = {"name": "dcc-mcp-official", "schemaVersion": "1", "skills": [skill]}
        original = validate_marketplace.load_marketplace
        validate_marketplace.load_marketplace = lambda: catalog
        try:
            with contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertFalse(validate_marketplace.check_prompt_contract())
            self.assertIn("must spell out the rollback step", output.getvalue())

            skill["recovery"].append(
                {
                    "on": "a partial rig is left behind",
                    "next": "delete the leftover rig group and rebuild",
                }
            )
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertTrue(validate_marketplace.check_prompt_contract())
        finally:
            validate_marketplace.load_marketplace = original

    def test_prompt_contract_rejects_unknown_undo_value(self) -> None:
        skill = valid_skill()
        skill["examplePrompts"] = ["Build a biped rig from the current Maya guide"]
        skill["undo"] = "automatic"
        skill["recovery"] = [
            {"on": "the guide is invalid", "next": "delete the rig group and rebuild"}
        ]
        catalog = {"name": "dcc-mcp-official", "schemaVersion": "1", "skills": [skill]}
        original = validate_marketplace.load_marketplace
        validate_marketplace.load_marketplace = lambda: catalog
        try:
            with contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertFalse(validate_marketplace.check_prompt_contract())
        finally:
            validate_marketplace.load_marketplace = original
        self.assertIn("has invalid undo value", output.getvalue())

    def test_prompt_contract_only_warns_for_asset_providers(self) -> None:
        skill = valid_skill()
        skill["category"] = "Asset Providers"
        skill["examplePrompts"] = ["Download a CC0 wooden crate model"]
        catalog = {"name": "dcc-mcp-official", "schemaVersion": "1", "skills": [skill]}
        original = validate_marketplace.load_marketplace
        validate_marketplace.load_marketplace = lambda: catalog
        try:
            with contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertTrue(validate_marketplace.check_prompt_contract())
        finally:
            validate_marketplace.load_marketplace = original
        self.assertIn("must declare a non-empty recovery array", output.getvalue())
        self.assertIn("must declare undo", output.getvalue())

    def test_schema_accepts_prompt_contract_fields(self) -> None:
        schema = json.loads((ROOT / "schemas" / "marketplace-v1.schema.json").read_text(encoding="utf-8"))
        skill = valid_skill()
        skill["examplePrompts"] = ["Build a biped rig from the current Maya guide"]
        skill["recovery"] = [
            {"on": "the guide is invalid", "next": "delete the rig group and rebuild"}
        ]
        skill["undo"] = "single-step"
        catalog = {
            "name": "dcc-mcp-official",
            "schemaVersion": "1",
            "version": "1.0.0",
            "skills": [skill],
        }
        from jsonschema import Draft202012Validator

        self.assertEqual(list(Draft202012Validator(schema).iter_errors(catalog)), [])

    def test_schema_rejects_unknown_undo_value(self) -> None:
        schema = json.loads((ROOT / "schemas" / "marketplace-v1.schema.json").read_text(encoding="utf-8"))
        catalog = {
            "name": "dcc-mcp-official",
            "schemaVersion": "1",
            "version": "1.0.0",
            "skills": [dict(valid_skill(), undo="automatic")],
        }
        from jsonschema import Draft202012Validator

        self.assertTrue(list(Draft202012Validator(schema).iter_errors(catalog)))

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
