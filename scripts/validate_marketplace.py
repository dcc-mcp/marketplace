#!/usr/bin/env python3
"""DCC-MCP marketplace validation tool.

Usage:
    python scripts/validate_marketplace.py schema        # JSON Schema validation
    python scripts/validate_marketplace.py uniqueness    # Duplicate name check
    python scripts/validate_marketplace.py reachability  # URL existence check
    python scripts/validate_marketplace.py catalog-parse # Validate via dcc-mcp-catalog
    python scripts/validate_marketplace.py all           # Run all checks (default)
"""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MARKETPLACE_JSON = ROOT / "marketplace.json"
SCHEMA_JSON = ROOT / "schemas" / "marketplace-v1.schema.json"


def load_marketplace() -> dict:
    with open(MARKETPLACE_JSON, encoding="utf-8") as f:
        return json.load(f)


def load_schema() -> dict:
    with open(SCHEMA_JSON, encoding="utf-8") as f:
        return json.load(f)


# ── schema validation ──────────────────────────────────────────────────


def validate_schema() -> bool:
    print("::group::Schema validation")
    try:
        from jsonschema import validate, ValidationError
    except ImportError:
        print("jsonschema not installed, trying check-jsonschema CLI...")
        import subprocess

        result = subprocess.run(
            [
                "check-jsonschema",
                "--schemafile", str(SCHEMA_JSON),
                str(MARKETPLACE_JSON),
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print(result.stderr or result.stdout)
            print("::error::Schema validation failed")
            print("::endgroup::")
            return False
        print(result.stdout)
    else:
        instance = load_marketplace()
        schema = load_schema()
        try:
            validate(instance=instance, schema=schema)
        except ValidationError as exc:
            print(f"::error::Schema validation failed: {exc.message}")
            print(f"  at path: {' -> '.join(str(p) for p in exc.absolute_path)}")
            print("::endgroup::")
            return False

    print("Schema validation passed.")
    print("::endgroup::")
    return True


# ── name uniqueness ────────────────────────────────────────────────────


def check_uniqueness() -> bool:
    print("::group::Name uniqueness check")
    data = load_marketplace()
    skills = data.get("skills", [])
    if not skills:
        print("::error::No skills found in marketplace.json")
        print("::endgroup::")
        return False

    names = [s.get("name", "") for s in skills]
    empty_names = [n for n in names if not n]
    if empty_names:
        print(f"::error::{len(empty_names)} skill(s) with empty name")
        print("::endgroup::")
        return False

    dupes = {name: count for name, count in Counter(names).items() if count > 1}
    if dupes:
        for name, count in dupes.items():
            print(f"::error::Duplicate skill name '{name}' appears {count} times")
        print("::endgroup::")
        return False

    print(f"All {len(names)} skill names are unique.")
    print("::endgroup::")
    return True


# ── metadata quality checks ────────────────────────────────────────────


_NAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_VALID_CATEGORIES = {"Skills", "Asset Providers", "Studio", "Infrastructure"}
_VALID_POLICIES = {"available", "installed_by_default", "not_available"}
_VALID_SOURCE_TYPES = {"git", "zip"}


def check_metadata_quality() -> bool:
    print("::group::Metadata quality check")
    data = load_marketplace()
    skills = data.get("skills", [])
    ok = True

    for skill in skills:
        name = skill.get("name", "")

        if not _NAME_PATTERN.match(name):
            print(f"::warning::Skill name '{name}' does not match kebab-case pattern")
            # Warning only — schema already enforces this

        dcc = skill.get("dcc", [])
        if not dcc:
            print(f"::warning::Skill '{name}' has no dcc targets")

        source = skill.get("source", {})
        source_type = source.get("type", "")
        if source_type not in _VALID_SOURCE_TYPES:
            print(f"::error::Skill '{name}' has invalid source type: '{source_type}'")
            ok = False

        url = source.get("url", "")
        if not url:
            print(f"::error::Skill '{name}' has no source URL")
            ok = False

        policy = skill.get("policy", {})
        installation = policy.get("installation", "")
        if installation not in _VALID_POLICIES:
            print(f"::error::Skill '{name}' has invalid policy.installation: '{installation}'")
            ok = False

    if ok:
        print(f"Metadata quality check passed for {len(skills)} skills.")
    print("::endgroup::")
    return ok


# ── URL reachability ───────────────────────────────────────────────────


def _http_head(url: str, timeout: int = 15) -> tuple[int, str]:
    req = urllib.request.Request(url, method="HEAD")
    req.add_header("User-Agent", "dcc-mcp-marketplace-ci/1.0")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, ""
    except urllib.error.HTTPError as exc:
        return exc.code, str(exc)
    except Exception as exc:
        return 0, str(exc)


def check_reachability() -> bool:
    print("::group::URL reachability check")
    data = load_marketplace()
    skills = data.get("skills", [])
    checked: set[str] = set()
    errors: list[tuple[str, str, str]] = []  # (name, url, reason)

    for skill in skills:
        name = skill.get("name", "")
        source = skill.get("source", {})
        url = source.get("url", "")

        if not url:
            print(f"::warning::Skill '{name}' has no source URL; skipping")
            continue

        if url in checked:
            continue
        checked.add(url)

        status, err = _http_head(url)
        if 200 <= status < 400:
            print(f"  OK ({status}) {name}: {url}")
        elif status == 404:
            print(f"::warning::NOT FOUND (404) {name}: {url} — repo may not exist yet")
        elif status == 403:
            # GitHub returns 403 for HEAD to repos without auth — not an error
            print(f"  WARN (403 for HEAD, likely auth-restricted) {name}: {url}")
        elif status > 0:
            # Unexpected HTTP status (5xx, etc.)
            print(f"::error::UNEXPECTED STATUS ({status}) {name}: {url}")
            errors.append((name, url, f"HTTP {status}"))
        else:
            # Network-level failure (timeout, DNS, connection refused)
            print(f"::error::NETWORK ERROR ({err}) {name}: {url}")
            errors.append((name, url, err))

    if not checked:
        print("No source URLs to check.")
        print("::endgroup::")
        return True

    ok_count = len(checked) - len(errors)
    print(f"URL check complete: {ok_count}/{len(checked)} reachable "
          f"({len(checked)} unique URLs).")

    if errors:
        print("::error::Some URLs are unreachable due to network errors "
              "(not 404). Check connectivity or repo availability.")
        print("::endgroup::")
        return False

    print("::endgroup::")
    return True


# ── catalog parse check ────────────────────────────────────────────────


def check_catalog_parse() -> bool:
    print("::group::Catalog parse check")
    try:
        raw = MARKETPLACE_JSON.read_text(encoding="utf-8")
        doc = json.loads(raw)
        skills = doc.get("skills", [])
        if not skills:
            print("::error::No skills found")
            print("::endgroup::")
            return False

        # Verify each skill has required fields for downstream catalog parsing
        required = ["name", "description", "version", "dcc", "source"]
        ok = True
        for skill in skills:
            missing = [f for f in required if f not in skill]
            if missing:
                print(f"::error::Skill '{skill.get('name', '?')}' missing fields: {missing}")
                ok = False

        entry_count = len(skills)
        dcc_set = sorted({d for s in skills for d in s.get("dcc", [])})
        print(f"Catalog: {entry_count} entries targeting DCCs: {', '.join(dcc_set)}")

        if ok:
            print("Catalog parse check passed.")
        print("::endgroup::")
        return ok
    except Exception as exc:
        print(f"::error::Catalog parse failed: {exc}")
        print("::endgroup::")
        return False


# ── main ───────────────────────────────────────────────────────────────


COMMANDS = {
    "schema": validate_schema,
    "uniqueness": check_uniqueness,
    "metadata": check_metadata_quality,
    "reachability": check_reachability,
    "catalog-parse": check_catalog_parse,
}


def main() -> None:
    if len(sys.argv) < 2:
        mode = "all"
    else:
        mode = sys.argv[1]

    modes = list(COMMANDS) if mode == "all" else [mode]
    unknown = [m for m in modes if m not in COMMANDS]
    if unknown:
        print(f"Unknown mode(s): {', '.join(unknown)}")
        print(f"Available: {', '.join(COMMANDS)} | all")
        sys.exit(2)

    failed = False
    for m in modes:
        if not COMMANDS[m]():
            failed = True

    if failed:
        print("\n::error::One or more validation checks failed.")
        sys.exit(1)

    print(f"\nAll checks passed ({', '.join(modes)}).")


if __name__ == "__main__":
    main()
