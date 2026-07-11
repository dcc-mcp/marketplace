#!/usr/bin/env python3
"""DCC-MCP marketplace validation tool.

Usage:
    python scripts/validate_marketplace.py all --catalog ./marketplace.json
    python scripts/validate_marketplace.py schema        # JSON Schema validation
    python scripts/validate_marketplace.py uniqueness    # Duplicate name check
    python scripts/validate_marketplace.py metadata      # Required metadata and immutable refs
    python scripts/validate_marketplace.py reachability  # URL existence check
    python scripts/validate_marketplace.py source-revisions # Verify pinned git commits are advertised
    python scripts/validate_marketplace.py skill-layout  # Verify declared skill roots at pinned revisions
    python scripts/validate_marketplace.py asset-contract # Verify opted-in asset descriptor contracts
    python scripts/validate_marketplace.py source-freshness # Report upstream commits awaiting review
    python scripts/validate_marketplace.py catalog-parse # Validate via dcc-mcp-catalog
    python scripts/validate_marketplace.py all           # Run all checks (default)
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from base64 import b64decode
from collections import Counter
from pathlib import Path
from urllib.parse import quote, urlparse

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
        from jsonschema import Draft202012Validator, FormatChecker
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
        errors = sorted(
            Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(instance),
            key=lambda error: list(error.absolute_path),
        )
        if errors:
            exc = errors[0]
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
_SEMVER_PATTERN = re.compile(
    r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
    r"(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)
_GIT_SHA_PATTERN = re.compile(r"^[a-f0-9]{40}$")


def check_metadata_quality() -> bool:
    print("::group::Metadata quality check")
    data = load_marketplace()
    skills = data.get("skills", [])
    ok = True
    official_catalog = data.get("name") == "dcc-mcp-official"
    skill_names = {skill.get("name", "") for skill in skills}

    if data.get("schemaVersion") != "1":
        print("::error::Catalog must declare schemaVersion '1'")
        ok = False

    for skill in skills:
        name = skill.get("name", "")

        if not _NAME_PATTERN.match(name):
            print(f"::warning::Skill name '{name}' does not match kebab-case pattern")
            # Warning only — schema already enforces this

        dcc = skill.get("dcc", [])
        if not dcc:
            print(f"::error::Skill '{name}' has no dcc targets")
            ok = False

        tags = skill.get("tags", [])
        if not tags:
            print(f"::error::Skill '{name}' has no tags")
            ok = False

        category = skill.get("category", "")
        if category not in _VALID_CATEGORIES:
            print(f"::error::Skill '{name}' has invalid category: '{category}'")
            ok = False

        for field in ("version", "minCoreVersion"):
            value = skill.get(field, "")
            if not isinstance(value, str) or not _SEMVER_PATTERN.fullmatch(value):
                print(f"::error::Skill '{name}' has invalid {field}: '{value}'")
                ok = False

        source = skill.get("source", {})
        source_type = source.get("type", "")
        if source_type not in _VALID_SOURCE_TYPES:
            print(f"::error::Skill '{name}' has invalid source type: '{source_type}'")
            ok = False

        url = source.get("url", "")
        if not url:
            print(f"::error::Skill '{name}' has no source URL")
            ok = False

        ref = source.get("ref", "")
        sha256 = source.get("sha256", "")
        if source_type == "git" and not ref:
            print(f"::error::Skill '{name}' has no git source ref")
            ok = False
        if source_type == "zip" and not sha256:
            print(f"::error::Skill '{name}' has no zip source sha256")
            ok = False
        if official_catalog and source_type == "git" and not _GIT_SHA_PATTERN.fullmatch(ref):
            print(f"::error::Official skill '{name}' must pin source.ref to a 40-character commit SHA")
            ok = False

        skill_roots = source.get("skillRoots")
        if official_catalog and (not isinstance(skill_roots, list) or not skill_roots):
            print(f"::error::Official skill '{name}' must declare non-empty source.skillRoots")
            ok = False
        elif skill_roots is not None:
            for root in skill_roots:
                if not _is_safe_skill_root(root):
                    print(f"::error::Skill '{name}' has unsafe source.skillRoots entry: {root!r}")
                    ok = False

        policy = skill.get("policy", {})
        installation = policy.get("installation", "")
        if installation not in _VALID_POLICIES:
            print(f"::error::Skill '{name}' has invalid policy.installation: '{installation}'")
            ok = False

        lifecycle = skill.get("lifecycle", "active")
        replaced_by = skill.get("replacedBy")
        if lifecycle == "deprecated" and not replaced_by:
            print(f"::error::Deprecated skill '{name}' must declare replacedBy")
            ok = False
        elif replaced_by == name:
            print(f"::error::Skill '{name}' cannot replace itself")
            ok = False
        elif replaced_by and replaced_by not in skill_names:
            print(f"::error::Skill '{name}' replaces unknown skill '{replaced_by}'")
            ok = False

    if ok:
        print(f"Metadata quality check passed for {len(skills)} skills.")
    print("::endgroup::")
    return ok


def _is_safe_skill_root(value: object) -> bool:
    if not isinstance(value, str) or not value or value.startswith(("/", "\\")):
        return False
    parts = value.split("/")
    return all(part not in {"", ".", ".."} for part in parts)


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
            print(f"::error::NOT FOUND (404) {name}: {url}")
            errors.append((name, url, "HTTP 404"))
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


# ── pinned source revision checks ──────────────────────────────────────


def check_source_revisions() -> bool:
    print("::group::Pinned source revision check")
    data = load_marketplace()
    skills = data.get("skills", [])
    errors: list[tuple[str, str]] = []

    for skill in skills:
        source = skill.get("source", {})
        if source.get("type") != "git":
            continue
        name = skill.get("name", "?")
        url = source.get("url", "")
        ref = source.get("ref", "")
        if not _GIT_SHA_PATTERN.fullmatch(ref):
            errors.append((name, "git source ref is not a full commit SHA"))
            continue
        try:
            result = subprocess.run(
                ["git", "ls-remote", "--heads", "--tags", url],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            errors.append((name, f"could not inspect source: {exc}"))
            continue
        if result.returncode != 0:
            errors.append((name, result.stderr.strip() or "git ls-remote failed"))
            continue
        advertised_revisions = {line.split()[0].lower() for line in result.stdout.splitlines() if line}
        if ref.lower() not in advertised_revisions:
            errors.append((name, f"pinned commit {ref} is not advertised by a branch or tag"))
            continue
        print(f"  OK {name}: {ref}")

    for name, reason in errors:
        print(f"::error::{name}: {reason}")
    if errors:
        print("::endgroup::")
        return False
    print(f"Pinned source revision check passed for {len(skills)} skills.")
    print("::endgroup::")
    return True


# ── skill layout checks ────────────────────────────────────────────────


def _github_repo_slug(url: str) -> str | None:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.netloc.lower() != "github.com":
        return None
    parts = [part for part in parsed.path.strip("/").split("/") if part]
    if len(parts) != 2:
        return None
    owner, repo = parts
    if repo.endswith(".git"):
        repo = repo[:-4]
    return f"{owner}/{repo}" if owner and repo else None


def _skill_root_contains_skill(tree_paths: set[str], skill_root: str) -> bool:
    prefix = skill_root.rstrip("/") + "/"
    return any(
        path.startswith(prefix) and path.endswith("/SKILL.md")
        for path in tree_paths
    )


def _github_api_json(path: str) -> dict:
    request = urllib.request.Request(
        f"https://api.github.com/{path.lstrip('/')}"
    )
    request.add_header("Accept", "application/vnd.github+json")
    request.add_header("User-Agent", "dcc-mcp-marketplace-ci/1.0")
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def _github_tree_paths(repo: str, ref: str) -> set[str]:
    body = _github_api_json(f"repos/{repo}/git/trees/{ref}?recursive=1")
    if body.get("truncated"):
        raise ValueError("GitHub tree response was truncated")
    return {
        item["path"]
        for item in body.get("tree", [])
        if item.get("type") == "blob" and isinstance(item.get("path"), str)
    }


def _github_file_text(repo: str, ref: str, path: str) -> str:
    body = _github_api_json(
        f"repos/{repo}/contents/{quote(path, safe='/')}?ref={quote(ref, safe='')}"
    )
    if body.get("encoding") != "base64" or not isinstance(body.get("content"), str):
        raise ValueError(f"GitHub did not return base64 file content for {path}")
    return b64decode(body["content"]).decode("utf-8")


# ── asset descriptor contract checks ─────────────────────────────────


def check_asset_contract() -> bool:
    """Verify opted-in asset sources describe the import handoff contract."""
    print("::group::Asset descriptor contract check")
    errors: list[tuple[str, str]] = []
    checked = 0
    for skill in load_marketplace().get("skills", []):
        if skill.get("assetContract") != "descriptor-v1":
            continue
        name = skill.get("name", "?")
        source = skill.get("source", {})
        repo = _github_repo_slug(source.get("url", ""))
        ref = source.get("ref", "")
        roots = source.get("skillRoots", [])
        if source.get("type") != "git" or not repo or not _GIT_SHA_PATTERN.fullmatch(ref):
            errors.append((name, "descriptor-v1 requires a pinned HTTPS GitHub git source"))
            continue
        if not isinstance(roots, list) or not roots:
            errors.append((name, "descriptor-v1 requires source.skillRoots"))
            continue
        try:
            tool_specs = [_github_file_text(repo, ref, f"{root}/tools.yaml") for root in roots]
        except (OSError, ValueError, UnicodeDecodeError, urllib.error.URLError, urllib.error.HTTPError) as exc:
            errors.append((name, f"could not inspect pinned tools.yaml: {exc}"))
            continue
        has_contract = any(
            "asset_descriptor" in spec
            and "source_url" in spec
            and ("license_spdx" in spec or "license_text" in spec)
            for spec in tool_specs
        )
        if not has_contract:
            errors.append((name, "tools.yaml must declare asset_descriptor with source_url and license_spdx or license_text"))
            continue
        checked += 1
        print(f"  OK {name}: descriptor-v1")

    for name, reason in errors:
        print(f"::error::{name}: {reason}")
    if errors:
        print("::endgroup::")
        return False
    print(f"Asset descriptor contract check passed for {checked} skill(s).")
    print("::endgroup::")
    return True


# ── source freshness checks ───────────────────────────────────────────


def check_source_freshness() -> bool:
    """Report newer commits on official source default branches without changing pins."""
    print("::group::Official source freshness audit")
    data = load_marketplace()
    if data.get("name") != "dcc-mcp-official":
        print("Catalog is not official; skipping upstream freshness audit.")
        print("::endgroup::")
        return True

    errors: list[tuple[str, str]] = []
    fresh = 0
    stale = 0
    for skill in data.get("skills", []):
        source = skill.get("source", {})
        if source.get("type") != "git":
            continue
        name = skill.get("name", "?")
        ref = source.get("ref", "")
        repo = _github_repo_slug(source.get("url", ""))
        if not repo or not _GIT_SHA_PATTERN.fullmatch(ref):
            errors.append((name, "requires an HTTPS GitHub URL and full commit SHA"))
            continue
        try:
            default_branch = _github_api_json(f"repos/{repo}")["default_branch"]
            comparison = _github_api_json(
                f"repos/{repo}/compare/{ref}...{quote(default_branch, safe='')}"
            )
            ahead_by = comparison.get("ahead_by", 0)
        except (KeyError, OSError, ValueError, urllib.error.URLError, urllib.error.HTTPError) as exc:
            errors.append((name, f"could not compare pinned source with upstream: {exc}"))
            continue
        if ahead_by:
            stale += 1
            print(
                f"::warning::{name}: {default_branch} has {ahead_by} commit(s) after pinned {ref}"
            )
        else:
            fresh += 1
            print(f"  OK {name}: pinned revision matches {default_branch}")

    for name, reason in errors:
        print(f"::error::{name}: {reason}")
    print(f"Freshness audit: {fresh} current, {stale} awaiting review.")
    print("::endgroup::")
    return not errors


def check_skill_layout() -> bool:
    print("::group::Declared skill root layout check")
    data = load_marketplace()
    if data.get("name") != "dcc-mcp-official":
        print("Catalog is not official; skipping official GitHub skill layout checks.")
        print("::endgroup::")
        return True

    errors: list[tuple[str, str]] = []
    checked = 0
    for skill in data.get("skills", []):
        source = skill.get("source", {})
        if source.get("type") != "git":
            continue
        name = skill.get("name", "?")
        ref = source.get("ref", "")
        skill_roots = source.get("skillRoots", [])
        repo = _github_repo_slug(source.get("url", ""))
        if not repo:
            errors.append((name, "official git source must be an HTTPS GitHub repository URL"))
            continue
        if not _GIT_SHA_PATTERN.fullmatch(ref):
            errors.append((name, "source.ref is not a full commit SHA"))
            continue
        if not isinstance(skill_roots, list) or not skill_roots:
            errors.append((name, "source.skillRoots is missing"))
            continue
        try:
            paths = _github_tree_paths(repo, ref)
        except (OSError, ValueError, urllib.error.URLError, urllib.error.HTTPError) as exc:
            errors.append((name, f"could not inspect GitHub tree: {exc}"))
            continue
        missing = [root for root in skill_roots if not _skill_root_contains_skill(paths, root)]
        if missing:
            errors.append((name, f"declared skill roots contain no SKILL.md: {', '.join(missing)}"))
            continue
        checked += 1
        print(f"  OK {name}: {', '.join(skill_roots)}")

    for name, reason in errors:
        print(f"::error::{name}: {reason}")
    if errors:
        print("::endgroup::")
        return False
    print(f"Declared skill root layout check passed for {checked} git skills.")
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
    "source-revisions": check_source_revisions,
    "skill-layout": check_skill_layout,
    "asset-contract": check_asset_contract,
    "source-freshness": check_source_freshness,
    "catalog-parse": check_catalog_parse,
}


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Validate a DCC-MCP marketplace catalog.")
    parser.add_argument("mode", nargs="?", default="all")
    parser.add_argument("--catalog", type=Path, metavar="PATH")
    args = parser.parse_args()

    global MARKETPLACE_JSON
    if args.catalog:
        MARKETPLACE_JSON = args.catalog.resolve()
    mode = args.mode

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
