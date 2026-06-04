# Contributing to DCC-MCP Marketplace

## Adding a skill entry

1. Fork this repository.
2. Add a JSON object under `skills[]` in `marketplace.json`.
3. Ensure the skill repo is public and tagged (use `source.ref` for a release tag when stable).
4. Run schema validation locally (once CI lands) or validate manually against `schemas/marketplace-v1.schema.json`.
5. Open a PR with:
   - Entry diff
   - Link to the skill repo
   - One-line test note (`dcc-mcp-cli marketplace install …` expected path)

## Entry checklist

- [ ] `name` is unique and kebab-case
- [ ] `description` explains agent-facing value in one sentence
- [ ] `dcc[]` lists every supported host (do not default to Maya-only)
- [ ] `tags` include `domain` or `infrastructure` per DCC-MCP skill taxonomy
- [ ] `minCoreVersion` matches the lowest tested dcc-mcp-core release
- [ ] `source.url` points to the canonical Git repo
- [ ] `requires.env` / `requires.bins` declared when the skill needs secrets or binaries

## Custom marketplace sources

Studios can fork this repo or publish a private `marketplace.json` and register it:

```bash
dcc-mcp-cli marketplace add https://github.com/my-studio/dcc-marketplace.git --ref main
```

Merge rules (implemented in CLI):

1. Official `dcc-mcp/marketplace` is always registered unless explicitly disabled.
2. Custom sources append entries; duplicate `name` values resolve by source priority (custom wins with a warning, or require unique names — TBD in core PR).

## Version bumps

- Patch: fix metadata typos, update `source.ref` pin
- Minor: new skill entry
- Major: breaking schema changes (coordinate with dcc-mcp-core release)
