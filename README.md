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
Base skills bundled with a DCC adapter are already available; the marketplace is for optional
extensions, asset providers, and studio tools. See the [migration guide](docs/bundled-skill-migration.md)
if an older marketplace copy of a bundled skill is installed.

## CLI

**`dcc-mcp-cli`** is the primary marketplace interface. The Gateway Admin panel
uses the same marketplace service, so both surfaces share catalog and install
behavior.

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

Every Monday, the `marketplace-freshness` workflow reports official source branches with newer
commits. It never changes a pin automatically; maintainers review the source, then publish a new
catalog version and immutable commit pin.

The `marketplace-source-refresh` workflow can prepare that review as a draft PR with refreshed
pins and one catalog patch bump. It never auto-merges or chooses an individual skill version.

## Publishing a skill

1. Copy [`examples/custom-studio-marketplace.json`](examples/custom-studio-marketplace.json) and
   replace its placeholder identity, source, and `source.skillRoots` values.
2. Create a skill repo with a valid `SKILL.md` + `tools.yaml` at the declared root.
3. Open a PR adding the completed entry to `marketplace.json`.
4. CI validates the JSON schema, metadata policy, source URL, immutable Git pin, and declared
   skill-root layout.
5. After merge, users can `marketplace install <name>`.

See [CONTRIBUTING.md](CONTRIBUTING.md).

Asset-provider authors: follow the [asset descriptor handoff guide](docs/asset-descriptor-contract.md)
to keep download, licensing, attribution, and DCC import responsibilities separate. For original,
license-safe README renders, use the [showcase guide](docs/readme-showcase-guide.md).

## Relationship to dcc-mcp-core

| Component | Role |
|-----------|------|
| **This repo** | Curated marketplace metadata (what can be installed) |
| **Skill repos** | Actual `SKILL.md` packages (what gets cloned) |
| **dcc-mcp-cli** | Search, install, update, list-installed |
| **dcc-mcp-core gateway** | `gateway://catalog` may mirror this index read-only; install stays CLI-first |

Legacy `dcc-mcp-core/dcc-mcp-catalog.yml` will redirect to this repo over time.
