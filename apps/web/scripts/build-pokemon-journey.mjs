import { readFileSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import vm from 'node:vm';
import './build-pokemon-loader.mjs';
const read = path => readFileSync(new URL(path, import.meta.url), 'utf8');
let html = read('../../../vendor/threeui/kage/public/landing-pages/kage.html');
function replace(from, to) {
  if (!html.includes(from)) throw new Error('Source anchor missing: ' + String(from).slice(0, 90));
  html = html.replace(from, to);
}
const world = JSON.parse(read('../src/data/world-map-110m.json'));
const map = world.countries.map(c => `<path data-country="${c.countryCode}" d="${c.path}"/>`).join('') + world.tinyCountries.map(c=>`<circle data-country="${c.countryCode}" cx="${c.x}" cy="${c.y}" r="3"/>`).join('');
const body = read('./scene-parts/pokemon-showcase.html').replace('<!-- WORLD_MAP -->', map);
const start = html.indexOf('<body '), end = html.indexOf('<script src="secret-pathways-assets/three.min.js">');
if (start < 0 || end < start) throw new Error('Missing document boundary');
html = html.slice(0, start) + body + '\n' + html.slice(end);
replace('<title>Kage — Where stillness reveals the unseen</title>', '<title>Pokécrack — Every pack. A bigger picture.</title>');
replace('A five-chapter night walk through a Kyoto mountain temple. Charred cypress, lantern light and a vermilion moon, rendered live in WebGL.', 'Discover Pokémon opening observations, worldwide coverage, trends and the set catalog.');
replace('</style>', read('./scene-parts/pokemon-showcase.css') + '\n</style>');
replace("const word = 'KAGE'", "const word = 'POKÉ'");
replace("const names = ['The Hidden Gate', 'The Sanmon', 'Still Gardens', 'Sacred Craft', 'Afterlight', 'Colophon'];", "const names = ['Welcome', 'Openings', 'Coverage', 'Trends', 'Sets', 'Explore data'];");
replace('<script src="secret-pathways-assets/three.min.js"></script>', '<script src="secret-pathways-assets/three.min.js"></script>\n<script src="pokemon-models/loader.js"></script>');
replace("['Raising the hall', () => buildTemple()],", "['Meeting our partners', () => loadPokemonModels()],\n  ['Raising the hall', () => buildTemple()],");
replace('function buildTemple() {', read('./scene-parts/pokemon-choreography.js.txt') + '\n' + read('./scene-parts/pokemon-characters.js.txt') + '\n' + read('./scene-parts/pokemon-landmarks.js.txt') + '\nfunction buildTemple() {');
replace('() => buildTemple()', '() => buildPokemonLandmarks()');
replace('() => buildTorii()', '() => buildPokemonGateway()');
// Route lights keep their original positions and compatible WORLD lighting hooks.
html = html.replace(/\bbuildLantern\(/g, 'buildPokemonRouteLight(');
// Keep the unused source declaration from replacing the adapter above.
replace('function buildPokemonRouteLight(x, z, s, y)', 'function buildOriginalLantern(x, z, s, y)');
replace('function buildCardCloth() {', read('./scene-parts/pokemon-runtime.js.txt') + '\n' + read('./scene-parts/pokemon-avatar-renderer.js.txt') + '\nfunction buildCardCloth() {');
replace('initPost(); buildCards(); buildCardCloth();', 'initPost(); buildCards(); initPokemonAvatars();');
replace('wireReveals(); wireForegroundStages(); wireNav(); wireHeroExit(); wireFocus(); wireCursor();', 'wireReveals(); wireNav(); wireFocus(); wireShowcase();');
replace('  updateLeaves(dt);', '  updateShowcaseMotion(dt);');
replace('  layoutWord();\n  measure();\n}', "  layoutWord();\n  measure();\n  resizePokemonAvatars();\n  if (journeyStarted && journeyPaused && document.documentElement.dataset.sceneStatus === 'ready') { RIG.smooth = RIG.prog = progressFor(scrollY); applyCamera(); updateShowcaseMotion(0); render(); }\n}");
replace('scene.add(rain); WORLD.rain = rain;', 'rain.visible = false; WORLD.rain = rain;');
replace('WORLD.leaves = { mesh: inst, list: list };', 'inst.visible = false; WORLD.leaves = { mesh: inst, list: list };');
replace('function render() {\n  FRAME++;', 'function render() {\n  WORLD.pokemonActors?.forEach(actor => actor.update(clock, REDUCE || journeyPaused));\n  FRAME++;');
replace('    renderPost();\n  }\n}', "    renderPost();\n  }\n  try { renderPokemonAvatars(); } catch (error) { disablePokemonAvatars(); console.warn('Character rendering stopped.', error); }\n}");
// Blue-hour Pokémon route: clean colour, cyan atmosphere, no haunted-temple plates.
replace('new THREE.FogExp2(0x050a0e, 0.0168)', 'new THREE.FogExp2(0x112d46, 0.0105)');
replace('new THREE.Color(0x060a0d)', 'new THREE.Color(0x10263d)');
replace('new THREE.HemisphereLight(0x53838f, 0x060a08, .13)', 'new THREE.HemisphereLight(0xaeeaff, 0x18342b, .58)');
replace('uExp: { value: .62 }', 'uExp: { value: .80 }');
replace('uGrain: { value: .020 }', 'uGrain: { value: .003 }');
replace('uSat: { value: 1.05 }', 'uSat: { value: 1.16 }');
replace('map: tx(texMoon()), color: hdr(3.6, .64, .61)', 'map: tx(texPokemonMoon()), color: hdr(1.9, 1.9, 1.9)');
replace('function buildMoon() {', `function texPokemonMoon() {
  const c = cvs(1024,1024), x = c.getContext('2d');
  x.save(); x.beginPath(); x.arc(512,512,493,0,Math.PI*2); x.clip();
  x.fillStyle='#eef7ff'; x.fillRect(0,0,1024,1024); x.fillStyle='#e76869';x.fillRect(0,0,1024,490);
  x.fillStyle='#263d57';x.fillRect(0,477,1024,70);
  x.beginPath();x.arc(512,512,132,0,Math.PI*2);x.fill();x.fillStyle='#e4f6ff';x.beginPath();x.arc(512,512,85,0,Math.PI*2);x.fill();
  const shade=x.createRadialGradient(345,300,40,540,555,560);shade.addColorStop(0,'#ffffff44');shade.addColorStop(.55,'#ffffff00');shade.addColorStop(1,'#031429dd');x.fillStyle=shade;x.fillRect(0,0,1024,1024);x.restore();return c;
}
function buildMoon() {`);
// Neutralize the old red foliage tint. Plants belong to a lush Pokémon route.
replace('hex(96 + v * 96, 14 + v * 22, 16 + v * 18)', 'hex(38 + v * 54, 100 + v * 90, 67 + v * 57)');
replace('map: tx(texLeaf()), color: 0x2b0406', 'map: tx(texLeaf()), color: 0x72c98b');
// Parent/frame lifecycle stays strictly local and pauses the retained render loop.
replace("  document.addEventListener('visibilitychange', () => {\n    if (document.hidden) { running = false; }\n    else if (!running) { running = true; tPrev = performance.now(); queue(); }\n  });", "  document.addEventListener('visibilitychange', syncJourneyVisibility);");
replace('function fallback(err) {', "function fallback(err) {\n  running = false; journeyPaused = true; cancelJourneyFrame();\n  disablePokemonAvatars(); disposePokemonAvatars();\n  document.documentElement.dataset.sceneStatus = 'fallback';\n  document.documentElement.classList.add('showcase-fallback');\n  document.querySelectorAll('[data-beat]').forEach(el=>{el.inert=false;el.classList.add('is-current');});\n  document.querySelectorAll('.chart-bar,.coverage-bar').forEach(el=>el.style.transform='none');\n  finishCounters();\n  notifyParent('pokecrack:ready', { status: 'fallback' });");
replace('  running = true; tPrev = performance.now();\n  INTRO.t0', "  journeyStarted = true;\n  document.documentElement.dataset.sceneStatus = 'ready';\n  notifyParent('pokecrack:ready', { status: 'ready' });\n  running = journeyVisible && !journeyPaused && !document.hidden; tPrev = performance.now();\n  INTRO.t0");
replace('if (i <= 1) return fallback(err);', 'return fallback(err);');
replace('function queue() { TIMER ? setTimeout(() => frame(performance.now()), 16) : requestAnimationFrame(frame); }', `let journeyFrame = 0;
function cancelJourneyFrame() { if (TIMER) clearTimeout(journeyFrame); else cancelAnimationFrame(journeyFrame); journeyFrame = 0; }
function queue() { if (journeyFrame || !running) return; const tick = now => { journeyFrame = 0; frame(now); }; journeyFrame = TIMER ? setTimeout(() => tick(performance.now()),16) : requestAnimationFrame(tick); }`);
replace("if (document.readyState === 'complete' || document.readyState === 'interactive') setTimeout(boot, 0);", "canvas.addEventListener('webglcontextlost', () => fallback(new Error('WebGL context lost')));\nif (document.readyState === 'complete' || document.readyState === 'interactive') setTimeout(boot, 0);");
for (const match of html.matchAll(/<script>([\s\S]*?)<\/script>/g)) new vm.Script(match[1]);
const destination = new URL('../public/landing-pages/pokemon-kage.html', import.meta.url);
writeFileSync(destination, '<!-- Generated from the archived Kage runtime by scripts/build-pokemon-journey.mjs. -->\n' + html);
console.log(fileURLToPath(destination));
const review = read('./scene-parts/pokemon-model-review.html').replace('/* CHARACTER_FACTORY */', read('./scene-parts/pokemon-choreography.js.txt') + '\n' + read('./scene-parts/pokemon-characters.js.txt'));
for (const match of review.matchAll(/<script>([\s\S]*?)<\/script>/g)) new vm.Script(match[1]);
writeFileSync(new URL('../public/landing-pages/pokemon-model-review.html', import.meta.url), review);

const motionReview = read('./scene-parts/pokemon-motion-review.html').replace('/* CHARACTER_FACTORY */', read('./scene-parts/pokemon-choreography.js.txt') + '\n' + read('./scene-parts/pokemon-characters.js.txt'));
for (const match of motionReview.matchAll(/<script>([\s\S]*?)<\/script>/g)) new vm.Script(match[1]);
writeFileSync(new URL('../public/landing-pages/pokemon-motion-review.html', import.meta.url), motionReview);
