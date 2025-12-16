export type DashboardMetrics = {
  total_organizations: number;
  total_users: number;
  total_jobs_processed: number;
  total_jobs_failed: number;
  success_rate: number;
  average_processing_time: number;
  total_credits_used: number;
};

export type GetDashboardResponse = {
  metrics: DashboardMetrics;
  timestamp: string;
};

export type HealthCheckStatus = {
  database: "healthy" | "unhealthy";
  celery: "healthy" | "unhealthy";
  redis: "healthy" | "unhealthy";
  storage: "healthy" | "unhealthy";
};

export type GetSystemHealthResponse = {
  status: "healthy" | "degraded" | "unhealthy";
  checks: HealthCheckStatus;
  timestamp: string;
};

export type BlockOrganizationPayload = {
  reason: string;
};

export type BlockOrganizationResponse = {
  detail: string;
  organization_id: string;
  status: string;
};

export type UnblockOrganizationResponse = {
  detail: string;
  organization_id: string;
  status: string;
};
