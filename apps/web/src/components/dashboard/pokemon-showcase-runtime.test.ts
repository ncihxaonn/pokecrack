import { readFileSync } from "node:fs";
import vm from "node:vm";
import { resolve } from "node:path";
import { describe, expect, it, vi } from "vitest";

const markup = readFileSync(resolve("scripts/scene-parts/pokemon-showcase.html"), "utf8");
const runtime = readFileSync(resolve("scripts/scene-parts/pokemon-runtime.js.txt"), "utf8");
function scene(coarse = true) {
  const doc = document.implementation.createHTMLDocument("Preview");
  doc.body.innerHTML = markup;
  const messages: ((event: { data: unknown; source: unknown; origin: string }) => void)[] = [];
  const parent = { postMessage: vi.fn() };
  let now = 1000;
  const clamp = (v: number, lo: number, hi: number) => Math.max(lo, Math.min(hi, v));
  const context = vm.createContext({
    document: doc, window: {}, parent, location: { origin: "https://preview.test" },
    addEventListener: (type: string, handler: typeof messages[number]) => { if (type === "message") messages.push(handler); },
    REDUCE: false, COARSE: coarse, performance: { now: () => now },
    RIG: { smooth: .70, intro: 1 }, clamp,
    damp: (value: number, target: number, rate: number, dt: number) => value + (target - value) * Math.min(1, rate * dt),
    smooth: (a: number, b: number, value: number) => { const t = clamp((value - a) / (b - a), 0, 1); return t * t * (3 - 2 * t); },
    requestAnimationFrame: vi.fn(), cancelAnimationFrame: vi.fn(), cancelJourneyFrame: vi.fn(),
    running: true, scrollY: 0, progressFor: () => 2.7, applyCamera: vi.fn(), render: vi.fn(),
  });
  vm.runInContext(readFileSync(resolve("scripts/scene-parts/pokemon-choreography.js.txt"), "utf8"), context);
  vm.runInContext(runtime, context);
  vm.runInContext("wireShowcase()", context);
  const send = (data: unknown, origin = "https://preview.test", source: unknown = parent) => messages.forEach(handler => handler({ data, origin, source }));
  return { doc, context, send, tick: (time: number) => { now = time; vm.runInContext("updateShowcaseMotion(0.016)", context); } };
}
const payload = {
  type: "pokecrack:metrics", mode: "demo", observationStatus: "published",
  metrics: { observedPacks: 4872, completeOpenings: 621, countriesObserved: 6, setCount: 4 },
  coverage: [{ countryCode: "AU", countryName: "Australia", packsObserved: 982 }],
  trend: [{ date: "2026-08-01", packsObserved: 100 }, { date: "2026-08-03", packsObserved: 200 }, { date: "2026-08-09", packsObserved: 400 }],
  catalog: { sets: [{ slug: "example", name: "Example set", series: "Series" }] },
};

