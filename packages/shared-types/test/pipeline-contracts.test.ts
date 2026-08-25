import { describe, expect, it } from "vitest";

import {
  extractorOutputSchema,
  sourceItemCandidateSchema,
  validatorOutputSchema,
} from "../src/index.js";

const candidate = {
  source_url: "https://www.youtube.com/watch?v=demo123",
  canonical_url: "https://www.youtube.com/watch?v=demo123",
  source_domain: "www.youtube.com",
  collector: "official_api",
  platform: "youtube",
  platform_id: "demo123",
  title: "Demo opening",
  excerpt: "Six packs were opened.",
  content: "Six packs were opened and one rare card was observed.",
  content_sha256: "a".repeat(64),
  author: "internal-source-handle",
  published_at: "2026-08-24T10:00:00Z",
  collected_at: "2026-08-24T10:05:00Z",
  metadata: { language: "en", duration_seconds: 90 },
  image_urls: ["https://img.example.test/frame-1.jpg"],
} as const;

const extractorOutput = {
  set_name: "Demo Set",
  product_name: "Booster Bundle",
  product_type: "booster_bundle",
  pack_count: 6,
  hits: [
    {
      card_name: "Demo Card",
      collector_number: "001/100",
      rarity_label: "double rare",
      quantity: 1,
    },
  ],
  country_code: "US",
  region: "United States West",
  retailer: null,
  batch_code: "DEMO-A",
  opened_at: "2026-08-24T10:00:00Z",
  evidence_tier: "A",
  confidence: 0.94,
  evidence: [
    {
      field: "pack_count",
      quote: "all six packs",
      source_locator: "00:12",
    },
  ],
} as const;

const validatorOutput = {
  decision: "accept",
  set_id: "sv-demo",
  set_name: "Demo Set",
  product_name: "Booster Bundle",
  product_type: "booster_bundle",
  pack_count: 6,
  hits: [
    {
      card_id: "sv-demo-001",
      card_name: "Demo Card",
      collector_number: "001/100",
      rarity_key: "double_rare",
      quantity: 1,
    },
  ],
  country_code: "US",
  region: "United States West",
  retailer: null,
  batch_code: "DEMO-A",
  opened_at: "2026-08-24T10:00:00Z",
  evidence_tier: "A",
  confidence: 0.92,
  conflict_codes: [],
} as const;

describe("SourceItemCandidate contract", () => {
  it("round trips the normalized collector boundary", () => {
    expect(sourceItemCandidateSchema.parse(candidate)).toEqual(candidate);
  });

  it("rejects unknown collectors and non-http source URLs", () => {
    expect(
      sourceItemCandidateSchema.safeParse({ ...candidate, collector: "youtube" }).success,
    ).toBe(false);
    expect(
      sourceItemCandidateSchema.safeParse({ ...candidate, source_url: "file:///etc/passwd" }).success,
    ).toBe(false);
    expect(() =>
      sourceItemCandidateSchema.safeParse({ ...candidate, source_url: "not a URL" }),
    ).not.toThrow();
    expect(
      sourceItemCandidateSchema.safeParse({ ...candidate, source_url: "not a URL" }).success,
    ).toBe(false);
  });

  it.each(["cookie", "token", "job_payload", "browser_profile"])(
    "rejects sensitive top-level field %s",
    (field) => {
      expect(
        sourceItemCandidateSchema.safeParse({ ...candidate, [field]: "private" }).success,
      ).toBe(false);
    },
  );

  it("rejects sensitive keys nested in collector metadata", () => {
    expect(
      sourceItemCandidateSchema.safeParse({
        ...candidate,
        metadata: { safe: { nested: true }, session: { access_token: "private" } },
      }).success,
    ).toBe(false);
  });
});

describe("extractor output contract", () => {
  it("round trips only structured factual output", () => {
    expect(extractorOutputSchema.parse(extractorOutput)).toEqual(extractorOutput);
  });

  it.each(["reasoning", "raw_ai_output", "prompt", "chain_of_thought"])(
    "rejects extractor field %s",
    (field) => {
      expect(
        extractorOutputSchema.safeParse({ ...extractorOutput, [field]: "private" }).success,
      ).toBe(false);
    },
  );

  it("enforces evidence tiers, confidence, and exact evidence field names", () => {
    expect(
      extractorOutputSchema.safeParse({ ...extractorOutput, evidence_tier: "official" }).success,
    ).toBe(false);
    expect(
      extractorOutputSchema.safeParse({ ...extractorOutput, confidence: 1.1 }).success,
    ).toBe(false);
    expect(
      extractorOutputSchema.safeParse({
        ...extractorOutput,
        product_type: "elite_trainer_box",
      }).success,
    ).toBe(false);
    expect(
      extractorOutputSchema.safeParse({
        ...extractorOutput,
        evidence: [{ field: "thoughts", quote: "private", source_locator: null }],
      }).success,
    ).toBe(false);
  });
});

describe("validator output contract", () => {
  it("round trips a strict independent validation result", () => {
    expect(validatorOutputSchema.parse(validatorOutput)).toEqual(validatorOutput);
  });

  it.each(["reasoning", "raw_ai_output", "model_response", "job_payload"])(
    "rejects validator field %s",
    (field) => {
      expect(
        validatorOutputSchema.safeParse({ ...validatorOutput, [field]: "private" }).success,
      ).toBe(false);
    },
  );

  it("enforces decision and evidence vocabularies", () => {
    expect(
      validatorOutputSchema.safeParse({ ...validatorOutput, decision: "approved" }).success,
    ).toBe(false);
    expect(
      validatorOutputSchema.safeParse({ ...validatorOutput, evidence_tier: "primary" }).success,
    ).toBe(false);
    expect(
      validatorOutputSchema.safeParse({ ...validatorOutput, product_type: "etb" }).success,
    ).toBe(true);
  });
});
