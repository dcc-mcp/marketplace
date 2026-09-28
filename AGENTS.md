# AGENTS.md — DCC-MCP Marketplace

> Official plugin, bundle, and skill registry for the DCC-MCP ecosystem. **Metadata lives here; implementations live in their own Git repositories.**
> Navigation map for AI agents, not a reference manual. Catalog field reference and publishing rules live in `README.md` and `docs/`.

## Repo shape — read this first

This is a **data-only catalog repository**. There is no `pyproject.toml`, no Python package, no `justfile`, and no build step. The deliverable is `marketplace.json`, validated by the Python scripts under `scripts/`.

If you were looking for source code of a skill or adapter, you are in the wrong repo — follow an entry's `source.url` instead.

## Build & test

CI runs everything on Python 3.12. No justfile — do not invent `vx just` recipes here.

```bash
pip install check-jsonschema
check-jsonschema --schemafile schemas/marketplace-v1.schema.json marketplace.json
for f in examples/*.json; do check-jsonschema --schemafile schemas/marketplace-v1.schema.json "$f"; done

pip install jsonschema
python scripts/validate_marketplace.py uniqueness
python scripts/validate_marketplace.py metadata
python scripts/validate_marketplace.py prompt-contract
python -m unittest discover -s tests -p "test_*.py"

# Network-backed smoke checks (skill-layout and asset-contract need GITHUB_TOKEN)
python scripts/validate_marketplace.py reachability
python scripts/validate_marketplace.py source-revisions
python scripts/validate_marketplace.py skill-layout
python scripts/validate_marketplace.py asset-contract
python scripts/validate_marketplace.py catalog-parse
```

`scripts/validate_marketplace.py` takes a mode and defaults to **all** modes. Available modes: `schema`, `uniqueness`, `metadata`, `reachability`, `source-revisions`, `skill-layout`, `asset-contract`, `prompt-contract`, `source-freshness`, `catalog-parse`. Pass `--catalog PATH` to validate a catalog other than the default `marketplace.json`.

## Repo layout

| Path | Role |
|---|---|
| `marketplace.json` | The catalog — the primary index read by `dcc-mcp-cli` and the public site |
| `marketplace.sigstore.json` | Sigstore attestation bundle for the catalog |
| `schemas/marketplace-v1.schema.json` | JSON Schema (draft 2020-12) every entry must satisfy |
| `scripts/validate_marketplace.py` | Validator CLI — the 10 modes above plus `all` |
| `scripts/refresh_source_pins.py` | Refreshes immutable source pins for the weekly freshness flow |
| `tests/` | unittest suite for the validator scripts |
| `docs/` | `prompt-contract.md`, `publishing-policy.md`, `asset-descriptor-contract.md`, `bundled-skill-migration.md`, `readme-showcase-guide.md`, `game-demo-asset-coverage.md` |
| `examples/custom-studio-marketplace.json` | Template for a private/studio marketplace |

## Catalog rules that CI enforces

- **Immutable pins only.** Official entries use a full 40-character Git commit in `source.ref`. Branch names such as `main` are not accepted — publish a new catalog version to roll out a newer revision.
- **`examplePrompts[]` is required on every entry.** `Skills`, `Studio`, and `Infrastructure` entries must also ship `recovery[]` and `undo`. See `docs/prompt-contract.md`.
- **`source.skillRoots` declares every installable directory.** CI verifies each declared root contains a `SKILL.md` at the pinned revision; the CLI installs only those directories.
- **`showcase` must be a repository-relative image path** (PNG/JPEG/WebP/AVIF/GIF, 16:9). It resolves against the immutable `source.ref` — never a mutable CDN URL.
- **New entries ship `examplePrompts` before merge.** See `CONTRIBUTING.md`.

## Release

- **There is no release-please or version automation in this repo.** No `.release-please-manifest.json`, no release workflow, no PyPI publish.
- Shipping a change is a pull request to `marketplace.json`; CI validates schema, metadata policy, source URL, immutable Git pin, and declared skill-root layout before merge.
- Every `marketplace.json` revision on `main` receives a GitHub Artifact Attestation signed through the public Sigstore service (`.github/workflows/attest-catalog.yml`). Verify a downloaded catalog with:

```bash
gh attestation verify marketplace.json --repo dcc-mcp/marketplace
```

- `freshness.yml` reports official source branches with newer commits every Monday; it never changes a pin automatically. `source-refresh.yml` can prepare a draft PR with refreshed pins and one catalog patch bump; it never auto-merges.

## Do / Don't

- **Do** single-source agent instructions here. This is the only agent contract file at the repo root.
- **Do** read `docs/publishing-policy.md` and `docs/prompt-contract.md` before adding or editing an entry.
- **Don't** add `CLAUDE.md` / `GEMINI.md` / `CURSOR.md` / `ANTHROPIC.md` / `OPENAI.md` / `COPILOT.md` / `CODEBUDDY.md` / `.cursorrules` / `.clinerules` / `.windsurfrules` at the root. Vendor-specific notes live under `docs/integrations/`, linked from here.
- **Don't** add skill implementations, `SKILL.md` files, or `scripts/`-style tool code to this repo — catalog entries only.
- **Don't** commit build artifacts or validator scratch output to the repo root.
