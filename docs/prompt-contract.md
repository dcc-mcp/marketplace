# Prompt contract

Every marketplace entry carries three optional fields that tell an agent how to
reach for the skill, what to do when it fails, and what the skill leaves behind.
They are metadata only — the marketplace never executes them.

```json
{
  "examplePrompts": [
    "Render a 24-frame PBR turntable of the selected asset with a studio HDR and export it to /tmp/turntable.mp4"
  ],
  "recovery": [
    {
      "on": "no renderable camera exists in the scene",
      "next": "dcc-mcp-cli marketplace inspect dcc-lookdev-turntable"
    }
  ],
  "undo": "single-step"
}
```

## `examplePrompts`

Natural-language prompts an agent can hand to the skill. This is the field that
decides whether an agent picks the entry up at all, so write prompts a user
would actually say, not a list of tool names.

- Required on **every** entry, including Asset Providers.
- One or more entries; the official catalog ships three per entry.
- Each entry must be a sentence: at least 8 characters, containing whitespace,
  and not just a comma- or pipe-separated list of identifiers.
- Entries must be unique within an entry.

## `recovery`

Ordered `{ "on", "next" }` rules describing what to do when the skill fails.

- `on` names the observable failure, for example `no renderable camera`.
- `next` is something the agent can actually do: another catalog entry name, a
  `dcc-mcp-cli` command, or a described user action. Bare `retry` is rejected —
  it tells the agent to spin without changing anything.
- Required on entries whose `category` is `Skills`, `Studio`, or
  `Infrastructure` — the ones that mutate a scene or an external system.
- Recommended but **not** required on `Asset Providers`; their dominant failure
  mode is an unreachable download source, so the validator only warns.

## `undo`

How much of the skill's work can be taken back.

| Value | Meaning |
|-------|---------|
| `single-step` | The host rolls the whole operation back with one undo step. |
| `manual` | Rollback needs explicit steps; spell them out in `recovery`. |
| `none` | Nothing host-side to undo, but say so explicitly in `recovery`. |

Required on the same categories as `recovery`. When the value is `manual` or
`none`, at least one `recovery` rule must mention the rollback — `undo`,
`rollback`, `revert`, `restore`, `reset`, `remove`, `delete`, or `discard`. A
read-only entry satisfies this by stating there is nothing to undo.

## Enforcing locally

```bash
python scripts/validate_marketplace.py prompt-contract
```

The check is part of `all`, so `python scripts/validate_marketplace.py all`
covers it too. CI runs it in the **Metadata policy checks** job.
