/* Deterministic scroll choreography. Reversing scroll retraces the same path;
 * no event-triggered timers, physics history or extra render loop. */
function pokemonScrollMotion(kind, distance, intro = 1, still = false) {
  const limit = (x) => Math.max(0, Math.min(1, x));
  const smoothstep = (a, b, x) => {
    const t = limit((x - a) / (b - a));
    return t * t * (3 - 2 * t);
  };
  const entry = still
    ? 1
    : kind === "pikachu"
      ? limit(intro)
      : limit((distance + 0.72) / 0.62);
  const exit = still ? 0 : limit((distance - 0.18) / 0.55);
  const opacity = still
    ? Math.abs(distance) < 0.5
      ? 1
      : 0
    : smoothstep(0, 0.035, entry) * (1 - smoothstep(0.92, 1, exit));
  const arrive = 1 - Math.pow(1 - entry, 3),
    leave = exit * exit;
  const motion = {
    distance,
    entry,
    exit,
    opacity,
    arrive,
    leave,
    phase: entry < 0.999 ? "enter" : exit > 0.001 ? "exit" : "rest",
    run: 0,
    sleep: kind === "snorlax" ? 1 : 0,
    flight: 0,
    yaw: 0,
    roll: 0,
    pitch: 0,
    clipTime: 0,
    drop: 0,
    sleepOpacity: 0,
    still,
  };
  if (kind === "pikachu") {
    motion.run = still
      ? 0
      : Math.max(1 - smoothstep(0.75, 1, entry), smoothstep(0, 0.2, exit));
    motion.clipTime = arrive * 1.8 + leave * 1.8;
    motion.yaw =
      -1.2 * (1 - smoothstep(0.7, 1, entry)) + 1.25 * smoothstep(0, 0.3, exit);
    motion.roll = -0.07 * motion.run * (exit > 0 ? -1 : 1);
  } else if (kind === "snorlax") {
    const fall = limit(entry / 0.72),
      settle = limit((entry - 0.72) / 0.28);
    // A supported turn comes first. Gravity starts only after the belly clears
    // the edge; the last half of the scroll beat is the accelerating fall.
    // An itchy belly motivates the roll: reach and scratch before the body
    // starts shifting toward the edge, then release the hand as support goes.
    motion.scratch = still
      ? 0
      : smoothstep(0.025, 0.11, distance) *
        (1 - smoothstep(0.36, 0.46, distance));
    motion.scratchStroke =
      Math.sin(limit((distance - 0.1) / 0.25) * Math.PI * 6) * motion.scratch;
    motion.armReach = still ? 0 : smoothstep(0.16, 0.38, distance);
    motion.shoulderLead = smoothstep(0.02, 0.62, motion.armReach);
    motion.turn = smoothstep(0.18, 0.9, motion.armReach);
    motion.slip =
      smoothstep(0.72, 1, motion.armReach) * smoothstep(0.3, 0.62, exit);
    motion.fall = limit((exit - 0.48) / 0.52);
    // Keep moving into the soft support before settling; an immediate upward
    // bounce at first contact reads like a rigid ball, not a heavy belly.
    motion.drop =
      entry < 0.72
        ? -(1 - fall * fall)
        : 0.035 * Math.sin(settle * Math.PI) * Math.exp(-settle * 2);
    motion.impact =
      entry < 0.72 ? 0 : Math.sin(settle * Math.PI * 2) * Math.exp(-settle * 3);
    motion.incoming = 1 - smoothstep(0.7, 1, entry);
    motion.roll =
      0.48 * (1 - entry) +
      0.11 * motion.impact +
      motion.turn * 1.3 +
      motion.fall * 0.8;
    motion.pitch =
      -0.16 * motion.incoming - 0.35 * motion.slip - motion.fall * 0.75;
    motion.yaw =
      0.12 * motion.incoming + 0.22 * motion.turn + motion.fall * 0.48;
    motion.sleepOpacity =
      smoothstep(0.94, 1, entry) *
      (still ? 1 : 1 - smoothstep(0.025, 0.1, distance));
  } else if (kind === "charizard") {
    Object.assign(motion, pokemonCharizardMechanics(entry, exit));
    motion.clipTime = arrive * 2.4 + leave * 2.4;
    // Head anticipates the left-front destination. The trunk follows after
    // toe-off through a modest bank, without reversing its forward axis.
    motion.yaw =
      -0.9 * (1 - motion.approach) - 0.72 * smoothstep(0, 0.65, motion.depart);
    motion.roll =
      -0.24 * Math.sin(Math.min(1, entry / 0.7) * Math.PI) +
      0.16 * Math.sin(motion.depart * Math.PI);
    motion.pitch =
      0.32 * motion.flight -
      0.27 * motion.brake +
      0.2 * motion.crouch +
      0.14 * smoothstep(0, 0.65, motion.depart);
  }
  return motion;
}
function pokemonScreenPose(kind, motion, anchor, viewport) {
  const right = viewport.width - anchor.left + anchor.width;
  let x = 0,
    y = 0;
  if (kind === "pikachu") {
    x = right * (1 - motion.arrive + motion.leave);
    y = -Math.sin(motion.entry * Math.PI) * anchor.height * 0.035;
  } else if (kind === "snorlax") {
    y =
      (anchor.top + anchor.height * 1.15) * motion.drop +
      (viewport.height - anchor.top + anchor.height) *
        motion.fall *
        motion.fall +
      anchor.height * 0.1 * motion.slip;
    x =
      anchor.width *
      (-0.035 * Math.sin(motion.exit * Math.PI * 2) +
        0.24 * motion.turn +
        0.22 * motion.slip +
        0.18 * motion.fall);
  } else if (kind === "charizard") {
    // Accelerate left AND toward the viewer in one continuous arc. Uniform
    // perspective enlargement preserves the original model proportions.
    // The whole silhouette clears the left edge before its opacity fades.
    const progress = motion.depart,
      near = Math.min(1, progress / 0.9);
    const depth = near * near * (3 - 2 * near),
      scale = 1 + 1.45 * depth;
    const travel =
      (0.12 * progress * progress + 0.88 * Math.pow(progress, 4)) / 0.57;
    const width = anchor.width * scale,
      height = anchor.height * scale;
    const center = anchor.left + anchor.width / 2;
    const clearance = center + anchor.width * 1.225 + viewport.width * 0.12;
    x = right * (1 - motion.approach) - clearance * travel;
    const centerY = anchor.top + anchor.height / 2;
    // A high desktop perch needs a lower projected centre as the body grows,
    // otherwise its face flies behind the navigation before reaching us.
    const nearCenterY = Math.max(centerY, viewport.height * 0.46);
    y =
      -(anchor.top + anchor.height) * (1 - motion.approach) +
      (nearCenterY - centerY) * depth -
      anchor.height *
        (motion.climb +
          0.06 * travel +
          0.06 * Math.pow(Math.sin(progress * Math.PI), 2));
    const left = center + x - width / 2,
      top = centerY + y - height / 2;
    return {
      left,
      top,
      width,
      height,
      right: left + width,
      bottom: top + height,
    };
  }
  return {
    left: anchor.left + x,
    top: anchor.top + y,
    width: anchor.width,
    height: anchor.height,
    right: anchor.left + x + anchor.width,
    bottom: anchor.top + y + anchor.height,
  };
}

