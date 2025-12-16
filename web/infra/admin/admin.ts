import { request } from "../http";
import type {
  GetDashboardResponse,
  GetSystemHealthResponse,
  BlockOrganizationPayload,
  BlockOrganizationResponse,
  UnblockOrganizationResponse,
} from "./types/admin-types";

export type {
  GetDashboardResponse,
  GetSystemHealthResponse,
  BlockOrganizationPayload,
  BlockOrganizationResponse,
  UnblockOrganizationResponse,
};

export async function getDashboard(): Promise<GetDashboardResponse> {
  return request<GetDashboardResponse>("/api/admin/dashboard/", {
    method: "GET",
  });
}

export async function getSystemHealth(): Promise<GetSystemHealthResponse> {
  return request<GetSystemHealthResponse>("/api/admin/system/health/", {
    method: "GET",
  });
}

export async function blockOrganization(
  organizationId: string,
  payload: BlockOrganizationPayload
): Promise<BlockOrganizationResponse> {
  return request<BlockOrganizationResponse>(
    `/api/admin/organizations/${organizationId}/block/`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    }
  );
}

export async function unblockOrganization(organizationId: string): Promise<UnblockOrganizationResponse> {
  return request<UnblockOrganizationResponse>(
    `/api/admin/organizations/${organizationId}/unblock/`,
    {
      method: "POST",
    }
  );
}
