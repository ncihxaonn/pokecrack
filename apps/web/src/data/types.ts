export type EvidenceState =
  | "ready"
  | "watch"
  | "anomaly"
  | "pending"
  | "insufficient";

export type ProductType = "Booster Box" | "ETB" | "Booster Bundle";

export interface CredibleInterval {
  readonly low: number;
  readonly high: number;
}

export interface ObservedMetric {
  readonly packsObserved: number;
  readonly openings: number;
  readonly independentSources: number;
  readonly baselineRate: number | null;
  readonly hitRate: number | null;
  readonly posteriorMean: number | null;
  readonly credibleInterval: CredibleInterval | null;
  readonly deltaFromBaseline: number | null;
  readonly state: EvidenceState;
  readonly sampleNote: string;
  readonly updatedAt: string;
}

export interface SetMetric extends ObservedMetric {
  readonly slug: string;
  readonly name: string;
  readonly series: string;
  readonly releaseDate: string;
  readonly signal: string;
}

export interface RegionMetric extends ObservedMetric {
  readonly slug: string;
  readonly name: string;
  readonly countryCode: string;
  readonly coverage: string;
}

export interface CountryMapCell extends ObservedMetric {
  readonly countryCode: string;
  readonly countryName: string;
  readonly periodStart: string;
  readonly periodEnd: string;
  readonly setScope: "all";
  readonly productScope: "all";
  readonly metricKey: "qualifying_hit_pack_rate";
  readonly metricVersion: string;
  readonly methodologyVersion: string;
}

export interface CatalogSet {
  readonly id: string;
  readonly slug: string;
  readonly name: string;
  readonly series: string | null;
  readonly releaseDate: string | null;
  readonly language: "en";
  readonly current: true;
  readonly refreshedAt: string;
}

export interface CatalogSnapshot {
  readonly source: "tcgdex";
  readonly name: "TCGdex";
  readonly language: "en";
  readonly status: "fresh" | "stale" | "attention" | "unavailable";
  readonly setCount: number;
  readonly upstreamSetCount: number | null;
  readonly lastCheckedAt: string | null;
  readonly lastChangedAt: string | null;
  readonly revision: number | null;
  readonly catalogOnly: true;
  readonly sets: readonly CatalogSet[];
}

export interface ObservationReadiness {
  readonly status: "empty" | "collecting" | "published";
  readonly period: Readonly<{ start: string; end: string }> | null;
  readonly observedPacks: number;
  readonly completeOpenings: number;
  readonly independentSources: null;
  readonly sourceCountryContributions: number;
  readonly countriesObserved: number;
  readonly countriesWithPublishedRate: number;
  readonly asOf: string | null;
  readonly methodologyVersion: string | null;
  readonly minimumPacks: 30;
  readonly minimumSources: 3;
  readonly watchMinimumPacks: 200;
  readonly metricKey: "qualifying_hit_pack_rate";
}

export interface RetailerMetric extends ObservedMetric {
  readonly slug: string;
  readonly name: string;
  readonly region: string;
  readonly channel: "specialty" | "mass-market" | "online" | "unknown";
}

export interface BatchMetric extends ObservedMetric {
  readonly code: string;
  readonly setSlug: string;
  readonly setName: string;
  readonly region: string;
  readonly productType: ProductType;
  readonly firstObserved: string;
  readonly lastObserved: string;
}

export interface TrendPoint {
  readonly date: string;
  readonly observedRate: number | null;
  readonly baselineRate: number | null;
  readonly packsObserved: number;
  readonly completeOpenings: number;
  readonly independentSources: number;
}

export type SourceAccess = "public" | "api-key" | "browser-auth-required";
export type SourceStatus = "operational" | "delayed" | "attention" | "paused";

export interface PublicSource {
  readonly id: string;
  readonly name: string;
  readonly kind: "catalog" | "video" | "community" | "social";
  readonly access: SourceAccess;
  readonly status: SourceStatus;
  readonly lastCollectedAt: string | null;
  readonly url: string;
  readonly note: string;
}

export type SocialPulseFreshness = "fresh" | "delayed" | "attention" | "paused";

