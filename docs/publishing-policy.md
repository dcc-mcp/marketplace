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

## Release and rollback

Changing package content requires a new package version and a new `source.ref` commit pin.
The CLI records the resolved commit alongside the semantic version, allowing it to show a
revision-only update. Roll back by restoring the previous catalog commit and pin; never force
move a published source reference.

## Lifecycle

Use `lifecycle: experimental` for packages still under evaluation. Mark superseded packages
as `deprecated` and set `replacedBy` to the successor package name. Do not silently remove a
package that may already be installed.

## Custom catalogs

Custom catalogs may use release tags when a studio manages the trust boundary. They do not
override official names by default; use a distinct package namespace or disable the default
source for a fully isolated deployment.
