# Pokémon product walkthrough — local preview

Worktree: `/Users/nixon/.codex/worktrees/bb70/PokeCrack`
Branch: `codex/pokemon-kage-hero-local`
Baseline: `81baa78bd13059d0be9f4885c263fb04813d41d2`
Status: local, uncommitted; nothing pushed, merged or deployed.

## Current implementation — 10 September 2026

The user approved the Kage-based camera journey and requested a much stronger
Pokémon identity, very short headlines and animated dashboard cards in the style
of an Apple product presentation. This iteration keeps the exact original six
camera stops, target splines, FOV changes, ground-level approach, final rise,
intro dolly and WebGL POKÉ wordmark. It replaces the earlier long-form temple
chapters and cloth picture gallery with six product presentation beats:

1. Every pack. A bigger picture. — Pikachu and a small pack-volume card.
2. Every opening. — observed pack count, complete openings and foil pack graphic.
3. One connected world. — country coverage, observed volumes and Snorlax.
4. See the story unfold. — actual dated pack volumes and Charizard.
5. Find your next obsession. — three catalog entries in a staggered card fan.
6. Your next discovery. — a direct entrance to the existing dashboard.

The central landmark is now Prism Tower, accompanied by Pokémon Center and
Professor Oak's Laboratory. These are procedural interpretations, not official
game models. Pokémon route lights, a Poké Ball gateway and sky sphere, Pikachu
and Snorlax models, blue-hour lighting and green foliage replace the former
shrine treatment. Pikachu, Snorlax and Charizard are now articulated Three.js mesh models. The
previous official Pokédex illustrations and their provenance remain as unused
local iteration assets; the current presentation does not load those images.
Prism Tower's identity was checked against the official Pokémon page:
https://legends.pokemon.com/en-us/story-world/lumiose-city.

The revised character update replaces the rejected procedural/chibi proportions
with intact rigged GLBs from 06wj/pokemon, pinned to commit
`00d96f7f18894055e7f1db44fa0df6462e5e4c8a`. Original geometry, skeletons,
colour textures and six animation clips remain unchanged on disk; placement
uses uniform scale only. Normal-map microtexture is softened at runtime and
Charizard's emissive flame is balanced for the local lighting. Native idle
animations drive the ears/body/tail/wings, with a restrained happy-clip blend
for Pikachu. No claim is made that the character assets are open-source:
upstream MIT covers code, and its README explicitly reserves Pokémon asset
rights to their respective owners. See `vendor/pokemon-models/README.md`.

The roadside figures use the same GLB factory. One transparent renderer shares
the existing journey clock, fading complete silhouettes through a reused render
target. It does not run a separate RAF. Pause/reduced motion freezes the current
pose. Each clone has independent bones. The r149 loader uses HTML image decoding
for embedded GLB textures under the existing CSP; no policy broadening is needed.
Skinned submesh culling is disabled because r149 uses undeformed bounds and
otherwise incorrectly removes the small eye meshes in tight camera framing.
Camera framing measures actual posed vertices, preserving long tails and wings.

Local multi-angle study: `/landing-pages/pokemon-model-review.html` shows front,
side, back and three-quarter views with model selection and pause controls.

Cards enter with scroll-controlled opacity, perspective and stagger; pointer
movement gives a restrained tilt. Counters and chart bars finish on a short
clock-based animation even when scrolling stops. Trends use actual date spacing
and volume, never fabricated values or suggested future odds. Country highlights
come from the supplied public snapshot; set names come from the catalog. Catalog
card emblems are decorative, not representations of official set cover art.

The original dashboard remains below. A strict same-origin/source-checked
message bridge projects only public totals, coverage, dated volume and three
catalog entries. Demo mode is visibly labeled. The map exit focuses the existing
map; catalog cards focus the existing catalog. Pause, offscreen visibility,
reduced motion, keyboard skipping, failed-scene fallback and a parent handshake
watchdog are supported. Pausing completes the current data presentation;
navigation while paused still updates a static scene.

The original Three.js runtime, embedded fonts and original reference images are
local. The eight archived text files and fourteen binary files remain unchanged.
The original reference is available at `/landing-pages/kage-reference.html`.
The new product card presentation uses the main scene's render loop rather than
creating the source gallery's separate cloth WebGL contexts.