export interface PublicSocialActivitySource {
  readonly id:
    | "bluesky_jetstream"
    | "nostr_multi_relay"
    | "mastodon_public_hashtag";
  readonly name:
    | "Bluesky Jetstream discovery"
    | "Nostr multi-relay discovery"
    | "Mastodon public hashtag discovery";
  readonly kind: "social";
  readonly access: "public";
  readonly status: SourceStatus;
  readonly freshness: SocialPulseFreshness;
  readonly lastCollectedAt: string | null;
  readonly newCandidates24h: number;
  readonly retainedCandidates: number;
  readonly activityOnly: true;
  readonly statisticsEligible: false;
}

export interface PublicSocialActivityPulse {
  readonly schemaVersion: "4.0.0";
  readonly window: Readonly<{ start: string; end: string }>;
  readonly activityOnly: true;
  readonly nonEvidence: true;
  readonly sources: readonly [
    PublicSocialActivitySource & {
      readonly id: "bluesky_jetstream";
      readonly name: "Bluesky Jetstream discovery";
    },
    PublicSocialActivitySource & {
      readonly id: "nostr_multi_relay";
      readonly name: "Nostr multi-relay discovery";
    },
    PublicSocialActivitySource & {
      readonly id: "mastodon_public_hashtag";
      readonly name: "Mastodon public hashtag discovery";
    },
  ];
}

export interface PublicServiceStatus {
  readonly id: string;
  readonly name: string;
  readonly status: "operational" | "degraded" | "maintenance";
  readonly detail: string;
  readonly checkedAt: string;
}

export interface AdminJob {
  readonly id: string;
  readonly name: string;
  readonly status: "running" | "queued" | "succeeded" | "failed";
  readonly lastRunAt: string | null;
  readonly nextRunAt: string | null;
  readonly records: number;
}

export interface BrowserSession {
  readonly id: string;
  readonly source: string;
  readonly status: "ready" | "auth-required" | "expired";
  readonly profile: string;
  readonly lastVerifiedAt: string | null;
}

export interface AiUsageRow {
  readonly day: string;
  readonly stage: "extract" | "validate" | "escalate";
  readonly requests: number;
  readonly inputTokens: number;
  readonly outputTokens: number;
  readonly estimatedAud: number;
}

export interface RecentActivity {
  readonly id: string;
  readonly observedAt: string;
  readonly platform: string;
  readonly setName: string;
  readonly productType: ProductType;
  readonly packCount: number;
  readonly region: string;
  readonly retailer: string;
  readonly evidenceTier: "A" | "B" | "activity-only";
  readonly classification: "rate-eligible" | "activity-only";
  readonly statisticsEligible: boolean;
  readonly published: boolean;
  readonly sourceUrl: string;
}

export interface SystemCheck {
  readonly id: string;
  readonly name: string;
  readonly status: "ok" | "warning" | "error";
  readonly value: string;
  readonly detail: string;
}

export interface DashboardData {
  readonly schemaVersion: "2.0.0";
  readonly mode: "demo" | "live";
  readonly generatedAt: string;
  readonly summary: {
    readonly observedPacks: number;
    readonly completeOpenings: number;
    readonly aiValidatedSources: number;
    readonly trackedSets: number;
    readonly trackedRegions: number;
    readonly batchSightings: number;
    readonly baselineHitRate: number | null;
    readonly globalCoverage: string;
    readonly methodologyVersion: string;
  };
  readonly catalog: CatalogSnapshot;
  readonly observations: ObservationReadiness;
  readonly mapCells: readonly CountryMapCell[];
  readonly sets: readonly SetMetric[];
  readonly regions: readonly RegionMetric[];
  readonly retailers: readonly RetailerMetric[];
  readonly batches: readonly BatchMetric[];
  readonly trend: readonly TrendPoint[];
  readonly sources: readonly PublicSource[];
  readonly socialActivityPulse?: PublicSocialActivityPulse;
  readonly services: readonly PublicServiceStatus[];
  readonly recentActivity: readonly RecentActivity[];
  readonly admin: {
    readonly jobs: readonly AdminJob[];
    readonly browserSessions: readonly BrowserSession[];
    readonly aiUsage: readonly AiUsageRow[];
    readonly system: readonly SystemCheck[];
  };
}

export type PublicDashboardData = Omit<DashboardData, "admin">;
export type AdminDashboardData = DashboardData["admin"];
