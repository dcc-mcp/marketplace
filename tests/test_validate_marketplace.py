import contextlib
import importlib.util
import io
import json
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


if __name__ == "__main__":
    unittest.main()
