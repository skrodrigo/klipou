export type Plan = {
  name: string;
  price_usd: number;
  price_brl: number;
  credits_monthly: number;
};

export type BillingPlan = {
  plan_id: string;
  name: string;
  price_usd: number;
  price_brl: number;
  credits_monthly: number;
};

export type ListPlansResponse = {
  plans: BillingPlan[];
};

export type UpgradePlanPayload = {
  new_plan: string;
};

export type UpgradePlanResponse = {
  organization_id: string;
  old_plan: string;
  new_plan: string;
  status: string;
};

export type DowngradePlanPayload = {
  new_plan: string;
};

export type DowngradePlanResponse = {
  organization_id: string;
  current_plan: string;
  downgrade_plan: string;
  status: string;
};

export type CancelSubscriptionResponse = {
  organization_id: string;
  status: string;
  message: string;
};

export type BillingTransaction = {
  transaction_id: string;
  amount: number;
  type: string;
  reason: string;
  balance_after: number;
  created_at: string;
};

export type GetBillingHistoryResponse = {
  organization_id: string;
  transactions: BillingTransaction[];
};

export type PurchaseCreditsPayload = {
  package: "small" | "medium" | "large";
};

export type PurchaseCreditsResponse = {
  detail: string;
  credits_purchased: number;
  credits_available: number;
  amount_charged: number;
};
