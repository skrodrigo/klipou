import json
from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction

from clips.models import Organization, OrganizationMember

@csrf_exempt
def organizations_view(request: HttpRequest):
    if not request.user.is_authenticated:
        return JsonResponse({"detail": "Not authenticated"}, status=401)

    if request.method == "GET":
        return list_organizations(request)
    elif request.method == "POST":
        return create_organization(request)
    
    return JsonResponse({"detail": "Method not allowed"}, status=405)

def list_organizations(request: HttpRequest):
    memberships = OrganizationMember.objects.filter(user=request.user, is_active=True).select_related('organization')
    organizations = []
    for membership in memberships:
        org = membership.organization
        organizations.append({
            "organization_id": str(org.organization_id),
            "name": org.name,
            "color": org.color,
            "plan": org.plan,
            "credits_available": org.credits_available,
            "role": membership.role
        })
    return JsonResponse({"organizations": organizations}, status=200)

def create_organization(request: HttpRequest):
    try:
        data = json.loads(request.body)
        name = data.get("name")
        color = data.get("color")
        if not name:
            return JsonResponse({"detail": "Organization name is required"}, status=400)

        with transaction.atomic():
            new_organization = Organization.objects.create(name=name, color=color)
            OrganizationMember.objects.create(
                user=request.user,
                organization=new_organization,
                role="admin"
            )
            request.user.current_organization = new_organization
            request.user.save()

        return JsonResponse({
            "organization_id": str(new_organization.organization_id),
            "name": new_organization.name,
            "color": new_organization.color,
            "plan": new_organization.plan,
            "credits_available": new_organization.credits_available,
        }, status=201)
    except json.JSONDecodeError:
        return JsonResponse({"detail": "Invalid JSON"}, status=400)
    except Exception as e:
        return JsonResponse({"detail": str(e)}, status=500)

@csrf_exempt
def switch_organization_view(request: HttpRequest):
    if not request.user.is_authenticated:
        return JsonResponse({"detail": "Not authenticated"}, status=401)
    
    if request.method != 'POST':
        return JsonResponse({"detail": "Method not allowed"}, status=405)

    try:
        data = json.loads(request.body)
        organization_id = data.get("organization_id")
        if not organization_id:
            return JsonResponse({"detail": "organization_id is required"}, status=400)

        membership = OrganizationMember.objects.filter(user=request.user, organization_id=organization_id, is_active=True).first()
        if not membership:
            return JsonResponse({"detail": "You are not a member of this organization"}, status=403)

        request.user.current_organization = membership.organization
        request.user.save()

        return JsonResponse({"detail": "Organization switched successfully"}, status=200)

    except json.JSONDecodeError:
        return JsonResponse({"detail": "Invalid JSON"}, status=400)
    except Exception as e:
        return JsonResponse({"detail": str(e)}, status=500)
