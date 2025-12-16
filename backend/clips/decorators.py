"""
Decorators para validação de créditos, quotas e autenticação.
"""

from functools import wraps
from rest_framework.response import Response
from rest_framework import status
from django.core.cache import cache
from datetime import datetime, timedelta

from .models import Organization, CreditTransaction


def require_credits(view_func):
    """
    Decorator para validar créditos antes de criar job.
    Valida se organização tem créditos suficientes.
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        try:
            organization_id = request.data.get("organization_id")
            video_id = request.data.get("video_id")

            if not organization_id:
                return Response(
                    {"error": "organization_id is required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Obtém organização
            org = Organization.objects.get(organization_id=organization_id)

            # Obtém vídeo para calcular créditos necessários
            from .models import Video
            video = Video.objects.get(video_id=video_id)

            # Calcula créditos necessários (1 crédito = 1 minuto)
            # Se duração não foi preenchida, usa valor padrão de 5 créditos
            if video.duration:
                credits_needed = int(video.duration / 60) + (1 if video.duration % 60 > 0 else 0)
            else:
                credits_needed = 5  # Valor padrão para vídeos sem duração conhecida

            # Valida créditos disponíveis
            if org.credits_available < credits_needed:
                return Response(
                    {
                        "error_code": "INSUFFICIENT_CREDITS",
                        "message": f"Você precisa de {credits_needed} créditos, mas tem apenas {org.credits_available}.",
                        "user_action": "Compre créditos para continuar.",
                        "credits_needed": credits_needed,
                        "credits_available": org.credits_available,
                    },
                    status=status.HTTP_402_PAYMENT_REQUIRED,
                )

            # Armazena créditos necessários no request para usar depois
            request.credits_needed = credits_needed
            request.organization = org

            return view_func(request, *args, **kwargs)

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

    return wrapper


def require_quota(quota_type: str):
    """
    Decorator para validar quotas técnicas por plano.
    
    Tipos de quota:
    - clips_per_job
    - storage
    - social_connections
    - team_members
    - projects
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            try:
                organization_id = request.data.get("organization_id") or kwargs.get("organization_id")

                if not organization_id:
                    return Response(
                        {"error": "organization_id is required"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                org = Organization.objects.get(organization_id=organization_id)

                # Define limites por plano
                limits = {
                    "clips_per_job": {"starter": 50, "pro": 200, "business": 500},
                    "storage": {"starter": 100, "pro": 500, "business": float("inf")},
                    "social_connections": {"starter": 2, "pro": 6, "business": 20},
                    "team_members": {"starter": 1, "pro": 5, "business": 50},
                    "projects": {"starter": 1, "pro": 5, "business": float("inf")},
                }

                if quota_type not in limits:
                    return Response(
                        {"error": f"Unknown quota type: {quota_type}"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                limit = limits[quota_type].get(org.plan, 0)

                # Armazena limite no request
                request.quota_limit = limit
                request.organization = org

                return view_func(request, *args, **kwargs)

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

        return wrapper

    return decorator


def rate_limit(requests_per_hour: int = None, requests_per_minute: int = None):
    """
    Decorator para rate limiting por usuário e IP.
    
    Padrões:
    - Starter: 10 jobs/hora
    - Pro: 50 jobs/hora
    - Business: ilimitado
    - Global: 100 requisições/minuto por IP
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            try:
                # Obtém IP do cliente
                client_ip = _get_client_ip(request)
                user_id = request.data.get("user_id") or getattr(request.user, "id", None)

                # Rate limit por IP (global)
                if requests_per_minute:
                    ip_key = f"rate_limit:ip:{client_ip}:minute"
                    ip_count = cache.get(ip_key, 0)

                    if ip_count >= requests_per_minute:
                        return Response(
                            {
                                "error_code": "RATE_LIMIT_ERROR",
                                "message": f"Você atingiu o limite de {requests_per_minute} requisições por minuto.",
                                "user_action": "Tente novamente em alguns momentos.",
                            },
                            status=status.HTTP_429_TOO_MANY_REQUESTS,
                        )

                    cache.set(ip_key, ip_count + 1, 60)

                # Rate limit por usuário (por plano)
                if user_id and requests_per_hour:
                    user_key = f"rate_limit:user:{user_id}:hour"
                    user_count = cache.get(user_key, 0)

                    if user_count >= requests_per_hour:
                        return Response(
                            {
                                "error_code": "RATE_LIMIT_ERROR",
                                "message": f"Você atingiu o limite de {requests_per_hour} jobs por hora.",
                                "user_action": "Tente novamente em uma hora.",
                            },
                            status=status.HTTP_429_TOO_MANY_REQUESTS,
                        )

                    cache.set(user_key, user_count + 1, 3600)

                return view_func(request, *args, **kwargs)

            except Exception as e:
                return Response(
                    {"error": str(e)},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        return wrapper

    return decorator


def refund_credits_on_failure(view_func):
    """
    Decorator para estornar créditos automaticamente em caso de falha.
    Deve ser usado em tasks que consomem créditos.
    """
    @wraps(view_func)
    def wrapper(self, *args, **kwargs):
        try:
            # Executa task
            result = view_func(self, *args, **kwargs)
            return result

        except Exception as e:
            # Obtém job para estornar créditos
            from .models import Job

            job_id = kwargs.get("job_id") or (args[0] if args else None)

            if job_id:
                try:
                    job = Job.objects.get(id=job_id)
                    org = Organization.objects.get(organization_id=job.organization_id)

                    # Estorna créditos
                    credits_to_refund = job.credits_consumed

                    if credits_to_refund > 0:
                        org.credits_available += credits_to_refund
                        org.save()

                        # Registra transação
                        CreditTransaction.objects.create(
                            organization_id=org.organization_id,
                            job_id=job.job_id,
                            amount=-credits_to_refund,  # Negativo = estorno
                            type="refund",
                            reason=f"Estorno automático - Job falhou: {str(e)}",
                            balance_after=org.credits_available,
                        )

                except Exception as refund_error:
                    print(f"Erro ao estornar créditos: {refund_error}")

            raise

    return wrapper


def _get_client_ip(request):
    """Obtém IP real do cliente considerando proxies."""
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        ip = x_forwarded_for.split(",")[0]
    else:
        ip = request.META.get("REMOTE_ADDR")
    return ip
