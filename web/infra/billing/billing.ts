import { request } from "../http";
import type {
  ListPlansResponse,
  UpgradePlanPayload,
  UpgradePlanResponse,
  DowngradePlanPayload,
  DowngradePlanResponse,
  CancelSubscriptionResponse,
  GetBillingHistoryResponse,
  PurchaseCreditsPayload,
  PurchaseCreditsResponse,
} from "./types/billing-types";

export type {
  ListPlansResponse,
  UpgradePlanPayload,
  UpgradePlanResponse,
  DowngradePlanPayload,
  DowngradePlanResponse,
  CancelSubscriptionResponse,
  GetBillingHistoryResponse,
  PurchaseCreditsPayload,
  PurchaseCreditsResponse,
};

export async function listPlans(): Promise<ListPlansResponse> {
  return request<ListPlansResponse>("/api/plans/", {
    method: "GET",
  });
}

export async function upgradePlan(
  organizationId: string,
  payload: UpgradePlanPayload
): Promise<UpgradePlanResponse> {
  return request<UpgradePlanResponse>(
    `/api/organizations/${organizationId}/upgrade/`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    }
  );
}

export async function downgradePlan(
  organizationId: string,
  payload: DowngradePlanPayload
): Promise<DowngradePlanResponse> {
  return request<DowngradePlanResponse>(
    `/api/organizations/${organizationId}/downgrade/`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    }
  );
}

export async function cancelSubscription(organizationId: string): Promise<CancelSubscriptionResponse> {
  return request<CancelSubscriptionResponse>(
    `/api/organizations/${organizationId}/cancel/`,
    {
      method: "POST",
    }
  );
}

export async function getBillingHistory(organizationId: string): Promise<GetBillingHistoryResponse> {
  return request<GetBillingHistoryResponse>(
    `/api/organizations/${organizationId}/billing/`,
    {
      method: "GET",
    }
  );
}

export async function purchaseCredits(
  payload: PurchaseCreditsPayload
): Promise<PurchaseCreditsResponse> {
  return request<PurchaseCreditsResponse>("/api/credits/purchase/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
