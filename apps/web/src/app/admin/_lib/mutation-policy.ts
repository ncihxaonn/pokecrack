export const ADMIN_INVALID_REQUEST_MESSAGE = "The request was rejected by the admin safety policy.";
export const MAX_SOURCE_URL_CHARS = 2048;
export const ADMIN_IMPORT_LIMITS = {
  csv: 512 * 1024,
  jsonl: 1024 * 1024,
  opencli: 256 * 1024,
} as const;

export type AdminImportKind = keyof typeof ADMIN_IMPORT_LIMITS;
export type AdminControlActionName =
  | "job.retry"
  | "job.cancel"
  | "source.disable"
  | "record.exclude"
  | "browser.refresh"
  | "service.restart";
export type AdminActionName =
  | "source.enqueue"
  | "import.csv"
  | "import.jsonl"
  | "import.opencli"
  | AdminControlActionName;

export type AdminMutationCommand =
  | { readonly action: "source.enqueue"; readonly sourceUrl: string }
  | {
      readonly action: "import.csv" | "import.jsonl" | "import.opencli";
      readonly importKind: AdminImportKind;
      readonly byteLength: number;
    }
  | { readonly action: AdminControlActionName; readonly targetId: string };

export type AdminMutationParseResult =
  | { readonly ok: true; readonly command: AdminMutationCommand }
  | { readonly ok: false; readonly message: typeof ADMIN_INVALID_REQUEST_MESSAGE };

type AdminImportActionName = "import.csv" | "import.jsonl" | "import.opencli";

const IMPORT_RULES: Record<AdminImportActionName, {
  readonly kind: AdminImportKind;
  readonly extensions: readonly string[];
  readonly mimeTypes: readonly string[];
}> = {
  "import.csv": { kind: "csv", extensions: [".csv"], mimeTypes: ["", "text/csv", "application/vnd.ms-excel"] },
  "import.jsonl": { kind: "jsonl", extensions: [".jsonl", ".ndjson"], mimeTypes: ["", "application/x-ndjson", "application/jsonl", "application/json", "text/plain"] },
  "import.opencli": { kind: "opencli", extensions: [".json"], mimeTypes: ["", "application/json", "text/plain"] },
};

const CONTROL_ACTIONS: readonly AdminControlActionName[] = [
  "job.retry",
  "job.cancel",
  "source.disable",
  "record.exclude",
  "browser.refresh",
  "service.restart",
];

function invalid(): AdminMutationParseResult {
  return { ok: false, message: ADMIN_INVALID_REQUEST_MESSAGE };
}

function hasOnlyOneField(formData: FormData, field: string): boolean {
  const entries = Array.from(formData.entries());
  return entries.length === 1 && entries[0]?.[0] === field && formData.getAll(field).length === 1;
}

function parseSourceUrl(formData: FormData): AdminMutationParseResult {
  if (!hasOnlyOneField(formData, "sourceUrl")) return invalid();
  const value = formData.get("sourceUrl");
  if (typeof value !== "string") return invalid();

  const candidate = value.trim();
  if (candidate.length === 0 || candidate.length > MAX_SOURCE_URL_CHARS) return invalid();

  try {
    const parsed = new URL(candidate);
    if (
      parsed.protocol !== "https:" ||
      parsed.username ||
      parsed.password ||
      parsed.search ||
      parsed.hash ||
      !parsed.hostname
    ) return invalid();
    return { ok: true, command: { action: "source.enqueue", sourceUrl: parsed.toString() } };
  } catch {
    return invalid();
  }
}

function parseImport(
  action: AdminImportActionName,
  formData: FormData,
): AdminMutationParseResult {
  if (!hasOnlyOneField(formData, "file")) return invalid();
  const value = formData.get("file");
  if (!(value instanceof File)) return invalid();

  const rule = IMPORT_RULES[action];
  const lowerName = value.name.toLowerCase();
  const hasAllowedExtension = rule.extensions.some((extension) => lowerName.endsWith(extension));
  if (!hasAllowedExtension || !rule.mimeTypes.includes(value.type.toLowerCase())) return invalid();
  if (value.size < 1 || value.size > ADMIN_IMPORT_LIMITS[rule.kind]) return invalid();

  return {
    ok: true,
    command: { action, importKind: rule.kind, byteLength: value.size },
  };
}

