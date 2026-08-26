export type OperationalState = "healthy" | "attention" | "paused" | "unavailable";

export interface AdminStatusData {
  readonly fixture: boolean;
  readonly label: string;
  readonly generatedAt: string;
  readonly queue: {
    readonly queued: number;
    readonly running: number;
    readonly dead: number;
  };
  readonly pipeline: {
    readonly freshness: string;
    readonly accepted: number;
    readonly rejected: number;
    readonly activityOnly: number;
    readonly duplicates: number;
  };
  readonly workers: readonly {
    readonly id: string;
    readonly label: string;
    readonly state: OperationalState;
    readonly heartbeat: string;
    readonly currentWork: string;
  }[];
  readonly sources: readonly {
    readonly id: string;
    readonly label: string;
    readonly policy: "enabled" | "disabled";
    readonly freshness: string;
    readonly adapterStatus: OperationalState;
  }[];
  readonly jobs: readonly {
    readonly id: string;
    readonly label: string;
    readonly status: "queued" | "running" | "dead" | "completed" | "cancelled";
    readonly attempts: string;
    readonly freshness: string;
    readonly records: number;
  }[];
  readonly browserSessions: readonly {
    readonly id: string;
    readonly label: string;
    readonly browser: OperationalState;
    readonly extension: OperationalState;
    readonly login: "ready" | "required" | "expired";
    readonly freshness: string;
  }[];
  readonly adapters: readonly {
    readonly id: string;
    readonly label: string;
    readonly mode: "fixture" | "live" | "disabled";
    readonly status: OperationalState;
    readonly freshness: string;
  }[];
  readonly ai: {
    readonly requests: number;
    readonly inputTokens: number;
    readonly outputTokens: number;
    readonly estimatedCostAud: number;
    readonly budgetAud: number | null;
    readonly paused: boolean;
    readonly rows: readonly {
      readonly day: string;
      readonly stage: "extract" | "validate" | "escalate";
      readonly requests: number;
      readonly inputTokens: number;
      readonly outputTokens: number;
      readonly estimatedCostAud: number;
    }[];
  };
  readonly capacity: {
    readonly database: CapacityStatus;
    readonly storage: CapacityStatus;
  };
  readonly backup: CheckpointStatus;
  readonly aggregation: CheckpointStatus;
  readonly services: readonly {
    readonly id: string;
    readonly label: string;
    readonly status: OperationalState;
    readonly freshness: string;
  }[];
  readonly records: readonly {
    readonly id: string;
    readonly label: string;
    readonly decision: "accepted" | "rejected" | "activity-only" | "duplicate";
    readonly freshness: string;
  }[];
}

export interface CapacityStatus {
  readonly used: string;
  readonly limit: string;
  readonly usedPercent: number;
  readonly thresholdPercent: number;
  readonly status: OperationalState;
}

export interface CheckpointStatus {
  readonly status: OperationalState;
  readonly freshness: string;
  readonly detail: string;
}

