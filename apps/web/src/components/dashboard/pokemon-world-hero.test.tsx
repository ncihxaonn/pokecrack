import React from "react";
import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { DEMO_PUBLIC_DATA } from "@/data/demo";
import { PokemonWorldHero } from "./pokemon-world-hero";

let intersection: IntersectionObserverCallback;
const disconnect = vi.fn();
function child() { return screen.getByTitle(/Pokémon world/) as HTMLIFrameElement; }
function message(data: unknown, origin = location.origin, source: MessageEventSource | null = child().contentWindow) {
  act(() => { window.dispatchEvent(new MessageEvent("message", { data, origin, source })); });
}
beforeEach(() => {
  vi.clearAllMocks();
  vi.stubGlobal("IntersectionObserver", class {
    constructor(callback: IntersectionObserverCallback) { intersection = callback; }
    observe = vi.fn(); disconnect = disconnect;
  });
  vi.stubGlobal("matchMedia", vi.fn(() => ({ matches: true })));
});
afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals(); });

describe("PokemonWorldHero", () => {
  it("embeds the complete same-origin document with only required capabilities", () => {
    render(<PokemonWorldHero data={DEMO_PUBLIC_DATA} />);
    expect(child()).toHaveAttribute("src", "/landing-pages/pokemon-kage.html");
    expect(child()).toHaveAttribute("sandbox", "allow-scripts allow-same-origin");
    fireEvent.load(child());
    expect(screen.getByRole("region")).toHaveAttribute("data-scene-status", "loading");
    expect(screen.getByRole("link", { name: /Skip the journey/ })).toHaveAttribute("href", "#world-coverage");
  });
  it("accepts readiness only from the expected window and origin", () => {
    render(<PokemonWorldHero data={DEMO_PUBLIC_DATA} />);
    message({ type: "pokecrack:ready", status: "ready" }, "https://example.com");
    message({ type: "pokecrack:ready", status: "ready" }, location.origin, window);
    message({ type: "pokecrack:ready", status: "invented" });
    expect(screen.getByRole("region")).toHaveAttribute("data-scene-status", "loading");
    message({ type: "pokecrack:ready", status: "ready" });
    expect(screen.getByRole("region")).toHaveAttribute("data-scene-status", "ready");
  });
  it("projects public presentation fields and labels demo data explicitly", () => {
    render(<PokemonWorldHero data={DEMO_PUBLIC_DATA} />);
    const post = vi.spyOn(child().contentWindow!, "postMessage");
    message({ type: "pokecrack:ready", status: "ready" });
    expect(post).toHaveBeenCalledWith(expect.objectContaining({ type: "pokecrack:metrics", mode: "demo", metrics: {
      observedPacks: DEMO_PUBLIC_DATA.observations.observedPacks,
      completeOpenings: DEMO_PUBLIC_DATA.observations.completeOpenings,
      countriesObserved: DEMO_PUBLIC_DATA.observations.countriesObserved,
      countriesWithPublishedRate: DEMO_PUBLIC_DATA.observations.countriesWithPublishedRate,
      setCount: DEMO_PUBLIC_DATA.catalog.setCount,
    } }), location.origin);
    const presentation = post.mock.calls.find(([payload]) => payload.type === "pokecrack:metrics")?.[0];
    expect(presentation.coverage).toEqual(DEMO_PUBLIC_DATA.mapCells.map(({ countryCode, countryName, packsObserved }) => ({ countryCode, countryName, packsObserved })));
    expect(presentation.trend).toEqual([...DEMO_PUBLIC_DATA.trend].sort((a,b) => a.date.localeCompare(b.date)).slice(-8).map(({ date, packsObserved }) => ({ date, packsObserved })));
    expect(presentation.catalog.sets).toEqual(DEMO_PUBLIC_DATA.catalog.sets.slice(0,3).map(({ slug, name, series }) => ({ slug, name, series })));
    expect(presentation).not.toHaveProperty("recentActivity");
  });
  it("updates the scene when published totals change", () => {
    const { rerender } = render(<PokemonWorldHero data={DEMO_PUBLIC_DATA} />);
    const post = vi.spyOn(child().contentWindow!, "postMessage");
    rerender(<PokemonWorldHero data={{ ...DEMO_PUBLIC_DATA, mode: "live", observations: { ...DEMO_PUBLIC_DATA.observations, observedPacks: 252 } }} />);
    expect(post).toHaveBeenCalledWith(expect.objectContaining({ type: "pokecrack:metrics", mode: "live", metrics: expect.objectContaining({ observedPacks: 252 }) }), location.origin);
  });
  it("times out a failed handshake but never times out a ready scene after data refresh", () => {
    vi.useFakeTimers();
    const { rerender } = render(<PokemonWorldHero data={DEMO_PUBLIC_DATA} />);
    act(() => vi.advanceTimersByTime(45_000));
    expect(screen.getByRole("region")).toHaveAttribute("data-scene-status", "fallback");
    message({ type: "pokecrack:ready", status: "ready" });
    rerender(<PokemonWorldHero data={{ ...DEMO_PUBLIC_DATA, observations: { ...DEMO_PUBLIC_DATA.observations, observedPacks: 253 } }} />);
    act(() => vi.advanceTimersByTime(45_000));
    expect(screen.getByRole("region")).toHaveAttribute("data-scene-status", "ready");
  });
  it("pauses offscreen rendering and cleans up parent listeners", () => {
    const { unmount } = render(<PokemonWorldHero data={DEMO_PUBLIC_DATA} />);
    const post = vi.spyOn(child().contentWindow!, "postMessage");
    act(() => intersection([{ isIntersecting: false, intersectionRatio: 0 } as IntersectionObserverEntry], {} as IntersectionObserver));
    expect(post).toHaveBeenLastCalledWith({ type: "pokecrack:visibility", visible: false }, location.origin);
    expect(document.documentElement.dataset.pokemonJourney).toBe("inactive");
    unmount();
    expect(disconnect).toHaveBeenCalledOnce();
    expect(document.documentElement.dataset.pokemonJourney).toBeUndefined();
  });
  it("moves focus to the existing map without trapping the visitor in the frame", () => {
    render(<><PokemonWorldHero data={DEMO_PUBLIC_DATA} /><div id="world-coverage">Map</div></>);
    const target = document.getElementById("world-coverage")!;
    target.scrollIntoView = vi.fn();
    message({ type: "pokecrack:explore" });
    expect(target).toHaveFocus();
    expect(target.scrollIntoView).toHaveBeenCalledWith({ behavior: "instant", block: "start" });
    message({ type: "pokecrack:ready", status: "fallback" });
    expect(screen.getByRole("status")).toHaveTextContent("The 3D scene is unavailable");
  });
  it("opens the existing catalog when a presentation set card is selected", () => {
    render(<><PokemonWorldHero data={DEMO_PUBLIC_DATA} /><h2 id="catalog-title">Catalog</h2></>);
    const target = document.getElementById("catalog-title")!;
    target.scrollIntoView = vi.fn();
    message({ type: "pokecrack:explore", target: "catalog" });
    expect(target).toHaveFocus();
    expect(target.scrollIntoView).toHaveBeenCalledWith({ behavior: "instant", block: "start" });
  });
});
