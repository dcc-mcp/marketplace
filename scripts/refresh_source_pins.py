#!/usr/bin/env python3
"""Prepare reviewed updates for official GitHub source pins."""

from __future__ import annotations

import argparse
import json
import os
import re
import urllib.request
from pathlib import Path
from typing import Callable
from urllib.parse import quote, urlparse


ROOT = Path(__file__).resolve().parent.parent
CATALOG = ROOT / "marketplace.json"
_GIT_SHA = re.compile(r"^[a-f0-9]{40}$")
_STABLE_SEMVER = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")


def github_repo_slug(url: str) -> str | None:
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


def github_json(path: str) -> dict:
    request = urllib.request.Request(f"https://api.github.com/{path.lstrip('/')}")
    request.add_header("Accept", "application/vnd.github+json")
    request.add_header("User-Agent", "dcc-mcp-marketplace-refresh/1.0")
    if token := os.environ.get("GITHUB_TOKEN"):
        request.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def bump_patch(version: str) -> str:
    match = _STABLE_SEMVER.fullmatch(version)
    if not match:
        raise ValueError(f"catalog version must be a stable semver: {version}")
    major, minor, patch = match.groups()
    return f"{major}.{minor}.{int(patch) + 1}"


def refresh_catalog(catalog: dict, fetch: Callable[[str], dict]) -> list[tuple[str, str, str]]:
    if catalog.get("name") != "dcc-mcp-official":
        raise ValueError("only the official catalog can refresh source pins")

    changes: list[tuple[str, str, str]] = []
    for skill in catalog.get("skills", []):
        source = skill.get("source", {})
        ref = source.get("ref", "")
        repo = github_repo_slug(source.get("url", ""))
        if source.get("type") != "git" or not repo or not _GIT_SHA.fullmatch(ref):
            continue

        default_branch = fetch(f"repos/{repo}").get("default_branch")
        if not isinstance(default_branch, str) or not default_branch:
            raise ValueError(f"{skill.get('name', '?')}: source has no default branch")
        comparison = fetch(f"repos/{repo}/compare/{ref}...{quote(default_branch, safe='')}")
        if not comparison.get("ahead_by", 0):
            continue
        target = fetch(f"repos/{repo}/commits/{quote(default_branch, safe='')}").get("sha", "")
        if not isinstance(target, str) or not _GIT_SHA.fullmatch(target):
            raise ValueError(f"{skill.get('name', '?')}: default branch has no commit SHA")
        source["ref"] = target
        changes.append((skill.get("name", "?"), ref, target))

    if changes:
        catalog["version"] = bump_patch(catalog.get("version", ""))
    return changes


def apply_updates(text: str, old_version: str, new_version: str, changes: list[tuple[str, str, str]]) -> str:
    updated, count = re.subn(
        r'(\{\s*"name": "dcc-mcp-official",\s*"schemaVersion": "1",\s*"version": ")' + re.escape(old_version) + r'(")',
        r"\g<1>" + new_version + r"\g<2>",
        text,
        count=1,
    )
    if count != 1:
        raise ValueError("could not update catalog version")
    for name, old_ref, new_ref in changes:
        pattern = r'("name": "' + re.escape(name) + r'"[\s\S]*?"ref": ")' + re.escape(old_ref) + r'(")'
        updated, count = re.subn(pattern, r"\g<1>" + new_ref + r"\g<2>", updated, count=1)
        if count != 1:
            raise ValueError(f"could not update source pin for {name}")
    return updated


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare official marketplace source-pin refreshes.")
    parser.add_argument("--write", action="store_true", help="write refreshed pins to marketplace.json")
    args = parser.parse_args()

    original = CATALOG.read_text(encoding="utf-8")
    catalog = json.loads(original)
    old_version = catalog.get("version", "")
    changes = refresh_catalog(catalog, github_json)
    if not changes:
        print("No source-pin updates available.")
        return 0

    for name, old_ref, new_ref in changes:
        print(f"{name}: {old_ref} -> {new_ref}")
    print(f"catalog: {old_version} -> {catalog['version']}")
    if args.write:
        CATALOG.write_text(apply_updates(original, old_version, catalog["version"], changes), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
