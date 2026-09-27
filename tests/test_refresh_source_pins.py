import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "refresh_source_pins.py"
SPEC = importlib.util.spec_from_file_location("refresh_source_pins", SCRIPT)
refresh = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(refresh)


class RefreshSourcePinsTests(unittest.TestCase):
    def test_refresh_updates_stale_pins_and_bumps_catalog_patch(self) -> None:
        old_ref = "a" * 40
        new_ref = "b" * 40
        catalog = {
            "name": "dcc-mcp-official",
            "version": "1.2.3",
            "skills": [{"name": "example", "source": {"type": "git", "url": "https://github.com/acme/example", "ref": old_ref}}],
        }

        def fetch(path: str) -> dict:
            return {
                "repos/acme/example": {"default_branch": "main"},
                f"repos/acme/example/compare/{old_ref}...main": {"ahead_by": 1},
                "repos/acme/example/commits/main": {"sha": new_ref},
            }[path]

        self.assertEqual(refresh.refresh_catalog(catalog, fetch), [("example", old_ref, new_ref)])
        self.assertEqual(catalog["version"], "1.2.4")
        self.assertEqual(catalog["skills"][0]["source"]["ref"], new_ref)

    def test_compare_failure_repins_the_dead_commit(self) -> None:
        old_ref = "a" * 40
        new_ref = "b" * 40
        catalog = {
            "name": "dcc-mcp-official",
            "version": "1.2.3",
            "skills": [{"name": "example", "source": {"type": "git", "url": "https://github.com/acme/example", "ref": old_ref}}],
        }

        def fetch(path: str) -> dict:
            if path == f"repos/acme/example/compare/{old_ref}...main":
                raise OSError("HTTP Error 404: Not Found")
            return {
                "repos/acme/example": {"default_branch": "main"},
                "repos/acme/example/commits/main": {"sha": new_ref},
            }[path]

        warnings: list[str] = []
        self.assertEqual(
            refresh.refresh_catalog(catalog, fetch, warnings.append),
            [("example", old_ref, new_ref)],
        )
        self.assertEqual(catalog["skills"][0]["source"]["ref"], new_ref)
        self.assertTrue(any("compare" in w for w in warnings), warnings)

    def test_unreachable_repo_skips_only_that_skill(self) -> None:
        old_ref = "a" * 40
        new_ref = "b" * 40
        catalog = {
            "name": "dcc-mcp-official",
            "version": "1.2.3",
            "skills": [
                {"name": "broken", "source": {"type": "git", "url": "https://github.com/acme/broken", "ref": old_ref}},
                {"name": "healthy", "source": {"type": "git", "url": "https://github.com/acme/healthy", "ref": old_ref}},
            ],
        }

        def fetch(path: str) -> dict:
            if path.startswith("repos/acme/broken"):
                raise OSError("HTTP Error 404: Not Found")
            return {
                "repos/acme/healthy": {"default_branch": "main"},
                f"repos/acme/healthy/compare/{old_ref}...main": {"ahead_by": 2},
                "repos/acme/healthy/commits/main": {"sha": new_ref},
            }[path]

        warnings: list[str] = []
        self.assertEqual(
            refresh.refresh_catalog(catalog, fetch, warnings.append),
            [("healthy", old_ref, new_ref)],
        )
        self.assertEqual(catalog["skills"][0]["source"]["ref"], old_ref)
        self.assertEqual(catalog["version"], "1.2.4")
        self.assertTrue(any("broken" in w for w in warnings))

    def test_apply_updates_changes_only_catalog_version_and_target_pin(self) -> None:
        old_ref = "a" * 40
        new_ref = "b" * 40
        original = '{\n  "name": "dcc-mcp-official",\n  "schemaVersion": "1",\n  "version": "1.2.3",\n  "skills": [{"name": "example", "source": {"ref": "' + old_ref + '"}}]\n}\n'
        updated = refresh.apply_updates(original, "1.2.3", "1.2.4", [("example", old_ref, new_ref)])
        self.assertIn('"version": "1.2.4"', updated)
        self.assertIn(f'"ref": "{new_ref}"', updated)


if __name__ == "__main__":
    unittest.main()
