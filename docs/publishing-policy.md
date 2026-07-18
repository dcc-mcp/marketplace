# Official Marketplace Publishing Policy

The official catalog is a curated installation contract, not a list of mutable repositories.

## Admission gate

Every official entry must provide a valid skill package, a supported DCC target, a minimum
Core version, an immutable Git commit pin, explicit skill roots, a maintainer, category, and
install policy. CI checks schema conformance, unique names, source reachability, that the
pinned commit is still advertised by the source repository, and that every `source.skillRoots`
directory contains a `SKILL.md` at that revision.

Packages that require credentials or external binaries must declare their variable and binary
names in `requires`; secrets must never appear in catalog metadata.

Use `showcase` for one repository-relative 16:9 workflow or result image. PNG, JPEG, WebP, AVIF,
and animated GIF are supported. The asset must exist at the pinned `source.ref`; clients resolve
it from the source repository without a separate CDN.

Asset-provider submissions must follow the [asset descriptor handoff](asset-descriptor-contract.md)
guide: download tools return a validated local-file descriptor with source and license attribution,
while DCC adapters own scene import.

Adapter-owned base skills are shipped and updated with their DCC adapter. Do not publish a
marketplace entry that duplicates an adapter's bundled skill directory; publish optional
extensions, asset providers, or studio tools instead.

## Release and rollback

Changing package content requires a new package version and a new `source.ref` commit pin.
The CLI records the resolved commit alongside the semantic version, allowing it to show a
revision-only update. Roll back by restoring the previous catalog commit and pin; never force
move a published source reference.

The scheduled source-refresh workflow may open a draft PR with newer immutable pins and a
catalog patch bump. It never merges that PR or changes an individual skill version: maintainers
review upstream compatibility and choose each skill's semantic version before merge.

## Lifecycle

Use `lifecycle: experimental` for packages still under evaluation. Mark superseded packages
as `deprecated` and set `replacedBy` to the successor package name. Do not silently remove a
package that may already be installed.

## Custom catalogs

Custom catalogs may use release tags when a studio manages the trust boundary. They do not
override official names by default; use a distinct package namespace or disable the default
source for a fully isolated deployment.
