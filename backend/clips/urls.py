from django.urls import path, re_path

from .views.videos_list_create_view import videos_list_create
from .views.video_clips_list_view import video_clips_list
from .views.video_progress_sse_view import video_progress_sse
from .views.video_status_update_view import video_status_update_view
from .views.job_views import get_job_status, list_jobs, sse_job_status
from .views.clip_views import download_clip, delete_clip, submit_clip_feedback, get_clip_details
from .views.stripe_webhook_view import stripe_webhook
from .views.schedule_views import list_schedules, create_schedule, update_schedule, cancel_schedule
from .views.integration_views import list_integrations, connect_integration, oauth_callback, disconnect_integration
from .views.organization_views import create_organization, get_organization, update_organization, get_organization_credits, add_team_member, remove_team_member
from .views.admin_views import reprocess_job, cancel_job, adjust_credits, get_job_failures, get_step_statistics
from .views.onboarding_views import complete_onboarding, get_onboarding, update_onboarding
from .views.team_member_views import list_team_members, invite_team_member, remove_team_member, update_team_member_role
from .views.webhook_views import create_webhook, list_webhooks, delete_webhook, test_webhook
from .views.billing_views import list_plans, upgrade_plan, downgrade_plan, cancel_subscription, get_billing_history, purchase_credits
from .views.analytics_views import get_organization_stats, get_job_performance, get_failure_analysis, get_credit_usage, get_clip_performance
from .views.template_views import list_templates, create_template, update_template, delete_template
from .views.admin_dashboard_views import admin_dashboard, system_health, block_organization, unblock_organization


urlpatterns = [
    # Videos
    path("videos/", videos_list_create, name="videos-list-create"),
    path("videos/<int:video_id>/clips/", video_clips_list, name="video-clips-list"),
    re_path(r"^videos/(?P<video_id>\d+)/progress/?$", video_progress_sse, name="video-progress-sse"),
    path("videos/<int:video_id>/status/", video_status_update_view, name="video-status-update"),
    
    # Jobs (SSE + Status)
    path("jobs/<uuid:job_id>/", get_job_status, name="get-job-status"),
    path("jobs/<uuid:job_id>/stream/", sse_job_status, name="sse-job-status"),
    path("organizations/<uuid:organization_id>/jobs/", list_jobs, name="list-jobs"),
    
    # Clips
    path("clips/<uuid:clip_id>/", get_clip_details, name="get-clip-details"),
    path("clips/<uuid:clip_id>/download/", download_clip, name="download-clip"),
    path("clips/<uuid:clip_id>/delete/", delete_clip, name="delete-clip"),
    path("clips/<uuid:clip_id>/feedback/", submit_clip_feedback, name="submit-clip-feedback"),
    
    # Stripe Webhook
    path("webhooks/stripe/", stripe_webhook, name="stripe-webhook"),
    
    # Schedules
    path("organizations/<uuid:organization_id>/schedules/", list_schedules, name="list-schedules"),
    path("schedules/", create_schedule, name="create-schedule"),
    path("schedules/<uuid:schedule_id>/", update_schedule, name="update-schedule"),
    path("schedules/<uuid:schedule_id>/cancel/", cancel_schedule, name="cancel-schedule"),
    
    # Integrations
    path("organizations/<uuid:organization_id>/integrations/", list_integrations, name="list-integrations"),
    path("integrations/connect/", connect_integration, name="connect-integration"),
    path("integrations/oauth-callback/", oauth_callback, name="oauth-callback"),
    path("integrations/<uuid:integration_id>/disconnect/", disconnect_integration, name="disconnect-integration"),
    
    # Organizations
    path("organizations/", create_organization, name="create-organization"),
    path("organizations/<uuid:organization_id>/", get_organization, name="get-organization"),
    path("organizations/<uuid:organization_id>/update/", update_organization, name="update-organization"),
    path("organizations/<uuid:organization_id>/credits/", get_organization_credits, name="get-organization-credits"),
    
    # Team Members
    path("organizations/<uuid:organization_id>/members/", list_team_members, name="list-team-members"),
    path("organizations/<uuid:organization_id>/members/invite/", invite_team_member, name="invite-team-member"),
    path("organizations/<uuid:organization_id>/members/<uuid:member_id>/", remove_team_member, name="remove-team-member"),
    path("organizations/<uuid:organization_id>/members/<uuid:member_id>/role/", update_team_member_role, name="update-team-member-role"),
    
    # Onboarding
    path("onboarding/", complete_onboarding, name="complete-onboarding"),
    path("onboarding/<int:user_id>/", get_onboarding, name="get-onboarding"),
    path("onboarding/<int:user_id>/update/", update_onboarding, name="update-onboarding"),
    
    # Webhooks
    path("webhooks/", create_webhook, name="create-webhook"),
    path("organizations/<uuid:organization_id>/webhooks/", list_webhooks, name="list-webhooks"),
    path("webhooks/<uuid:webhook_id>/", delete_webhook, name="delete-webhook"),
    path("webhooks/<uuid:webhook_id>/test/", test_webhook, name="test-webhook"),
    
    # Billing & Plans
    path("plans/", list_plans, name="list-plans"),
    path("organizations/<uuid:organization_id>/upgrade/", upgrade_plan, name="upgrade-plan"),
    path("organizations/<uuid:organization_id>/downgrade/", downgrade_plan, name="downgrade-plan"),
    path("organizations/<uuid:organization_id>/cancel/", cancel_subscription, name="cancel-subscription"),
    path("organizations/<uuid:organization_id>/billing/", get_billing_history, name="get-billing-history"),
    path("credits/purchase/", purchase_credits, name="purchase-credits"),
    
    # Analytics
    path("organizations/<uuid:organization_id>/analytics/stats/", get_organization_stats, name="get-organization-stats"),
    path("organizations/<uuid:organization_id>/analytics/performance/", get_job_performance, name="get-job-performance"),
    path("organizations/<uuid:organization_id>/analytics/failures/", get_failure_analysis, name="get-failure-analysis"),
    path("organizations/<uuid:organization_id>/analytics/credits/", get_credit_usage, name="get-credit-usage"),
    path("clips/<uuid:clip_id>/performance/", get_clip_performance, name="get-clip-performance"),
    
    # Templates
    path("templates/", list_templates, name="list-templates"),
    path("templates/create/", create_template, name="create-template"),
    path("templates/<uuid:template_id>/", update_template, name="update-template"),
    path("templates/<uuid:template_id>/delete/", delete_template, name="delete-template"),
    
    # Admin
    path("admin/dashboard/", admin_dashboard, name="admin-dashboard"),
    path("admin/system/health/", system_health, name="system-health"),
    path("admin/jobs/<uuid:job_id>/reprocess/", reprocess_job, name="reprocess-job"),
    path("admin/jobs/<uuid:job_id>/cancel/", cancel_job, name="cancel-job"),
    path("admin/organizations/<uuid:organization_id>/credits/adjust/", adjust_credits, name="adjust-credits"),
    path("admin/organizations/<uuid:organization_id>/block/", block_organization, name="block-organization"),
    path("admin/organizations/<uuid:organization_id>/unblock/", unblock_organization, name="unblock-organization"),
    path("admin/jobs/failures/", get_job_failures, name="get-job-failures"),
    path("admin/statistics/steps/", get_step_statistics, name="get-step-statistics"),
]
