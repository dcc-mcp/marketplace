# AGENTS.md — DCC-MCP Marketplace

> Navigation map, not a reference manual. Follow the links; don't read
> everything upfront.

The official DCC-MCP registry: plugin, bundle, and skill catalog metadata
for the ecosystem. Implementations live in their own Git repositories —
**this repository holds metadata only**, published and consumed through
`dcc-mcp-cli`.

---

## Repository Contract

**This is a data repository with no build step; validation is a set of
single-purpose checks driven from `scripts/`.**

| Task | Command |
|------|---------|
| Validate the whole catalog (parse) | `python scripts/validate_marketplace.py catalog-parse` |
| Check entry uniqueness | `python scripts/validate_marketplace.py uniqueness` |
| Check required metadata | `python scripts/validate_marketplace.py metadata` |
| Check the prompt contract | `python scripts/validate_marketplace.py prompt-contract` |
| Check that sources resolve | `python scripts/validate_marketplace.py reachability` |
| Check pinned source revisions | `python scripts/validate_marketplace.py source-revisions` |
| Check skill package layout | `python scripts/validate_marketplace.py skill-layout` |
| Check asset contracts | `python scripts/validate_marketplace.py asset-contract` |
| Refresh pinned source revisions | `python scripts/refresh_source_pins.py` |
| Run the script test suite | `python -m pytest tests/ -q` |

**Repository layout**

| Path | Role |
|------|------|
| `marketplace.json` | The catalog — every plugin, bundle, and skill entry |
| `marketplace.sigstore.json` | Sigstore provenance for catalog releases |
| `schemas/` | JSON Schema (`marketplace-v1.schema.json`) for catalog entries |
| `scripts/` | `validate_marketplace.py`, `refresh_source_pins.py` |
| `tests/` | pytest suite covering the validation scripts |
| `docs/`, `examples/` | Publishing guide and reference entries |

**Release flow** — Catalog entries are data, not versioned code — there is no `release-please`
here. Validate with `python scripts/validate_marketplace.py <check>` before
opening a PR; CI runs the same checks. `CONTRIBUTING.md` is the
authoritative publishing guide.

**Prohibitions**

- Do not add implementation code — catalog entries must point at their own Git repository.
- Do not hand-edit `marketplace.sigstore.json`.
- Do not add a second agent contract file at the repository root; `AGENTS.md` is the single source.
- Do not add an entry without running the validation scripts; CI runs the same checks.

---

## Agent Contract Files

`AGENTS.md` is the **only** agent contract file at the repository root. It is the
native instruction file for Codex, OpenCode, Cursor, GitHub Copilot, Windsurf,
Cline, Roo Code, Kiro, Trae, and Augment, and Claude Code falls back to it when
no `CLAUDE.md` exists — so do not add `CLAUDE.md`, `GEMINI.md`, `CURSOR.md`, or
any other vendor-specific variant.

**Gemini CLI exception:** Gemini CLI defaults its context file to `GEMINI.md`. To
make it read `AGENTS.md`, set `context.fileName` once in `~/.gemini/settings.json`:

```json
{
  "context": {
    "fileName": ["AGENTS.md", "GEMINI.md"]
  }
}
```
