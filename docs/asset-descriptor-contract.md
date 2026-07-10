# Asset descriptor handoff

Asset-provider skills find and download files. DCC adapter skills import files into the active
scene. Keep those jobs separate by returning the shared `AssetDescriptor` contract after every
download.

## Source-skill output

Return an `asset_descriptor` field from each download tool. It must contain a stable `asset_id`,
at least one local file variant, and attribution with the original source URL plus either an SPDX
license identifier or license text.

```json
{
  "asset_descriptor": {
    "asset_id": "provider:asset-123",
    "variants": [{
      "local_path": "/workspace/downloads/asset.glb",
      "format": "glb",
      "preferred": true
    }],
    "attribution": {
      "source_url": "https://provider.example/assets/asset-123",
      "license_spdx": "CC-BY-4.0",
      "author": "Asset author",
      "attribution_text": "Asset author — CC BY 4.0"
    }
  }
}
```

Construct the descriptor with `dcc_mcp_core.asset_import.AssetDescriptor` and call
`descriptor.validate()` before returning it. Validation rejects missing local paths, source URLs,
and license data. Preserve provider-specific download data in `extra`; do not replace the shared
fields.

Declare the same `asset_descriptor` field in the download tool's `output_schema`. Search and
inspect tools should expose the source URL and license/usage data needed to build that descriptor.

## DCC handoff

Pass the returned descriptor unchanged to an adapter import skill as the `descriptor` field of an
`ImportToSceneRequest`. The adapter owns namespace, materials, placement, and host API calls;
the source skill must not import into a DCC directly.

```json
{
  "descriptor": { "asset_id": "provider:asset-123", "variants": ["..."] },
  "material_mode": "as_authored",
  "target_collection": "DownloadedAssets",
  "skip_existing": true
}
```

The adapter returns `ImportToSceneResult` with created nodes and warnings. Carry attribution into
the scene or its import metadata so users can retain source and license information.

## Submission checklist

- Download output contains a validated `asset_descriptor`.
- The descriptor has a local path, source URL, and license text or SPDX identifier.
- `tools.yaml` documents the descriptor output and the source skill's license/usage fields.
- The source skill stays DCC-neutral; adapter skills perform scene import.

See the [Core asset-import contract](https://github.com/dcc-mcp/dcc-mcp-core/blob/main/python/dcc_mcp_core/asset_import.py)
for the complete fields and format values.
