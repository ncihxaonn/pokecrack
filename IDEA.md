This ChatGPT conversation is a technical planning session for a project called Pokecrack — a free, non-commercial dashboard that tracks Pokémon TCG (trading card game) pack-opening data. Here’s the gist:

What Pokecrack is

An unofficial “alt-data” dashboard that observes and aggregates real-world pack openings — which sets/products people open, how many packs, what rare cards appear, and where (country, region, retailer, batch code). It presents this like a stock/quant terminal, with the tagline:

Crack open the data behind every pack.

Crucially, it’s framed as an observation tool, not a prediction or “lucky pack” guarantee — the plan repeatedly insists the UI must never claim things like “guaranteed hot” or “best store.”

The core technical debate

Most of the conversation is the user working out the data-collection architecture, and settling a key question: how much can run purely on a VPS versus their personal computer. The final decision:

- Everything runs on the VPS — no dependence on the user’s home machine staying online (they only SSH-tunnel in once via noVNC to log into sites and clear captchas).

- Scrapling = the main scraper for public web pages (HTTP + JavaScript-rendered).

- OpenCLI (+ a persistent Chromium and its Browser Bridge extension, all on the VPS) = only for login-required social platforms like Reddit, X, Bilibili, Xiaohongshu.

- Official APIs (TCGdex for card catalog, YouTube Data API for discovery) are preferred first.

- AI does all the review — two AI passes extract and validate data, with a third to break ties; conflicting or low-confidence data is auto-rejected. No human review queue.

The stack

Next.js on Vercel Hobby (dashboard) + Supabase Free (database) + a VPS running Docker services for collection, AI validation, aggregation, scheduling, and monitoring. Statistics use empirical Bayes with credible intervals, and everything is designed around Supabase’s free-tier limits.

The naming thread

There’s also a lengthy tangent about naming the project — the AI proposed 10 alternatives (PokeLattice, PokeQuorum, etc.) and warned that “Poke” still risks Pokémon trademark association. The user ultimately chose Pokecrack as a working name, with legal/trademark review deferred to a future commercialization checklist.
