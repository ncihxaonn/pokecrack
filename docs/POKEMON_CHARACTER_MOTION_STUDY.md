# Character motion revision — 10 September 2026

> Current review: [POKEMON_MOTION_REVIEW.md](./POKEMON_MOTION_REVIEW.md). The latest user direction supersedes this file's historical "turn away / recede" exit: Charizard now flies toward the viewer and exits left. This file preserves earlier iteration notes.

Local hero: http://127.0.0.1:3017/
Motion review: http://127.0.0.1:3017/landing-pages/pokemon-motion-review.html

## References and interpretation

- [Animation Mentor: Fall and Recovery](https://www.animationmentor.com/blog/tutorial-animate-fall-and-recovery-sequence/), Justin Milgate. The useful structure is the loss of balance before the fall, a change in the spine, and readable story poses. Applied to Snorlax as supported anticipation, a side roll, loss of support and a shorter accelerating descent. Human references inform timing; their proportions and poses are not copied onto Snorlax.
- [Animation Mentor: Overlap and Follow-through](https://www.animationmentor.com/blog/tutorial-animate-overlap-and-follow-through/), Nathaniel Seymour, and [Drew Adams on overlapping action](https://www.animationmentor.com/blog/follow-through-and-overlapping-action-the-12-basic-principles-of-animation/). Applied as different delays for shoulders, elbows, wrists, hips, feet and head. Limbs swing through after the torso begins its turn and settle after arrival.
- [Brown University robotic bat wing](https://engineering.brown.edu/news/2013-02-20/brown-researchers-build-robotic-bat-wing). The article and linked video distinguish extended downstroke from folded recovery. Applied to Charizard's actual wing chain: 38% power stroke, 62% recovery, delayed elbow and wingtip reversal. These exact timings are artistic choices, not measurements from the research.
- [Chin & Lentink: Birds repurpose the role of drag and lift to take off and land](https://www.nature.com/articles/s41467-019-13347-3). Body attitude and wing stroke orientation vary during acceleration and braking. Applied as banking along the entrance curve, a small pitch-up on arrival, and neck counter-rotation.
- [CMU capture subject 90](https://mocap.cs.cmu.edu/search.php?subjectnumber=90) includes a rug-pull fall in indexed results, but the actual capture page was unreachable. No CMU motion was downloaded, viewed, retargeted or used in this implementation.

## Implementation

Pikachu's approved path, run clip and gait math remain unchanged. The original
three GLBs remain byte-identical and uniformly scaled.

Snorlax uses the native sleeping pose, then additive articulation on the existing
rig. The exit's first half turns/slides while supported; quadratic vertical
travel begins after support is lost. Different delayed, damped joint curves
create inertial overlap. The body rotates about its belly rather than its feet.
The resting silhouette now sits into the card edge with the hand hanging below.
Sizing compensates for the chapter's vertical travel so approaching the nav
cannot shrink the character. This is authored animation, not a ragdoll solver.

Charizard uses a continuous scene-clock wing cycle even at held scroll. Wing
roots press down, elbows fold on recovery and distal wing joints lag. Legs tuck,
the head counters body pitch and the tail follows with a traveling offset.
Joint rotations are converted from model axes to each joint's parent space;
using arbitrary imported local axes was the principal weakness of the old flap.
Every additive transform is restored before native animation evaluation to avoid
accumulation. Main-hero pause and reduced-motion lifecycle remain unchanged.

The motion review page shares the production fragments, cameras and screen-path
functions. Its slider and named poses allow close inspection; its looping control
is opt-in. The hero still uses its original single animation clock.

## Verification

- Original model hashes, real r149 GLB decoding, isolated cloned skeletons,
  native animation, pause freeze and four-angle framing pass.
- Repeated held poses do not accumulate rotations. Clock advances articulate
  Charizard at fixed scroll; both arms, both legs and the head change during
  Snorlax's fall. Pikachu's fitted camera width remains 8.60502877200261.
- 101 scroll samples for Pikachu and Snorlax, and 404 samples spanning four
  flight phases for Charizard fit the journey cameras without clipped vertices.
- 17 targeted frontend tests pass. Lint and TypeScript pass.
- Browser inspection covers the motion review's sleep/roll/slip/fall poses,
  Charizard's changing wing silhouette, and the embedded desktop hero.
- At 390×844, Coverage and Trends remain readable, both models load and content
  width equals viewport width (375 CSS pixels excluding the scrollbar). The
  temporary viewport override was reset after inspection.

Worktree: `/Users/nixon/.codex/worktrees/bb70/PokeCrack`
Branch: `codex/pokemon-kage-hero-local`. Uncommitted local changes; no push or deploy.

## Charizard landing and takeoff — second revision

The user accepted Snorlax and Pikachu; their choreography branches are unchanged.
Charizard now lands on the trend card, bears weight and stands before taking off.
The previous continuous hover at the card is superseded by this grounded pause.

Additional primary references:

- [Whole-body 3D kinematics of bird take-off](https://pubmed.ncbi.nlm.nih.gov/29330588/): hindlimbs propel the trunk during launch. Used to separate crouch, leg extension and aerial travel.
- [Transition from wing to leg forces during landing](https://pubmed.ncbi.nlm.nih.gov/24855670/): braking precedes load transfer to the legs. Used to separate approach, reach, contact, compression and recovery.
- [Animation Mentor: Animating Birds in Flight](https://www.animationmentor.com/blog/tutorial-how-to-animate-birds-in-flight/): chest/head offsets and a trailing tail complement articulated wings. Used for delayed head settling, balancing forearms and tail follow-through. Exact curves are authored for this character, not retargeted motion capture.

Two-segment leg IK preserves original bone lengths while the hips descend.
The contact target stays on the card edge through compression and extension.
During the last push, heels rotate around fixed toes; only after toe-off does
the screen trajectory begin. Approaching legs extend, then tuck after launch.
The chest pitches into the crouch, arms balance the impact and swing through the
push, head/neck recover later, and delayed tail joints react to both transitions.
Wings reduce their activity while grounded and contribute to braking and launch.
All of this continues to follow the shared scene clock and scroll progress.

Verification: 18 targeted frontend tests; actual GLB tests include fixed toe
positions through seven grounded load/push samples, repeated-pose stability,
cloned skeleton isolation, pause and 404 airborne framing samples. The model
review offers named landing, compression, crouch, push and release poses.

Final browser inspection also confirms the integrated Trends contact surface at
1280×800 and the normal narrow panel (524 CSS pixels), with scene and all three
characters reporting ready. The temporary viewport was reset. Lint passed.

## Snorlax limb recoil refinement

The body route stays unchanged. Shoulder, elbow and wrist now respond to the
landing with separate damped impulses, then swing back. The response uses chapter
distance beyond the body's clamped arrival so settling does not stop prematurely.
The slide-off triggers a second impulse; the unsupported descent has multiple
asymmetric arm/leg swings and delayed wrists/feet. Added named review poses for
landing recoil and the following swing. Charizard and Pikachu are unchanged.
Visual inspection compares the arm raised after impact with its subsequent
hanging pose. The real-GLB verifier checks a visible wrist-angle change between
those phases, alongside the existing clipping, pause and non-accumulation checks.

## Itchy-belly motivation

Snorlax now raises the near hand and scratches the side of its belly before any
exit travel. Three short scroll-linked strokes articulate elbow, wrist and
fingers. The reach continues into the existing roll; the hand releases before
the unsupported descent and the accepted limb recoil resumes. Sleep puffs stop
as the scratching begins. Named review poses expose the scratch and side reach.
The other characters and the established falling path are unchanged. Browser
inspection refined the near-hand silhouette to keep the claws visible outside
the belly. A sequencing test checks scratch-before-roll and release-before-fall.

## Charizard destination gaze and balance

Destination gaze now leads launch while the body is still crouching; on approach
it looks down toward the landing point. Aim is distributed through neck and head.
Forearms make larger opposing balance gestures during compression and extension.
The tail rises against the forward body pitch, follows the push and counter-swings
during the turn. Landing compression starts while contact is blending in, and
leg reach overlaps that compression, removing the previous straight-leg hold
before the squat. Foot IK and fixed-toe checks remain intact. Browser comparisons
cover landing absorption and pre-launch gaze/tail balance; the other characters
are unchanged. Tests additionally cover overlapping reach/load and gaze leading
actual departure. Changes remain local on the existing uncommitted branch.

## Reach-led Snorlax roll

The arm now extends farther after scratching; shoulder lead is derived from that
reach, torso turn follows the shoulder, and slide begins only after sufficient
reach/turn. Upper and lower spine offsets make that lead visible while the elbow
opens to extend the hand. Removed the unrelated anticipatory counter-roll. The
sequencing test verifies shoulder lead before torso travel, with no early fall.
Original drop/recoil and both other characters remain intact. Browser inspection
covers the reaching side pose. 20 targeted tests and real-GLB checks pass; local
changes remain uncommitted on `codex/pokemon-kage-hero-local`.

## Charizard forward departure

Removed right-edge translation. After toe-off, Charizard turns to face into the
scene and travels toward a central vanishing point, with uniform viewport scaling
to convey increasing distance. The last segment clears the upper frame. Framing
covers the new rear-facing poses; tests check receding size and convergence toward
the scene centre. Landing, grounded propulsion and the other characters remain
unchanged. 21 targeted tests and the real-GLB framing/contact checks pass.


## Shoulder-led takeoff revision (2026-09-10)

Synced the independent Motion Study refinement: raised wings through leg loading, a first downstroke around toe-off, delayed elbow/wrist shaping, open forewings on the power stroke, folded recovery, chest elevation after wing depression and head counter-rotation. Wing quaternions use the original rest sample so the native idle cannot impose a second beat. Foot IK and the existing left/forward exit stay in place.

References: https://pmc.ncbi.nlm.nih.gov/articles/PMC3655074/ ; https://pmc.ncbi.nlm.nih.gov/articles/PMC6227979/ ; https://pubmed.ncbi.nlm.nih.gov/29330588/ . Provini’s dual-view footage was checked via https://www.audubon.org/news/how-birds-take-flight-such-ease . Timings are authored, not motion-capture data.


### Sustained three-beat departure

The first downstroke now overlaps the leg push; two more complete power/recovery cycles continue after toe-off. Torso loading begins while feet remain planted, and delayed climb increments follow each beat. References: https://www.nature.com/articles/s41467-019-13347-3 and https://pubmed.ncbi.nlm.nih.gov/20435815/ . Three cycles are an authored staging choice.
