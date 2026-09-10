# Pokémon Cards 151 reference attribution

The Hero stack follows the card DOM contract and holographic CSS techniques
from [simeydotme/pokemon-cards-151](https://github.com/simeydotme/pokemon-cards-151),
copyright Simon Goellner. The upstream project is released under
[GPL-3.0](https://github.com/simeydotme/pokemon-cards-151/blob/main/LICENSE).

The PokeCrack port keeps the same `card__translater`, `card__rotator`,
`card__front`, `card__shine`, `card__glitter`, `card__glare` and `card__glare2`
layer contract so the Hero uses the same 3D and foil behavior. The relevant
rewrite lives in `apps/web/scripts/scene-parts/pokemon-showcase.css` and
`apps/web/scripts/scene-parts/pokemon-runtime.js.txt`.

The Hero references the original 151 card scans and Pokémon card back from
`images.pokemontcg.io` and `tcg.pokemon.com` at runtime. Those third-party
artwork assets are not redistributed in this repository.