// Contact, load acceptance and propulsion are separate from aerial travel.
// Feet stay planted through the crouch; the flight path starts at toe-off.
function pokemonCharizardMechanics(entry, exit) {
  const clamp = (x) => Math.max(0, Math.min(1, x));
  const ease = (a, b, x) => {
    const t = clamp((x - a) / (b - a));
    return t * t * (3 - 2 * t);
  };
  const pulse = (a, b, c, x) => ease(a, b, x) * (1 - ease(b, c, x));
  const contact = ease(0.64, 0.72, entry),
    release = ease(0.36, 0.44, exit);
  const landingLoad = pulse(0.68, 0.82, 1, entry);
  const windup = pulse(0.015, 0.22, 0.38, exit);
  const push = ease(0.22, 0.38, exit) * (1 - ease(0.4, 0.5, exit));
  const depart = clamp((exit - 0.4) / 0.6);
  const flight = Math.max(1 - contact, release);
  return {
    approach: 1 - Math.pow(1 - clamp(entry / 0.7), 2),
    depart,
    // A delayed rise continues through recovery after each force-producing
    // downstroke. This carries the body upward rather than just waggling wings.
    climb:
      0.025 * ease(0.4, 0.49, exit) +
      0.025 * ease(0.51, 0.64, exit) +
      0.02 * ease(0.67, 0.81, exit),
    contact,
    support: contact * (1 - release),
    flight,
    landingLoad,
    windup,
    push,
    crouch: landingLoad + windup,
    brake: pulse(0.38, 0.63, 0.8, entry),
    reach: pulse(0.42, 0.66, 0.84, entry),
    // Extend through toe-off, then sweep the extended legs aft. The ankle
    // follows the hip slightly later instead of snapping the toes backward.
    legSweep: exit > 0 ? ease(0.4, 0.62, exit) : 1 - ease(0.28, 0.55, entry),
    ankleSweep: exit > 0 ? ease(0.43, 0.68, exit) : 1 - ease(0.3, 0.58, entry),
    gazeYaw:
      -0.5 * pulse(0.15, 0.55, 0.88, entry) -
      0.65 * pulse(0.015, 0.2, 0.78, exit),
    gazePitch:
      0.28 * pulse(0.15, 0.55, 0.88, entry) -
      0.3 * pulse(0.015, 0.2, 0.75, exit),
    wingDrive: Math.max(
      flight,
      0.55 * pulse(0.68, 0.72, 0.95, entry),
      0.75 * ease(0.1, 0.34, exit),
    ),
    action:
      entry < 0.55
        ? "approach"
        : entry < 0.7
          ? "brake"
          : entry < 0.76
            ? "touchdown"
            : entry < 0.9
              ? "absorb"
              : entry < 1
                ? "settle"
                : exit < 0.015
                  ? "rest"
                  : exit < 0.22
                    ? "crouch"
                    : exit < 0.4
                      ? "push"
                      : exit < 0.5
                        ? "liftoff"
                        : "fly",
  };
}

