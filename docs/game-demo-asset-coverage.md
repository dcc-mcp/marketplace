# Game demo asset coverage

The marketplace now covers the asset classes needed for a small gameplay demo without bundling
third-party content. Provider skills download files and return attribution-aware
`AssetDescriptor` values; engine and DCC skills remain responsible for import.

| Demo need | Marketplace coverage | Notes |
| --- | --- | --- |
| Props, environments, characters | Kenney, Quaternius, Poly Haven, Objaverse, Sketchfab | Prefer CC0 providers for the fastest demo path. |
| PBR materials and HDRIs | Poly Haven, ambientCG | Both offer CC0 content. |
| Animated character packs | Quaternius, Kenney | Pack contents vary; inspect before download. |
| HUD and inventory icons | Game Icons | CC BY 3.0; retain the returned author credit. |
| UI fonts | Google Fonts | The downloaded family license is saved beside the font. |
| Music and sound effects | Mixkit | Accept only items explicitly marked with the Free License. |
| Cutscenes and background video | Pexels Video, Mixkit | Pexels needs an API key. |
| Import and format fixtures | Khronos glTF Sample Assets | Intended for pipeline validation, not final art direction. |
| Engine extensions | Godot Asset Store, Blender Extensions | Add-ons are code; review their own license and trust before installation. |
| City PCG vectors | OpenStreetMap City, Overture City | Bounded GeoJSON for roads, buildings, land cover, water, and infrastructure. |

## Demo smoke path

1. Install `dcc-asset-kenney`, `dcc-asset-quaternius`, `dcc-asset-polyhaven`,
   `dcc-asset-game-icons`, `dcc-asset-google-fonts`, and `dcc-asset-mixkit-free-media`.
2. Search before downloading, and keep the selected result's source and license fields.
3. Download one environment pack, one animated character pack, one material or HDRI, one icon,
   one font, and one sound effect.
4. Validate every returned `AssetDescriptor`, then hand it to the target DCC or engine importer.
5. Export a credits file from the descriptors before sharing the demo.

`dcc-asset-kenney` is installable directly for Godot, Unreal, and Unity because
its provider contract is engine-neutral. It only searches, downloads, and
returns a validated descriptor; engine import remains owned by the selected
adapter. Do not create an engine-specific asset-download Skill for this path.

## Sources intentionally not automated

- [Freesound](https://freesound.org/docs/api/terms_of_use.html): free API access is limited to
  non-commercial use, so it is not a safe default marketplace provider.
- [OpenGameArt](https://opengameart.org/content/faq): individual assets use different licenses;
  some impose attribution, share-alike, GPL, or DRM constraints. A future provider needs strict
  per-item filtering and cannot label the whole catalog simply as free.
- [Poly Pizza](https://poly.pizza/docs/press): its published API description does not yet provide
  the stable general integration contract required by the marketplace.
- Mixamo: no supported public download API was found. Keep it as a user-driven workflow unless an
  official automation contract becomes available.

This list is deliberately policy-based: a resource being free to download is not enough. A new
provider must expose a stable machine interface and enough license data to build a valid descriptor.