export const ADMIN_DEMO_FIXTURE = {
  fixture: true,
  label: "Synthetic fixture · operational values are illustrative and read-only",
  generatedAt: "2026-08-25T03:00:00.000Z",
  queue: { queued: 18, running: 3, dead: 2 },
  pipeline: {
    freshness: "12 minutes ago",
    accepted: 146,
    rejected: 21,
    activityOnly: 37,
    duplicates: 14,
  },
  workers: [
    { id: "collector-01", label: "Collector", state: "healthy", heartbeat: "21 seconds ago", currentWork: "2 running" },
    { id: "ai-worker-01", label: "AI worker", state: "healthy", heartbeat: "34 seconds ago", currentWork: "1 running" },
    { id: "aggregator-01", label: "Aggregator", state: "attention", heartbeat: "8 minutes ago", currentWork: "idle" },
  ],
  sources: [
    { id: "youtube-metadata", label: "YouTube metadata", policy: "enabled", freshness: "12 minutes ago", adapterStatus: "healthy" },
    { id: "public-community", label: "Public community pages", policy: "enabled", freshness: "3 hours ago", adapterStatus: "attention" },
    { id: "retailer-unapproved", label: "Unapproved retailer domains", policy: "disabled", freshness: "never", adapterStatus: "paused" },
  ],
  jobs: [
    { id: "job-discover-01", label: "Metadata discovery", status: "running", attempts: "1 / 4", freshness: "2 minutes ago", records: 46 },
    { id: "job-validate-01", label: "Evidence validation", status: "queued", attempts: "0 / 3", freshness: "7 minutes ago", records: 91 },
    { id: "job-social-01", label: "Authenticated collection", status: "dead", attempts: "3 / 3", freshness: "2 hours ago", records: 0 },
  ],
  browserSessions: [
    { id: "browser-western", label: "Western social session", browser: "healthy", extension: "healthy", login: "required", freshness: "17 minutes ago" },
    { id: "browser-chinese", label: "Chinese social session", browser: "healthy", extension: "attention", login: "expired", freshness: "2 days ago" },
    { id: "browser-research", label: "General research session", browser: "healthy", extension: "healthy", login: "ready", freshness: "6 minutes ago" },
  ],
  adapters: [
    { id: "tcgdex", label: "TCGdex catalog", mode: "fixture", status: "healthy", freshness: "12 minutes ago" },
    { id: "youtube", label: "YouTube discovery", mode: "fixture", status: "healthy", freshness: "12 minutes ago" },
    { id: "opencli-western", label: "OpenCLI western social", mode: "disabled", status: "paused", freshness: "not connected" },
    { id: "scrapling-public", label: "Scrapling public pages", mode: "fixture", status: "attention", freshness: "3 hours ago" },
  ],
  ai: {
    requests: 364,
    inputTokens: 821000,
    outputTokens: 160000,
    estimatedCostAud: 4.92,
    budgetAud: 10,
    paused: false,
    rows: [
      { day: "2026-08-23", stage: "extract", requests: 184, inputTokens: 412000, outputTokens: 82000, estimatedCostAud: 2.48 },
      { day: "2026-08-24", stage: "validate", requests: 162, inputTokens: 368000, outputTokens: 69000, estimatedCostAud: 2.17 },
      { day: "2026-08-25", stage: "escalate", requests: 18, inputTokens: 41000, outputTokens: 9000, estimatedCostAud: 0.27 },
    ],
  },
  capacity: {
    database: { used: "312 MB", limit: "500 MB", usedPercent: 62, thresholdPercent: 80, status: "healthy" },
    storage: { used: "420 MB", limit: "1 GB", usedPercent: 42, thresholdPercent: 80, status: "healthy" },
  },
  backup: { status: "healthy", freshness: "9 hours ago", detail: "Latest synthetic backup checkpoint completed." },
  aggregation: { status: "attention", freshness: "42 minutes ago", detail: "Latest synthetic aggregate is outside the 30-minute target." },
  services: [
    { id: "collector", label: "Collector service", status: "healthy", freshness: "21 seconds ago" },
    { id: "ai-worker", label: "AI worker service", status: "healthy", freshness: "34 seconds ago" },
    { id: "aggregator", label: "Aggregator service", status: "attention", freshness: "8 minutes ago" },
    { id: "auth-browser", label: "Authenticated browser service", status: "attention", freshness: "17 minutes ago" },
  ],
  records: [
    { id: "record-accepted-01", label: "YouTube · Surging Sparks opening", decision: "accepted", freshness: "12 minutes ago" },
    { id: "record-rejected-01", label: "Community · incomplete opening", decision: "rejected", freshness: "28 minutes ago" },
    { id: "record-activity-01", label: "Social · auxiliary activity", decision: "activity-only", freshness: "44 minutes ago" },
    { id: "record-duplicate-01", label: "Cross-posted opening", decision: "duplicate", freshness: "1 hour ago" },
  ],
} as const satisfies AdminStatusData;
