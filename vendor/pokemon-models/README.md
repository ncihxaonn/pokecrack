# Local Pokémon model study

This replaces the user-rejected procedural character proportions in the local
hero preview. Models were inspected in front, side, back and three-quarter
views; source mesh/bone proportions are preserved with uniform placement scale.

Source: https://github.com/06wj/pokemon
Pinned commit: `00d96f7f18894055e7f1db44fa0df6462e5e4c8a`
Upstream interactive reference: https://06wj.github.io/pokemon/index.html?scene=gallery#006
Retrieved: 2026-09-10. Exact paths, sizes, animation metadata and SHA-256 values
are recorded in `sources.json`. Unmodified GLBs are served locally from
`apps/web/public/landing-pages/pokemon-models/` (about 17.5 MB total).

## Rights and provenance

The upstream **code** is MIT licensed (`UPSTREAM-CODE-LICENSE`). Its README
explicitly states that this is an unofficial demonstration, Pokémon characters
and assets belong to their respective owners, and the repository does **not**
grant rights to those assets. Therefore these are publicly available rigged
models used for the requested local fan preview, **not assets represented as
open-source or commercially cleared**. `UPSTREAM-README.md` preserves the source
statement. This local task does not authorize pushing or publishing them.

The three original GLBs contain six skeletal clips each: idle, happy, walk, run,
attack and sleep. Hero motion uses native idle/run/sleep clips with scroll-driven positioning;
Pikachu trots, Snorlax sleeps and falls, and Charizard adds articulated wing
flaps. The standalone model study retains the gentle native idle presentation.
No mesh, UV, bone or character proportion has been regenerated. Textures are
surfaces on real skinned geometry, not flat character image billboards.

## Runtime

`three-r149/` contains unmodified official Three.js r149 example modules and
its MIT license, from https://github.com/mrdoob/three.js/tree/r149.
`apps/web/scripts/build-pokemon-loader.mjs` deterministically wraps those example
modules around Kage's existing THREE namespace, avoiding a second Three runtime.
Build: `node apps/web/scripts/build-pokemon-journey.mjs`.
Verify: `node apps/web/scripts/verify-pokemon-characters.mjs`.
View: http://127.0.0.1:3017/landing-pages/pokemon-model-review.html

The model check parses actual GLBs and verifies hashes, mesh counts, independent
skeleton cloning, frozen pause poses and unclipped four-angle animated framing.
It stubs only browser image decoding; actual textures and lighting were checked
in the local browser. Models and loaders are local; no runtime CDN dependency.