// Shoulder-led power stroke followed by a folded recovery. Phase delays are
// fractions of one beat, not accumulated spring state, so scrubbing retraces it.
function pokemonCharizardWingBeat(time, motion) {
  const ease = (a, b, x) => {
    const t = Math.max(0, Math.min(1, (x - a) / (b - a)));
    return t * t * (3 - 2 * t);
  };
  const down = 0.42;
  const launch =
    ease(0.015, 0.14, motion.exit) * (1 - ease(0.96, 1, motion.exit));
  // Three visible power strokes: the first overlaps leg extension and toe-off;
  // the second and third continue supporting and accelerating the airborne body.
  // Each recovery returns to the raised pose before the next depression.
  const launchPhase =
    down * ease(0.2, 0.4, motion.exit) +
    (1 - down) * ease(0.4, 0.48, motion.exit) +
    down * ease(0.48, 0.56, motion.exit) +
    (1 - down) * ease(0.56, 0.64, motion.exit) +
    down * ease(0.64, 0.72, motion.exit) +
    (1 - down) * ease(0.72, 0.8, motion.exit) +
    ease(0.8, 0.96, motion.exit);
  const cycle = time * 0.82;
  const sample = (phase, folding, force = false) => {
    const p = ((phase % 1) + 1) % 1;
    if (force) return p < down ? Math.sin((p / down) * Math.PI) ** 2 : 0;
    if (folding)
      return p < down ? 0 : Math.sin(((p - down) / (1 - down)) * Math.PI) ** 2;
    return p < down
      ? Math.cos((p / down) * Math.PI)
      : -Math.cos(((p - down) / (1 - down)) * Math.PI);
  };
  const blend = (lag, folding, force = false) => {
    const cruising = sample(cycle - lag, folding, force);
    // Clamp the first stroke's delayed joints at the raised pose, rather than
    // wrapping the elbow/wrist into a fictitious preceding recovery stroke.
    return (
      cruising * (1 - launch) +
      sample(Math.max(0, launchPhase - lag), folding, force) * launch
    );
  };
  return {
    launch,
    launchPhase,
    stroke: (lag = 0) => blend(lag, false),
    fold: (lag = 0) => blend(lag, true),
    power: (lag = 0) => blend(lag, false, true),
  };
}
