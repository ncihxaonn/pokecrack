import type { CredibleInterval, EvidenceState } from "@/data/types";

export type SignalTone = "neutral" | "warning" | "alert" | "muted";

export const PUBLIC_SIGNAL_LABELS = [
  "Insufficient sample",
  "No significant signal",
  "Watch",
  "Possible anomaly",
] as const;

export interface SignalPresentation {
  readonly label: string;
  readonly tone: SignalTone;
  readonly detail: string;
}

const SIGNALS: Record<EvidenceState, SignalPresentation> = {
  ready: {
    label: "No significant signal",
    tone: "neutral",
    detail: "The observed interval does not meet the configured signal threshold.",
  },
  watch: {
    label: "Watch",
    tone: "warning",
    detail: "The observation merits continued sampling but is not an anomaly finding.",
  },
  anomaly: {
    label: "Possible anomaly",
    tone: "alert",
    detail: "The configured observational threshold is met; causal interpretation is not supported.",
  },
  pending: {
    label: "Publication pending",
    tone: "muted",
    detail: "The evidence threshold is met, but the reviewed baseline and interval are not published yet.",
  },
  insufficient: {
    label: "Insufficient sample",
    tone: "muted",
    detail: "The publication threshold has not been met.",
  },

};

export function getSignalPresentation(state: EvidenceState): SignalPresentation {
  return SIGNALS[state];
}

interface ConfidenceInput {
  readonly packsObserved: number;
  readonly credibleInterval: CredibleInterval | null;
  readonly state: EvidenceState;
}

export interface ConfidencePresentation {
  readonly label: "High" | "Moderate" | "Limited" | "Unavailable";
  readonly detail: string;
}

export function getConfidence(input: ConfidenceInput): ConfidencePresentation {
  if (!input.credibleInterval) {
    return {
      label: "Unavailable",
      detail: "No outcome interval is published.",
    };
  }

  const width = input.credibleInterval.high - input.credibleInterval.low;
  if (input.state !== "insufficient" && input.packsObserved >= 1_000 && width <= 0.05) {
    return {
      label: "High",
      detail: "Large observed sample with a comparatively narrow interval.",
    };
  }
  if (input.state !== "insufficient" && input.packsObserved >= 200 && width <= 0.08) {
    return {
      label: "Moderate",
      detail: "Publication threshold met with a usable interval.",
    };
  }
  return {
    label: "Limited",
    detail: "Small sample or wide interval; interpret cautiously.",
  };
}
