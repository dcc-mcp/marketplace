# `source-revisions`: assert-reachability

## Why

The check asserted that a pinned revision appears among the refs a source repo
advertises (`git ls-remote --heads --tags`). That is an assertion about the
**tip** of every branch and tag, not about the pinned revision.

The catalog deliberately pins immutable commit SHAs, and `freshness.yml`
deliberately reports newer upstream commits without moving those pins. So as
soon as a source repo merges one commit, its branch tip moves past the pin,
`ls-remote` stops advertising it, and the check reports the pinned revision as
missing — even though the revision is fully reachable from the default branch.

That is a false failure. It is the direct cause of the recurring red
`Dry-run smoke test`, and it recurs on every upstream merge.

## The rule now

`source-revisions` asserts that a pinned revision **resolves in the source
repository**. It no longer asserts that the pin is still a branch tip or tag.

| Outcome | Meaning | Result |
|---|---|---|
| Advertised by a branch or tag | pin is a tip — strongest case | pass |
| Not advertised, but resolves via history | pin drifted, still reachable | pass |
| Indeterminate (rate limit, 5xx, timeout, non-GitHub host) | cannot tell | pass + `::warning::` |
| Does not resolve in the source repo | genuinely missing | **fail** |

Drift is expected and non-blocking: `source-freshness` and the weekly
`freshness.yml` flow are the surfaces that report it. A pin that no longer
resolves at all is a real catalog defect and still fails.

## How reachability is resolved

1. `git ls-remote --heads --tags` — the pre-existing fast path. A hit here is
   conclusive and costs no further requests.
2. Otherwise, for GitHub sources, `GET /repos/{owner}/{repo}/compare/{ref}...HEAD`.
   A `200` proves the revision resolves (`status` is `identical`, `behind`,
   `ahead`, or `diverged`); `404` proves it does not. This is the same endpoint
   `source-freshness` already uses.
3. Otherwise, for non-GitHub hosts, `git fetch --depth=1 origin {ref}`. Success
   proves resolution; `not our ref` proves absence and **fails**. A server that
   refuses to serve arbitrary SHAs outright (it does not enable
   `allowReachableSHA1InWant`) is **indeterminate**: the refusal is a statement
   about server capability, not about the revision. Any other fetch failure —
   DNS, connection refused, auth, deleted repository — means the revision could
   not be resolved and **fails**, matching how an unreachable GitHub repo is
   treated.

## Rate limits

Unauthenticated GitHub REST allows 60 requests per hour per IP. With ~32 unique
`(url, ref)` pairs the check fits today but has no headroom as the catalog
grows, so the CI step passes `GITHUB_TOKEN` (5,000/hr), matching the
`skill-layout` and `asset-contract` steps. Results are cached per `(url, ref)`,
so the 41 entries that share 32 pairs cost 32 lookups, not 41.

A `403` is only treated as a rate limit when no token is configured. If a token
was sent, a `403` means the token cannot see the repository, which for the
official catalog is a real defect and fails.

## Loud-on-blind guard

If over half of the resolved pins come back indeterminate, the check prints a
prominent warning. Because every official-catalog entry is a commit pin, a
fully rate-limited run would otherwise be indistinguishable from a clean one.

## Discrimination

The change must not make the check permissive. `tests/test_validate_marketplace.py`
covers both directions:

- external pin drift → passes
- source repo genuinely unreachable / revision genuinely missing → still fails