## Reproduce

```sh
node apps/web/scripts/verify-pokemon-characters.mjs
node apps/web/scripts/build-pokemon-journey.mjs
pnpm --filter @pokecrack/web build
DATA_MODE=demo pnpm --filter @pokecrack/web start --hostname 127.0.0.1 --port 3017
```

Preview: http://127.0.0.1:3017/

Edit the builder or `apps/web/scripts/scene-parts/` fragments, then regenerate.
Do not hand-edit generated `pokemon-kage.html`. Static HTML changes are served
immediately. Restart Next after adding new public assets, and rebuild for React
changes. No WebGL fallback can be inspected at
`/landing-pages/pokemon-kage.html?nogl=1`.

Only the Pokémon scene route permits same-origin embedding. All other routes
retain frame-ancestors none and X-Frame-Options DENY. The iframe enables only
scripts and same-origin access.

## Changed paths

- `apps/web/src/components/dashboard/home-view.tsx`: hero before the existing map.
- `apps/web/src/components/dashboard/pokemon-world-hero.tsx`, `.module.css`, `.test.tsx`: iframe, projected data, lifecycle and exit behavior.
- `apps/web/src/components/dashboard/pokemon-showcase-runtime.test.ts`: real data, animation completion, pause and message validation regressions.
- `apps/web/scripts/verify-pokemon-characters.mjs`: validates real mesh geometry, articulation, original GLB hashes, real skeleton animation, clone isolation, frozen poses and four-angle animation framing.
- `apps/web/scripts/build-pokemon-journey.mjs` and `scene-parts/`: deterministic source adaptation, landmark models, product presentation markup/styles/runtime.
- `apps/web/public/landing-pages/pokemon-kage.html`: generated scene.
- `apps/web/public/landing-pages/pokemon-assets/`: previous-iteration artwork/provenance, no longer loaded by the hero.
- `apps/web/public/landing-pages/kage-reference.html`, `secret-pathways-assets/`: original local reference and assets.
- `apps/web/next.config.ts`, `src/app/security-headers.test.ts`: precise frame exception.
- `apps/web/eslint.config.js`: excludes the supplied minified runtime and generated third-party GLTF loader.
- `vendor/threeui/kage/`: immutable source archive and manifests.
- `docs/KAGE_MOTION_STUDY.md`: historical reference study, before the approved Kage rebuild.

## Verification before the 3D character update

- 243 frontend tests passed across 42 test files, including paused chart
  completion, truthful counters, irregular date spacing, empty data, source
  validation and catalog exit. Existing jsdom navigation/Node experimental
  warnings were emitted by unrelated suites; no tests failed.
- Production build, TypeScript and lint passed.
- Procedural model smoke check: 131 meshes, 44,186 triangles, finite geometry
  and transforms in both initialization orders.
- Previous route-header checks confirmed one CSP per route and the narrowly
  scoped frame exception; those configuration files are unchanged this turn.

- Actual browser checks covered the 1280×800 desktop view, 390×844 portrait
  and 667×375 landscape. Headlines and card contents fit. Parent and scene
  scrollWidth equal their clientWidth; character art retains its 1:1 proportions.
- Final Enter the dashboard click focuses `world-coverage` at 82px below the
  restored header. The deliverable browser preview is back at the opening beat.
- Catalog-card click focuses `catalog-title`, positioned approximately 82px
  below the restored app header. The no-WebGL URL retains all six readable
  chapters and accessible dashboard exits.
- Confirmed pause navigation, full chart/counter completion, paused CSS scan,
  and repainting the 3D scene after resizing while paused.
- All 8 original text hashes, 14 original binary hashes and 3 character artwork
  hashes pass. Original camera stops and standalone reference remain unchanged.

Browser automation reported three MutationObserver errors without an application
URL. The application and supplied scene do not contain that observer call; these
were not classified as application failures. Functional checks above completed.

Visual acceptance remains with the user. No remote publication is authorized.

## Revised GLB character verification (2026-09-10)

- Real r149 GLTF parsing: 7/1/6 skinned meshes and 3,950/5,576/6,000 triangles
  for Pikachu/Snorlax/Charizard, respectively; six native clips per character.
- Original source SHA-256 checks pass. Independent skeletons, pause freeze,
  finite transforms and four camera angles across sampled animation times pass.
