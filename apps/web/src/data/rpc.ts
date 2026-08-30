export const PUBLIC_DASHBOARD_RPC = "get_public_dashboard_snapshot_v3" as const;
export const PUBLIC_STUDY_COVERAGE_RPC = "get_public_study_coverage_v1" as const;
export const ADMIN_DASHBOARD_RPC = "get_admin_dashboard_snapshot_v1" as const;

interface RpcResult {
  readonly data: unknown;
  readonly error: unknown | null;
}

export function unwrapRpcSnapshot(result: RpcResult): unknown {
  if (result.error !== null) {
    throw new Error("Aggregate snapshot request failed");
  }
  return result.data;
}
