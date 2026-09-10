import { readFileSync, writeFileSync } from 'node:fs';
import vm from 'node:vm';
const root = new URL('../../../vendor/pokemon-models/three-r149/', import.meta.url);
// Keep Kage's exact r149 renderer. Wrap the matching official example modules
// around that existing THREE namespace instead of loading a second Three copy.
function wrap(path, name, exports) {
  let source = readFileSync(new URL(path, root), 'utf8');
  source = source.replace(/import\s*\{([\s\S]*?)\}\s*from 'three';/, 'const {$1} = THREE;')
    .replace("import { toTrianglesDrawMode } from '../utils/BufferGeometryUtils.js';", 'const { toTrianglesDrawMode } = PokemonBufferUtils;')
    .replace(/export function /g, 'function ')
    .replace(/export\s*\{[^}]*\};/g, '');
  return `const ${name} = (() => {\n${source}\nreturn { ${exports} };\n})();\n`;
}
const output = '/* Three.js r149 example modules.\n' + readFileSync(new URL('LICENSE', root), 'utf8') + '*/\n' +
  wrap('examples/jsm/utils/BufferGeometryUtils.js', 'PokemonBufferUtils', 'toTrianglesDrawMode') +
  wrap('examples/jsm/utils/SkeletonUtils.js', 'PokemonSkeletonUtils', 'clone') +
  wrap('examples/jsm/loaders/GLTFLoader.js', 'PokemonGLTF', 'GLTFLoader');
new vm.Script(output);
writeFileSync(new URL('../public/landing-pages/pokemon-models/loader.js', import.meta.url), output);
