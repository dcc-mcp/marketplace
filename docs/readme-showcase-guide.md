# README Showcase Guide

Use original renders to show what an asset skill can deliver. Do not copy source-site
thumbnails, example renders, logos, or interface screenshots into a skill README.

## Recommended first showcase sources

- **Poly Haven** — CC0 models, textures, and HDRIs. Use one model, one material, and one HDRI
  to make a compact Blender scene. <https://polyhaven.com/license>
- **ambientCG** — CC0 materials, HDRIs, and models. Pair a material with a simple original mesh
  when the skill primarily returns an archive. <https://ambientcg.com/>
- **Kenney** and **Quaternius** — use packs whose individual asset pages state CC0. Do not use
  either publisher's logo in the render. <https://kenney.nl/support>
- **Smithsonian Open Access** — use only individual entries marked CC0 and retain the item link
  beneath the image. <https://www.si.edu/openaccess/faq>

NASA assets are useful demos but are not the default showcase choice: follow NASA's media-use
guidelines, avoid its insignia and identifiers, and never imply endorsement.
<https://www.nasa.gov/nasa-brand-center/images-and-media/>

## Authoring workflow

1. Record the asset page URL and its per-item license before download.
2. Download through the source skill, then hand its `asset_descriptor` to a DCC adapter.
3. Render an original scene in Blender or the target DCC; do not include third-party branding.
4. Save an optimized image under `docs/images/<skill>-showcase.webp` in the skill repository.
5. Add the image and a short provenance line to the skill README:

   ```md
   ![One-sentence description of the rendered result](docs/images/<skill>-showcase.webp)

   Rendered with `<skill>` using [source asset](https://example.invalid) — `CC0-1.0`.
   ```

Use a 16:9 image (at least 1280 × 720), concise descriptive alt text, and an image file below
500 KB where practical. A README should show one representative workflow, not a gallery of
unattributed assets.