- Full frontend suite: 244 tests across 42 files passed (existing jsdom
  navigation and Node localStorage warnings only).
- Browser: checked all three characters from front, side, back and ¾; embedded
  colour textures load, tail/wing proportions are intact, and the hero's Pikachu
  eye meshes render correctly after the r149 culling fix.
- Worktree `/Users/nixon/.codex/worktrees/bb70/PokeCrack`, branch
  `codex/pokemon-kage-hero-local`. All changes remain uncommitted and local.

- Final TypeScript and lint checks passed. Browser checks also covered the mobile
  trend/coverage chapters at 390×844; scene content width matched its viewport.
  Temporary viewport override was reset and the preview returned to the opening.

## Scroll character choreography (2026-09-10)

- Pikachu uses the original run clip to trot in from the right, turns toward the
  viewer, then turns and runs off as the first chapter leaves. Intro progress
  drives the opening arrival; subsequent travel and gait follow scroll position.
- Snorlax drops from above, rebounds gently and rests asleep on the coverage
  card's upper-right edge with small Z puffs. Forward scroll drops him below
  the screen; the fall remains visible after the card's own fade starts.
- Charizard banks and flaps its actual shoulder/wing joints along a curved
  entrance, hovers gently, then flies up and out on forward scroll.
- Reversing scroll retraces travel and gait without trigger timers. Paused or
  reduced-motion navigation shows a settled static character. All hero effects
  share the existing scene clock. Wing offsets restore their native base pose
  before each evaluation, preventing accumulated rotation on constant tracks.
- Camera bounds include sampled run/sleep/banked-flight poses. Expanded render
  viewports preserve the approved resting body size instead of shrinking it.
  Snorlax fits the available space below navigation and follows the card corner.
- New source: `apps/web/scripts/scene-parts/pokemon-choreography.js.txt`.
  Updated actor factory, renderer, runtime, CSS/markup and generated HTML.
- 16 targeted frontend tests passed; TypeScript and lint passed. GLB checks cover
  101 scroll poses per model, reverse determinism, native sleep/run selection,
  four-angle framing and repeated-pose non-accumulation. Desktop and narrow
  viewport browser checks covered the perch and chapter transitions.
- Same worktree and branch as above. No commit, push or deployment.

## Articulated fall and flight revision (2026-09-10)

The previous two-joint flap and whole-body fall have been replaced by the
reference-informed motion described in `POKEMON_CHARACTER_MOTION_STUDY.md`.
Pikachu remains unchanged. Snorlax now anticipates, rolls and slips before its
accelerating fall, with independently delayed limbs. Charizard has continuous
multi-joint wing strokes, folded recovery, tucked legs and a following tail.
The local `/landing-pages/pokemon-motion-review.html` page shares these exact
fragments and supports direct progress scrubbing. The original Kage camera route,
GLB assets and dashboard data remain intact. No commit, push or deployment.

### Charizard weight transfer and grounded takeoff

Charizard now reaches for the trend-card edge, compresses its legs on contact,
recovers to standing, crouches and pushes off with fixed toes before flying away.
The motion study has dedicated pose buttons for this sequence. Original Snorlax
and Pikachu motion remains unchanged. See `POKEMON_CHARACTER_MOTION_STUDY.md` for
references, IK/contact details and verification. 18 targeted tests and the real
GLB checks pass. Local and uncommitted on the existing branch; no remote writes.

### Pokémon TCG card surfaces

The Hero stack now uses the reference site's real card component contract:
`card__translater`, `card__rotator`, `card__front`, `card__shine`,
`card__glitter`, `card__glare` and `card__glare2`. Pikachu illustration rare,
Charizard ex and Snorlax are rendered from their original 151 card scans, with
the same perspective tilt, foil masks, blend modes and pointer-following glare
as [pokemon-cards-151](https://github.com/simeydotme/pokemon-cards-151).

The port and its GPL-3.0 attribution are documented in
`vendor/pokemon-cards-151/`. Card scans and the official card back remain
runtime references to `images.pokemontcg.io` and `tcg.pokemon.com`; they are not
bundled into this repository. The opening, coverage, trend and catalog surfaces
keep the earlier lightweight foil treatment from `vendor/pokemon-cards-css/`.
