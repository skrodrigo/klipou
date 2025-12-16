import { request } from "../http";
import type {
  GetOrganizationStatsResponse,
  GetJobPerformanceResponse,
  GetFailureAnalysisResponse,
  GetCreditUsageResponse,
  GetClipPerformanceResponse,
} from "./types/analytics-types";

export type {
  GetOrganizationStatsResponse,
  GetJobPerformanceResponse,
  GetFailureAnalysisResponse,
  GetCreditUsageResponse,
  GetClipPerformanceResponse,
};

export async function getOrganizationStats(organizationId: string): Promise<GetOrganizationStatsResponse> {
  return request<GetOrganizationStatsResponse>(
    `/api/organizations/${organizationId}/analytics/stats/`,
    {
      method: "GET",
    }
  );
}

export async function getJobPerformance(organizationId: string): Promise<GetJobPerformanceResponse> {
  return request<GetJobPerformanceResponse>(
    `/api/organizations/${organizationId}/analytics/performance/`,
    {
      method: "GET",
    }
  );
}

export async function getFailureAnalysis(organizationId: string): Promise<GetFailureAnalysisResponse> {
  return request<GetFailureAnalysisResponse>(
    `/api/organizations/${organizationId}/analytics/failures/`,
    {
      method: "GET",
    }
  );
}

export async function getCreditUsage(organizationId: string): Promise<GetCreditUsageResponse> {
  return request<GetCreditUsageResponse>(
    `/api/organizations/${organizationId}/analytics/credits/`,
    {
      method: "GET",
    }
  );
}

export async function getClipPerformance(clipId: string): Promise<GetClipPerformanceResponse> {
  return request<GetClipPerformanceResponse>(`/api/clips/${clipId}/performance/`, {
    method: "GET",
  });
}