describe("Pokémon presentation runtime", () => {
  it("fades the 3D characters with their chapter and clears previous poses on exit", () => {
    const s = scene();
    vm.runInContext("RIG.smooth=0", s.context); s.tick(1000);
    const opacity = (kind: string) => (s.doc.querySelector(`[data-character="${kind}"]`) as HTMLElement & { _characterOpacity: number })._characterOpacity;
    expect(opacity("pikachu")).toBe(1);
    expect(opacity("snorlax")).toBe(0);
    vm.runInContext("RIG.smooth=2", s.context); s.tick(1100);
    expect(opacity("pikachu")).toBe(0);
    expect(opacity("snorlax")).toBe(1);
    vm.runInContext("RIG.smooth=2.55", s.context); s.tick(1200);
    expect(opacity("snorlax")).toBeGreaterThan(0);
    expect(opacity("snorlax")).toBe(1); // Keep the falling silhouette opaque until it leaves the viewport.
    vm.runInContext("RIG.smooth=3", s.context); s.tick(1300);
    expect(opacity("snorlax")).toBe(0);
    expect(opacity("charizard")).toBe(1);
  });
  it("finishes truthful counters and chart bars even when scrolling stops halfway into a beat", () => {
    const s = scene(); s.send(payload); s.tick(1000); s.tick(1900);
    expect(s.doc.querySelector('#gate [data-metric="observedPacks"]')?.textContent).toBe("4,872");
    vm.runInContext("RIG.smooth=2.70", s.context); s.tick(2000); s.tick(2900);
    expect([...s.doc.querySelectorAll(".chart-bar")].map(el => (el as SVGElement).style.transform)).toEqual(["scaleY(1.0000)", "scaleY(1.0000)", "scaleY(1.0000)"]);
  });
  it("finishes the current chart immediately when motion is paused during its entrance", () => {
    const s = scene(); s.send(payload);
    s.doc.documentElement.dataset.sceneStatus = "ready";
    vm.runInContext("journeyStarted=true; RIG.smooth=2.70", s.context); s.tick(1000);
    expect(s.doc.querySelector<SVGElement>(".chart-bar")?.style.transform).toBe("scaleY(0.0000)");
    s.doc.getElementById("journey-motion")?.click();
    expect([...s.doc.querySelectorAll(".chart-bar")].map(el => (el as SVGElement).style.transform)).toEqual(["scaleY(1.0000)", "scaleY(1.0000)", "scaleY(1.0000)"]);
    expect(s.doc.querySelector('.beat.is-current')?.getAttribute('data-beat')).toBe("3");
  });
  it("uses actual dates and volumes and never fills empty history with invented values", () => {
    const s = scene(); s.send(payload);
    const bars = [...s.doc.querySelectorAll(".chart-bar")];
    const centers = bars.map(el => Number(el.getAttribute("x")) + Number(el.getAttribute("width")) / 2);
    expect(centers).toHaveLength(3);
    expect((centers[2]! - centers[1]!) / (centers[1]! - centers[0]!)).toBeCloseTo(3);
    expect(bars.map(el => Number(el.getAttribute("height")))).toEqual([37.5, 75, 150]);
    s.send({ ...payload, trend: [] });
    expect(s.doc.querySelectorAll(".chart-bar")).toHaveLength(0);
    expect(s.doc.getElementById("trend-latest")?.textContent).toBe("—");
    expect(s.doc.getElementById("trend-period")?.textContent).toContain("History is building");
  });
  it("validates message origin/source and renders incoming names only as text", () => {
    const s = scene();
    s.send(payload, "https://foreign.test"); s.send(payload, "https://preview.test", {});
    expect(s.doc.querySelector('[data-metric="observedPacks"]')?.textContent).toBe("—");
    s.send({ ...payload, mode: "live", observationStatus: "collecting", catalog: { sets: [{ name: '<img src=x onerror="alert(1)">', slug: "bad/slug", series: "Series" }] } });
    expect(s.doc.querySelector('[data-set-name]')?.textContent).toBe('<img src=x onerror="alert(1)">');
    expect(s.doc.querySelector('.set-card img')).toBeNull();
    expect(s.doc.querySelector('[data-provenance]')?.textContent).toContain("Collecting");
    expect(s.doc.querySelector('.set-card')?.getAttribute('data-catalog-slug')).toBe("");
  });
  it("applies the attributed TCG foil surface and maps pointer position to every card", () => {
    const s = scene(false);
    expect(s.doc.querySelectorAll(".tcg-card")).toHaveLength(9);
    expect(s.doc.querySelectorAll(".card-stack .stack-card")).toHaveLength(2);
    expect(s.doc.querySelector(".pokemon-card-front .reference-card-image")?.getAttribute("src")).toBe("https://images.pokemontcg.io/sv3pt5/173_hires.png");
    expect(s.doc.querySelector('.pokemon-card-front .card__translater .card__rotator .card__shine')).not.toBeNull();
    expect(s.doc.querySelector('.pokemon-card-front .card__glare2')).not.toBeNull();
    expect(s.doc.querySelector('#hero [data-metric]')).toBeNull();
    expect(s.doc.querySelectorAll('.reference-card .card__translater')).toHaveLength(3);
    expect(s.doc.querySelector('[data-card-foil="electric"]')).not.toBeNull();
    expect(s.doc.querySelector('.set-card[data-card-rarity="gallery"]')).not.toBeNull();

    const card = s.doc.querySelector<HTMLElement>('[data-card-foil="electric"][data-tilt]')!;
    card.getBoundingClientRect = () => ({ left: 10, top: 20, width: 200, height: 100, right: 210, bottom: 120 } as DOMRect);
    card.dispatchEvent(Object.assign(new Event("pointermove"), { clientX: 190, clientY: 30 }));
    expect(card.style.getPropertyValue("--pointer-x")).toBe("90.00%");
    expect(card.style.getPropertyValue("--pointer-y")).toBe("10.00%");
    expect(card.style.getPropertyValue("--card-opacity")).toBe("1");
    card.dispatchEvent(new Event("pointerleave"));
    expect(card.style.getPropertyValue("--pointer-x")).toBe("50.00%");
    expect(card.style.getPropertyValue("--pointer-y")).toBe("50.00%");
    expect(card.style.getPropertyValue("--card-opacity")).toBe("0.7");
    vm.runInContext("RIG.smooth=0.20", s.context);
    s.tick(1000);
    expect(card.style.getPropertyValue("--rotate-x")).not.toBe("0.00deg");
    expect(card.style.getPropertyValue("--rotate-y")).not.toBe("0.00deg");

    const catalogCard = s.doc.querySelector<HTMLElement>('.set-card[data-card-rarity="gallery"]')!;
    catalogCard.getBoundingClientRect = () => ({ left: 0, top: 0, width: 100, height: 100, right: 100, bottom: 100 } as DOMRect);
    catalogCard.dispatchEvent(Object.assign(new Event("pointermove"), { clientX: 100, clientY: 0 }));
    expect(catalogCard.style.getPropertyValue("--pointer-x")).toBe("100.00%");
    expect(catalogCard.style.getPropertyValue("--pointer-y")).toBe("0.00%");
  });
});
