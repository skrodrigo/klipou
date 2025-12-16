export type OrganizationStats = {
  total_videos: number;
  total_clips: number;
  total_jobs: number;
  successful_jobs: number;
  failed_jobs: number;
  average_processing_time: number;
  credits_used_this_month: number;
  credits_available: number;
};

export type GetOrganizationStatsResponse = {
  organization_id: string;
  stats: OrganizationStats;
};

export type JobPerformance = {
  job_id: string;
  status: string;
  processing_time: number;
  clips_generated: number;
  credits_used: number;
  created_at: string;
  completed_at: string | null;
};

export type GetJobPerformanceResponse = {
  organization_id: string;
  jobs: JobPerformance[];
  total: number;
};

export type FailureAnalysis = {
  step: string;
  failure_count: number;
  success_rate: number;
  average_duration: number;
  last_error: string | null;
};

export type GetFailureAnalysisResponse = {
  organization_id: string;
  failures: FailureAnalysis[];
};

export type CreditUsage = {
  date: string;
  credits_used: number;
  jobs_processed: number;
};

export type GetCreditUsageResponse = {
  organization_id: string;
  usage: CreditUsage[];
  total_used_this_month: number;
  total_available: number;
};

export type ClipPerformanceMetrics = {
  platform: string;
  views: number;
  likes: number;
  shares: number;
  comments: number;
  engagement_rate: number;
  updated_at: string;
};

export type GetClipPerformanceResponse = {
  clip_id: string;
  performance: ClipPerformanceMetrics[];
};