function parseControl(action: AdminControlActionName, formData: FormData): AdminMutationParseResult {
  if (!hasOnlyOneField(formData, "targetId")) return invalid();
  const value = formData.get("targetId");
  if (typeof value !== "string") return invalid();
  const targetId = value.trim();
  if (!/^[a-z0-9][a-z0-9._:-]{0,127}$/.test(targetId) || targetId.includes("..")) return invalid();
  return { ok: true, command: { action, targetId } };
}

export function parseAdminMutation(action: AdminActionName, formData: FormData): AdminMutationParseResult {
  if (action === "source.enqueue") return parseSourceUrl(formData);
  if (action in IMPORT_RULES) return parseImport(action as AdminImportActionName, formData);
  if (CONTROL_ACTIONS.includes(action as AdminControlActionName)) return parseControl(action as AdminControlActionName, formData);
  return invalid();
}

export const ADMIN_CONTROL_UNAVAILABLE_MESSAGE =
  "This control is disabled until the restricted, audited admin RPC is configured.";
export const ADMIN_CONTROL_RPC_NAME = "admin_control_and_audit_v1";
export const ADMIN_CONTROL_FAILED_MESSAGE = "The control request was not accepted.";
export const ADMIN_CONTROL_SUCCESS_MESSAGE = "The audited control request was accepted.";

export interface AdminMutationActor {
  readonly userId: string;
  readonly email: string;
}

export interface AdminMutationDependencies {
  readonly enabled: boolean;
  readonly invoke: (rpcName: string, parameters: Readonly<Record<string, unknown>>) => Promise<unknown>;
  readonly revalidate: (path: string) => void;
  readonly invalidatePublicDashboard: () => void;
}

export interface AdminActionResult {
  readonly status: "success" | "failed" | "unavailable";
  readonly message: string;
}

const ACTION_PATHS: Record<AdminActionName, string> = {
  "source.enqueue": "/admin/sources",
  "import.csv": "/admin/sources",
  "import.jsonl": "/admin/sources",
  "import.opencli": "/admin/sources",
  "job.retry": "/admin/jobs",
  "job.cancel": "/admin/jobs",
  "source.disable": "/admin/sources",
  "record.exclude": "/admin/sources",
  "browser.refresh": "/admin/browser",
  "service.restart": "/admin/system",
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function acceptedRpcResult(value: unknown, command: AdminMutationCommand): boolean {
  if (!isRecord(value) || value.error !== null || !isRecord(value.data)) return false;
  const data = value.data;
  if (data.ok !== true || data.audit_written !== true) return false;
  return command.action !== "source.enqueue" || data.policy_validated === true;
}

function rpcParameters(
  command: AdminMutationCommand,
  actor: AdminMutationActor,
): Readonly<Record<string, unknown>> {
  const common = {
    p_action: command.action,
    p_actor_id: actor.userId,
    p_actor_email: actor.email,
  };
  if (command.action === "source.enqueue") {
    return { ...common, p_source_url: command.sourceUrl, p_target_id: null };
  }
  if ("targetId" in command) {
    return { ...common, p_source_url: null, p_target_id: command.targetId };
  }
  return { ...common, p_source_url: null, p_target_id: null };
}

export async function executeAdminMutation(
  command: AdminMutationCommand,
  actor: AdminMutationActor,
  dependencies: AdminMutationDependencies,
): Promise<AdminActionResult> {
  if (!dependencies.enabled || command.action.startsWith("import.")) {
    return { status: "unavailable", message: ADMIN_CONTROL_UNAVAILABLE_MESSAGE };
  }

  try {
    const response = await dependencies.invoke(ADMIN_CONTROL_RPC_NAME, rpcParameters(command, actor));
    if (!acceptedRpcResult(response, command)) {
      return { status: "failed", message: ADMIN_CONTROL_FAILED_MESSAGE };
    }
    dependencies.revalidate(ACTION_PATHS[command.action]);
    if (command.action === "record.exclude") {
      dependencies.invalidatePublicDashboard();
    }
    return { status: "success", message: ADMIN_CONTROL_SUCCESS_MESSAGE };
  } catch {
    return { status: "failed", message: ADMIN_CONTROL_FAILED_MESSAGE };
  }
}
