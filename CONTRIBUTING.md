# Contributing to DCC-MCP Marketplace

## Adding a skill entry

1. Fork this repository.
2. Add a JSON object under `skills[]` in `marketplace.json`; preserve `schemaVersion: "1"`.
3. Pin a Git source to its complete 40-character commit SHA. The pin must still be advertised by a branch or tag in the source repository.
4. Run `python scripts/validate_marketplace.py all` locally.
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
- [ ] Official `source.ref` is a complete immutable commit SHA, never a branch name
- [ ] `requires.env` / `requires.bins` declared when the skill needs secrets or binaries
- [ ] The pinned repository revision contains a valid `SKILL.md` and any referenced `tools.yaml`

## Custom marketplace sources

Studios can fork this repo or publish a private `marketplace.json` and register it:

```bash
dcc-mcp-cli marketplace add https://github.com/my-studio/dcc-marketplace.git --ref main
```

Merge rules (implemented in CLI):

1. Official `dcc-mcp/marketplace` is always registered unless explicitly disabled.
2. Custom sources append entries; duplicate names resolve to the first configured source. With default configuration this means official entries win.
3. Do not rely on name collisions for overrides. Publish studio packages in a namespace such as `studio-maya-rig-tools`, or explicitly disable the default source for an isolated catalog.

## Version bumps

- Patch: fix metadata typos, update `source.ref` pin
- Minor: new skill entry
- Major: breaking schema changes (coordinate with dcc-mcp-core release)
