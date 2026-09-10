import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import vm from "node:vm";
import { describe, expect, it } from "vitest";

const context = vm.createContext({});
vm.runInContext(readFileSync(resolve("scripts/scene-parts/pokemon-choreography.js.txt"), "utf8"), context);
const motion = (kind: string, distance: number, intro = 1, still = false) => context.pokemonScrollMotion(kind, distance, intro, still);
const anchor = { left: 860, top: 200, width: 220, height: 220 };
const viewport = { width: 1280, height: 800 };
const screen = (kind: string, state: ReturnType<typeof motion>) => context.pokemonScreenPose(kind, state, anchor, viewport);

describe("scroll-linked Pokémon entrances and exits", () => {
  it("keeps Snorlax sleeping on the perch, enters above the screen and leaves below it", () => {
    const before = motion("snorlax", -.72);
    expect(screen("snorlax", before).bottom).toBeLessThan(0);
    const perched = motion("snorlax", 0);
    expect(screen("snorlax", perched).top).toBeCloseTo(anchor.top);
    expect(perched.sleep).toBe(1);
    expect(perched.sleepOpacity).toBe(1);
    const leaving = motion("snorlax", .55);
    expect(leaving.opacity).toBe(1); // The card fade must not cut off the fall.
    expect(leaving.sleepOpacity).toBe(0);
    expect(screen("snorlax", leaving).top).toBeGreaterThan(anchor.top);
    expect(screen("snorlax", motion("snorlax", .73)).top).toBeGreaterThan(viewport.height);
  });
  it("reaches for an itch before rolling, then lets go during the fall", () => {
    const itchy=motion("snorlax",.15);
    expect(itchy.scratch).toBe(1);
    expect(itchy.turn+itchy.fall).toBe(0);
    expect(itchy.sleepOpacity).toBe(0);
    const leading=motion("snorlax",.22);
    expect(leading.armReach).toBeGreaterThan(0);
    expect(leading.shoulderLead).toBeGreaterThan(leading.turn);
    expect(leading.slip+leading.fall).toBe(0);
    expect(motion("snorlax",.29).scratch).toBe(1);
    expect(motion("snorlax",.29).turn).toBeGreaterThan(0);
    expect(motion("snorlax",.50).scratch).toBe(0);
    expect(motion("snorlax",.15,1,true).scratch).toBe(0);
  });
  it("rolls while supported before accelerating off the edge", () => {
    const turning = motion("snorlax", .34);
    expect(turning.turn).toBeGreaterThan(.5);
    expect(turning.fall).toBe(0);
    expect(screen("snorlax", turning).top).toBeCloseTo(anchor.top);
    const at = (exit: number) => screen("snorlax", motion("snorlax", .18 + exit * .55)).top;
    expect(at(.9) - at(.8)).toBeGreaterThan(at(.7) - at(.6));
    expect(motion("snorlax", .34).sleepOpacity).toBe(0);
  });
  it("looks ahead before takeoff and blends compression into contact", () => {
    const preparing=motion("charizard",.27);
    expect(preparing.depart).toBe(0);
    expect(preparing.gazeYaw).toBeLessThan(-.5);
    expect(preparing.yaw).toBeCloseTo(0); // Look left before the planted trunk follows.
    const touching=motion("charizard",-.72+.70*.62);
    expect(touching.support).toBeGreaterThan(.5);
    expect(touching.landingLoad).toBeGreaterThan(0);
    expect(touching.reach).toBeGreaterThan(0);
  });
  it("lands before compressing and pushes before leaving the card", () => {
    const landed = motion("charizard", -.212);
    expect(landed.support).toBe(1);
    expect(landed.landingLoad).toBeGreaterThan(.99);
    expect(screen("charizard", landed).top).toBeCloseTo(anchor.top);
    const crouched = motion("charizard", .30);
    const pushing = motion("charizard", .365);
    expect(crouched.crouch).toBeGreaterThan(.99);
    expect(pushing.crouch).toBeLessThan(crouched.crouch);
    expect(pushing.push).toBeGreaterThan(.8);
    for (const state of [crouched,pushing]) {
      expect(state.support).toBe(1);
      expect(screen("charizard",state).top).toBeCloseTo(anchor.top);
      expect(screen("charizard",state).left).toBeCloseTo(anchor.left);
    }
    const airborne = motion("charizard", .46);
    expect(airborne.support).toBe(0);
    expect(screen("charizard",airborne).top).toBeLessThan(anchor.top);
  });
  it("flies left toward the viewer without an airborne spin, on desktop and mobile", () => {
    for (const [base, view] of [[anchor, viewport], [{left:300,top:180,width:180,height:180},{width:539,height:963}]] as const) {
      let prior = context.pokemonScreenPose("charizard",motion("charizard",.40),base,view);
      let priorYaw=0;
      for(let distance=.405;distance<=.731;distance+=.005) {
        const state=motion("charizard",distance),rect=context.pokemonScreenPose("charizard",state,base,view);
        expect(rect.left+rect.width/2).toBeLessThanOrEqual(prior.left+prior.width/2);
        expect(rect.width).toBeGreaterThanOrEqual(prior.width);
        expect(rect.width/rect.height).toBeCloseTo(base.width/base.height);
        expect(state.yaw).toBeGreaterThan(-Math.PI/2); // The face stays in the front hemisphere.
        expect(state.yaw).toBeLessThanOrEqual(0);
        expect(Math.abs(state.yaw-priorYaw)).toBeLessThan(.045);
        prior=rect;priorYaw=state.yaw;
      }
      expect(prior.right).toBeLessThan(0);
      const fading=context.pokemonScreenPose("charizard",motion("charizard",.18+.55*.92),base,view);
      expect(fading.right).toBeLessThan(0); // No fading out in mid-air.
    }
  });
  it("joins the launch path with continuous position and velocity at toe-off", () => {
    const epsilon=.00001,launch=.18+.55*.40;
    const points=[launch-epsilon,launch,launch+epsilon].map(d=>screen("charizard",motion("charizard",d)));
    for(const key of ["left","top","width"]){
      expect(Math.abs(points[2][key]-points[0][key])).toBeLessThan(.001);
      expect(Math.abs((points[2][key]-points[1][key])/epsilon-(points[1][key]-points[0][key])/epsilon)).toBeLessThan(1);
    }
  });
  it("uses running legs and flying wings while traveling and retraces on reverse scroll", () => {
    expect(motion("pikachu", 0, .3).run).toBe(1);
    expect(motion("charizard", -.5).flight).toBe(1);
    for (const kind of ["pikachu", "snorlax", "charizard"]) {
      const snapshots = [-.7, -.4, -.1, 0, .3, .5, .7].map(distance => ({distance, state: motion(kind, distance, Math.max(0, Math.min(1, (distance + .72) / .62)))}));
      for (const { distance, state } of snapshots.reverse()) {
        expect(motion(kind, distance, Math.max(0, Math.min(1, (distance + .72) / .62)))).toEqual(state);
      }
      const last=screen(kind,motion(kind,.73));
      expect(last.left > viewport.width || last.right < 0 || last.top > viewport.height || last.bottom < 0).toBe(true);
    }
  });
  it("settles the active character without travel when motion is disabled", () => {
    for (const kind of ["pikachu", "snorlax", "charizard"]) {
      const state = motion(kind, -.2, .3, true);
      const rect = screen(kind, state);
      expect(rect.left).toBeCloseTo(anchor.left);
      expect(rect.top).toBeCloseTo(anchor.top);
      expect(state.run + state.flight).toBe(0);
      expect(state.opacity).toBe(1);
      expect(motion(kind, 1, 1, true).opacity).toBe(0);
    }
  });
});
