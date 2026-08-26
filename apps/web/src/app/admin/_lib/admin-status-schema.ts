import { z } from "zod";

const operationalState = z.enum(["healthy", "attention", "paused", "unavailable"]);

function databaseText(maxCodePoints: number, blankMessage: string) {
  return z.string()
    // PostgreSQL char_length/left count Unicode code points while JavaScript
    // string.length counts UTF-16 code units. The first bound is a hard payload
    // cap; the second matches the database contract exactly.
    .min(1)
    .max(maxCodePoints * 2)
    .refine((value) => Array.from(value).length <= maxCodePoints, `Must contain at most ${maxCodePoints} characters`)
    // PostgreSQL btrim(text) removes the ordinary space character by default.
    .refine((value) => value.replace(/^ +| +$/gu, "").length > 0, blankMessage);
}

const identifier = databaseText(160, "Identifier must not be blank");
const label = databaseText(160, "Label must not be blank");
const freshness = databaseText(160, "Freshness must not be blank");
const shortText = databaseText(160, "Value must not be blank");
const detail = databaseText(500, "Detail must not be blank");
const count = z.number().int().min(0).max(Number.MAX_SAFE_INTEGER);
const tokenCount = z.number().int().min(0).max(Number.MAX_SAFE_INTEGER);
const moneyAud = z.number().finite().min(0).max(Number.MAX_SAFE_INTEGER);

const worker = z.object({
  id: identifier,
  label,
  state: operationalState,
  heartbeat: freshness,
  currentWork: shortText,
}).strict();

const source = z.object({
  id: identifier,
  label,
  policy: z.enum(["enabled", "disabled"]),
  freshness,
  adapterStatus: operationalState,
}).strict();

const job = z.object({
  id: identifier,
  label,
  status: z.enum(["queued", "running", "dead", "completed", "cancelled"]),
  attempts: databaseText(32, "Attempts must not be blank"),
  freshness,
  records: count,
}).strict();

const browserSession = z.object({
  id: identifier,
  label,
  browser: operationalState,
  extension: operationalState,
  login: z.enum(["ready", "required", "expired"]),
  freshness,
}).strict();

const adapter = z.object({
  id: identifier,
  label,
  mode: z.enum(["fixture", "live", "disabled"]),
  status: operationalState,
  freshness,
}).strict();

const aiUsageRow = z.object({
  day: z.string().regex(/^\d{4}-\d{2}-\d{2}$/),
  stage: z.enum(["extract", "validate", "escalate"]),
  requests: count,
  inputTokens: tokenCount,
  outputTokens: tokenCount,
  estimatedCostAud: moneyAud,
}).strict();

const capacity = z.object({
  used: databaseText(64, "Used capacity must not be blank"),
  limit: databaseText(64, "Capacity limit must not be blank"),
  usedPercent: z.number().finite().min(0).max(100),
  thresholdPercent: z.number().finite().min(0).max(100),
  status: operationalState,
}).strict();

const checkpoint = z.object({
  status: operationalState,
  freshness,
  detail,
}).strict();

const service = z.object({
  id: identifier,
  label,
  status: operationalState,
  freshness,
}).strict();

const record = z.object({
  id: identifier,
  label,
  decision: z.enum(["accepted", "rejected", "activity-only", "duplicate"]),
  freshness,
}).strict();

export const liveAdminStatusDataSchema = z.object({
  fixture: z.literal(false),
  label: databaseText(200, "Snapshot label must not be blank"),
  generatedAt: z.string().datetime({ offset: true }),
  queue: z.object({
    queued: count,
    running: count,
    dead: count,
  }).strict(),
  pipeline: z.object({
    freshness,
    accepted: count,
    rejected: count,
    activityOnly: count,
    duplicates: count,
  }).strict(),
  workers: z.array(worker).max(50),
  sources: z.array(source).max(50),
  jobs: z.array(job).max(100),
  browserSessions: z.array(browserSession).max(50),
  adapters: z.array(adapter).max(50),
  ai: z.object({
    requests: count,
    inputTokens: tokenCount,
    outputTokens: tokenCount,
    estimatedCostAud: moneyAud,
    budgetAud: moneyAud.nullable(),
    paused: z.boolean(),
    rows: z.array(aiUsageRow).max(100),
  }).strict(),
  capacity: z.object({
    database: capacity,
    storage: capacity,
  }).strict(),
  backup: checkpoint,
  aggregation: checkpoint,
  services: z.array(service).max(100),
  records: z.array(record).max(50),
}).strict();
