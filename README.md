# DCC-MCP Marketplace

Official skill registry for the [DCC-MCP](https://github.com/dcc-mcp/dcc-mcp-core) ecosystem.

Publish, discover, install, and upgrade DCC-MCP skill packs through **`dcc-mcp-cli`**. Metadata lives in this repo; skill implementations live in their own Git repositories.

## Design references

- [ClawHub](https://github.com/openclaw/clawhub) — skill registry + CLI install/update/pin flows
- [Codex marketplace metadata](https://developers.openai.com/codex/plugins/build#marketplace-metadata) — curated catalog JSON, multi-source `marketplace add`, git-backed entries

## Install layout

Installed skills land at:

```text
~/.dcc-mcp/marketplace/<dcc>/<name>/
```

Example:

```text
~/.dcc-mcp/marketplace/maya/dcc-asset-hunyuan-download/
~/.dcc-mcp/marketplace/blender/dcc-asset-polyhaven/
```

After install, `dcc-mcp-cli` registers the path with the running adapter and triggers a skill reload.

## CLI (planned in dcc-mcp-core)

All marketplace operations go through **`dcc-mcp-cli`**, not Admin UI directly. Admin may shell out to the CLI or display its JSON output.

```bash
# Register marketplace sources (official + custom)
dcc-mcp-cli marketplace add dcc-mcp/marketplace
dcc-mcp-cli marketplace add https://github.com/my-studio/private-marketplace.git --ref main
dcc-mcp-cli marketplace list

# Discover
dcc-mcp-cli marketplace search --query hunyuan --dcc maya
dcc-mcp-cli marketplace inspect dcc-asset-hunyuan-download

# Install / upgrade / remove
dcc-mcp-cli marketplace install dcc-asset-hunyuan-download --dcc maya
dcc-mcp-cli marketplace update --all
dcc-mcp-cli marketplace list-installed
dcc-mcp-cli marketplace uninstall dcc-asset-hunyuan-download --dcc maya
```

Default official source URL:

```text
https://raw.githubusercontent.com/dcc-mcp/marketplace/main/marketplace.json
```

Environment overrides:

| Variable | Purpose |
|----------|---------|
| `DCC_MCP_MARKETPLACE_SOURCES` | Comma-separated extra catalog URLs or `owner/repo` shorthands |
| `DCC_MCP_MARKETPLACE_INSTALL_ROOT` | Override install root (default `~/.dcc-mcp/marketplace`) |

## Catalog format

Primary index: [`marketplace.json`](marketplace.json)

JSON schema: [`schemas/marketplace-v1.schema.json`](schemas/marketplace-v1.schema.json)

Each skill entry includes:

- Identity: `name`, `description`, `version`, `maintainer`
- Targeting: `dcc[]`, `tags[]`, `category`, `minCoreVersion`
- Source: `source.type` (`git` | `zip`), `source.url`, `source.ref` or `source.sha256`, and `source.skillRoots`
- Policy: `policy.installation` (`available` | `installed_by_default` | `not_available`)
- Optional runtime hints: `requires.env`, `requires.bins` (ClawHub-style)

Official entries use a full 40-character Git commit in `source.ref`. The CLI records that
resolved commit in local install state, so an update can be detected even when an entry's
semantic version is unchanged. Branch names such as `main` are intentionally not accepted
in the official catalog; use an immutable commit pin and publish a new catalog version to
roll out a newer package revision.

Official entries also declare every installable directory in `source.skillRoots`. The CLI
installs only those directories, keeping repository examples and development-only skills out
of users' local skill paths. CI verifies that each declared root contains a `SKILL.md` at the
pinned revision.

## Publishing a skill

1. Create a standalone skill repo with a valid `SKILL.md` + `tools.yaml`.
2. Open a PR adding an entry to `marketplace.json`.
3. CI validates the JSON schema, metadata policy, source URL, immutable Git pin, and declared
   skill-root layout.
4. After merge, users can `marketplace install <name>`.

See [CONTRIBUTING.md](CONTRIBUTING.md).

## Relationship to dcc-mcp-core

| Component | Role |
|-----------|------|
| **This repo** | Curated marketplace metadata (what can be installed) |
| **Skill repos** | Actual `SKILL.md` packages (what gets cloned) |
| **dcc-mcp-cli** | Search, install, update, list-installed |
| **dcc-mcp-core gateway** | `gateway://catalog` may mirror this index read-only; install stays CLI-first |

Legacy `dcc-mcp-core/dcc-mcp-catalog.yml` will redirect to this repo over time.
