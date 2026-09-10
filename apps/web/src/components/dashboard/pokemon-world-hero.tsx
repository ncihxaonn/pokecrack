"use client";

import React, { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import type { PublicDashboardData } from "@/data/types";
import styles from "./pokemon-world-hero.module.css";

export function PokemonWorldHero({ data, provenance }: { data: PublicDashboardData; provenance?: ReactNode }) {
  const section = useRef<HTMLElement>(null);
  const frame = useRef<HTMLIFrameElement>(null);
  const visible = useRef(true);
  const ready = useRef(false);
  const [status, setStatus] = useState<"loading" | "ready" | "fallback">("loading");
  const { observedPacks, completeOpenings, countriesObserved, countriesWithPublishedRate } = data.observations;
  const setCount = data.catalog.setCount;
  const presentation = useMemo(() => ({
    observationStatus: data.observations.status,
    coverage: data.mapCells.map(({ countryCode, countryName, packsObserved }) => ({ countryCode, countryName, packsObserved })),
    trend: [...data.trend].sort((a, b) => a.date.localeCompare(b.date)).slice(-8).map(({ date, packsObserved }) => ({ date, packsObserved })),
    catalog: { status: data.catalog.status, sets: data.catalog.sets.slice(0, 3).map(({ slug, name, series }) => ({ slug, name, series })) },
  }), [data.observations.status, data.mapCells, data.trend, data.catalog.status, data.catalog.sets]);

  useEffect(() => {
    const element = section.current;
    if (!element) return;
    const sendVisibility = () => frame.current?.contentWindow?.postMessage({ type: "pokecrack:visibility", visible: visible.current && !document.hidden }, window.location.origin);
    const sendData = () => frame.current?.contentWindow?.postMessage({
      type: "pokecrack:metrics", mode: data.mode, ...presentation,
      metrics: { observedPacks, completeOpenings, countriesObserved, countriesWithPublishedRate, setCount },
    }, window.location.origin);
    const watchdog = ready.current ? undefined : window.setTimeout(() => setStatus("fallback"), 45_000);
    const onMessage = (event: MessageEvent) => {
      if (event.origin !== window.location.origin || event.source !== frame.current?.contentWindow || !event.data || typeof event.data !== "object") return;
      if (event.data.type === "pokecrack:ready" && (event.data.status === "ready" || event.data.status === "fallback")) {
        ready.current = true;
        window.clearTimeout(watchdog);
        setStatus(event.data.status);
        sendData(); sendVisibility();
      }
      if (event.data.type === "pokecrack:explore") {
        const target = document.getElementById(event.data.target === "catalog" ? "catalog-title" : "world-coverage");
        if (!target) return;
        target.tabIndex = -1;
        target.focus({ preventScroll: true });
        target.scrollIntoView({ behavior: window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ? "instant" : "smooth", block: "start" });
      }
    };
    window.addEventListener("message", onMessage);
    document.addEventListener("visibilitychange", sendVisibility);
    const observer = typeof IntersectionObserver === "undefined" ? null : new IntersectionObserver(([entry]) => {
      visible.current = entry?.isIntersecting ?? true;
      document.documentElement.dataset.pokemonJourney = (entry?.intersectionRatio ?? 1) > .5 ? "active" : "inactive";
      sendVisibility();
    }, { threshold: [0, .5] });
    observer?.observe(element);
    document.documentElement.dataset.pokemonJourney = "active";
    sendData();
    return () => {
      window.clearTimeout(watchdog);
      observer?.disconnect();
      window.removeEventListener("message", onMessage);
      document.removeEventListener("visibilitychange", sendVisibility);
      delete document.documentElement.dataset.pokemonJourney;
    };
  }, [data.mode, observedPacks, completeOpenings, countriesObserved, countriesWithPublishedRate, setCount, presentation]);

  return (
    <section className={styles.journey} ref={section} aria-label="Explore the Pokémon world" data-scene-status={status}>
      <div className={styles.accessibleIntro}>
        {provenance}
        <h1>Pokémon opening analysis</h1>
      </div>
      <a className={styles.skip} href="#world-coverage">Skip the journey and explore the data</a>
      <iframe ref={frame} className={styles.scene} src="/landing-pages/pokemon-kage.html" title="Pokémon world — openings, coverage, trends and sets around Prism Tower" sandbox="allow-scripts allow-same-origin" onError={() => setStatus("fallback")} />
      {status === "fallback" ? <p className={styles.fallback} role="status">The 3D scene is unavailable. <a href="#world-coverage">Explore the opening data</a></p> : null}
    </section>
  );
}
