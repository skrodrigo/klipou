"""
Views para gerenciamento de organizações.
"""

from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
import uuid

from ..models import Organization, CreditTransaction


@api_view(["POST"])
def create_organization(request):
    """
    Cria uma nova organização.
    
    Body:
    {
        "name": "string",
        "billing_email": "email@example.com",
        "plan": "starter|pro|business"
    }
    """
    try:
        name = request.data.get("name")
        billing_email = request.data.get("billing_email")
        plan = request.data.get("plan", "starter")

        if not name or not billing_email:
            return Response(
                {"error": "name and billing_email are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Define créditos iniciais por plano
        initial_credits = {
            "starter": 300,
            "pro": 1000,
            "business": 5000,
        }

        org = Organization.objects.create(
            name=name,
            billing_email=billing_email,
            plan=plan,
            credits_monthly=initial_credits.get(plan, 300),
            credits_available=initial_credits.get(plan, 300),
        )

        return Response(
            {
                "organization_id": str(org.organization_id),
                "name": org.name,
                "plan": org.plan,
                "credits_available": org.credits_available,
                "created_at": org.created_at.isoformat(),
            },
            status=status.HTTP_201_CREATED,
        )

    except Exception as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_400_BAD_REQUEST,
        )


@api_view(["GET"])
def get_organization(request, organization_id):
    """
    Obtém detalhes de uma organização.
    """
    try:
        org = Organization.objects.get(organization_id=organization_id)

        return Response(
            {
                "organization_id": str(org.organization_id),
                "name": org.name,
                "plan": org.plan,
                "billing_email": org.billing_email,
                "credits_available": org.credits_available,
                "credits_monthly": org.credits_monthly,
                "credits_purchased": org.credits_purchased,
                "stripe_customer_id": org.stripe_customer_id,
                "created_at": org.created_at.isoformat(),
                "updated_at": org.updated_at.isoformat(),
            },
            status=status.HTTP_200_OK,
        )

    except Organization.DoesNotExist:
        return Response(
            {"error": "Organization not found"},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_400_BAD_REQUEST,
        )


@api_view(["PUT"])
def update_organization(request, organization_id):
    """
    Atualiza dados de uma organização.
    
    Body:
    {
        "name": "string",
        "billing_email": "email@example.com"
    }
    """
    try:
        org = Organization.objects.get(organization_id=organization_id)

        # Atualiza campos
        if "name" in request.data:
            org.name = request.data["name"]

        if "billing_email" in request.data:
            org.billing_email = request.data["billing_email"]

        org.save()

        return Response(
            {
                "organization_id": str(org.organization_id),
                "name": org.name,
                "billing_email": org.billing_email,
                "updated_at": org.updated_at.isoformat(),
            },
            status=status.HTTP_200_OK,
        )

    except Organization.DoesNotExist:
        return Response(
            {"error": "Organization not found"},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_400_BAD_REQUEST,
        )


@api_view(["GET"])
def get_organization_credits(request, organization_id):
    """
    Obtém histórico de transações de crédito.
    
    Query params:
    - type: filtering por tipo (consumption, refund, purchase, monthly_renewal)
    - limit: número máximo de resultados (padrão 20)
    - offset: paginação (padrão 0)
    """
    try:
        type_filter = request.query_params.get("type")
        limit = int(request.query_params.get("limit", 20))
        offset = int(request.query_params.get("offset", 0))

        org = Organization.objects.get(organization_id=organization_id)

        query = CreditTransaction.objects.filter(organization_id=organization_id).order_by("-created_at")

        if type_filter:
            query = query.filter(type=type_filter)

        total = query.count()
        transactions = list(query[offset : offset + limit])

        transactions_data = []
        for tx in transactions:
            try:
                transactions_data.append({
                    "transaction_id": str(tx.transaction_id),
                    "amount": tx.amount,
                    "type": tx.type,
                    "reason": tx.reason,
                    "balance_after": tx.balance_after,
                    "created_at": tx.created_at.isoformat(),
                })
            except Exception as tx_error:
                print(f"[get_organization_credits] Error serializing transaction {tx.transaction_id}: {str(tx_error)}")
                continue

        return Response(
            {
                "organization_id": str(org.organization_id),
                "credits_available": org.credits_available,
                "total": total,
                "limit": limit,
                "offset": offset,
                "transactions": transactions_data,
            },
            status=status.HTTP_200_OK,
        )

    except Organization.DoesNotExist:
        return Response(
            {"error": "Organization not found"},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        import traceback
        print(f"[get_organization_credits] Error: {str(e)}")
        print(traceback.format_exc())
        return Response(
            {"error": str(e)},
            status=status.HTTP_400_BAD_REQUEST,
        )


@api_view(["POST"])
def add_team_member(request, organization_id):
    """
    Adiciona membro à organização.
    
    Body:
    {
        "email": "member@example.com",
        "role": "admin|editor|viewer"
    }
    
    TODO: Implementar modelo TeamMember
    """
    try:
        org = Organization.objects.get(organization_id=organization_id)
        email = request.data.get("email")
        role = request.data.get("role", "editor")

        if not email:
            return Response(
                {"error": "email is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # TODO: Criar TeamMember
        # TODO: Enviar email de convite

        return Response(
            {
                "status": "invitation_sent",
                "email": email,
                "role": role,
            },
            status=status.HTTP_201_CREATED,
        )

    except Organization.DoesNotExist:
        return Response(
            {"error": "Organization not found"},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_400_BAD_REQUEST,
        )


@api_view(["DELETE"])
def remove_team_member(request, organization_id, member_id):
    """
    Remove membro da organização.
    
    Body:
    {
        "organization_id": "uuid"
    }
    
    TODO: Implementar modelo TeamMember
    """
    try:
        org = Organization.objects.get(organization_id=organization_id)

        # TODO: Deletar TeamMember

        return Response(
            {
                "status": "member_removed",
            },
            status=status.HTTP_200_OK,
        )

    except Organization.DoesNotExist:
        return Response(
            {"error": "Organization not found"},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_400_BAD_REQUEST,
        )
