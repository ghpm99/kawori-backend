from django.conf import settings
from django.template.loader import render_to_string
from django.utils import timezone

from mailer.ai_assist import suggest_payment_notification_copy
from mailer.models import EmailQueue


def enqueue_email(
    to_email,
    subject,
    template_name,
    context,
    email_type=EmailQueue.TYPE_GENERIC,
    category=EmailQueue.CATEGORY_TRANSACTIONAL,
    priority=EmailQueue.PRIORITY_NORMAL,
    user=None,
    scheduled_at=None,
    max_retries=3,
    context_data=None,
):
    body_html = render_to_string(template_name, context)

    return EmailQueue.objects.create(
        user=user,
        to_email=to_email,
        from_email=settings.EMAIL_HOST_USER,
        subject=subject,
        body_html=body_html,
        email_type=email_type,
        category=category,
        priority=priority,
        scheduled_at=scheduled_at or timezone.now(),
        max_retries=max_retries,
        context_data=context_data or {},
    )


def enqueue_password_reset(user, raw_token):
    from authentication.models import UserToken

    reset_url = f"{settings.BASE_URL_FRONTEND}/reset-password?token={raw_token}"

    return enqueue_email(
        to_email=user.email,
        subject="Redefinição de senha - Kawori",
        template_name="password_reset_email.html",
        context={
            "user": user,
            "token": raw_token,
            "reset_url": reset_url,
            "expiry_minutes": UserToken.EXPIRY_CONFIG[
                UserToken.TOKEN_TYPE_PASSWORD_RESET
            ],
        },
        email_type=EmailQueue.TYPE_PASSWORD_RESET,
        category=EmailQueue.CATEGORY_TRANSACTIONAL,
        priority=EmailQueue.PRIORITY_HIGH,
        user=user,
    )


def enqueue_email_verification(user, raw_token):
    from authentication.models import UserToken

    verify_url = f"{settings.BASE_URL_FRONTEND}/verify-email?token={raw_token}"

    return enqueue_email(
        to_email=user.email,
        subject="Bem-vindo ao Kawori - Verifique seu email",
        template_name="email_verification.html",
        context={
            "user": user,
            "verify_url": verify_url,
            "expiry_hours": UserToken.EXPIRY_CONFIG[
                UserToken.TOKEN_TYPE_EMAIL_VERIFICATION
            ]
            // 60,
        },
        email_type=EmailQueue.TYPE_EMAIL_VERIFICATION,
        category=EmailQueue.CATEGORY_TRANSACTIONAL,
        priority=EmailQueue.PRIORITY_HIGH,
        user=user,
    )


def enqueue_payment_notification(user, payments, final_date):
    total_value = sum(float(p["value"]) for p in payments)
    ai_copy = suggest_payment_notification_copy(
        user, payments, final_date, channel="email"
    )
    subject_prefix = "Notificação de Pagamentos"
    if ai_copy and ai_copy.get("subject_prefix"):
        subject_prefix = ai_copy["subject_prefix"]

    return enqueue_email(
        to_email=user.email,
        subject=f'{subject_prefix} - Vencimento até {final_date.strftime("%d/%m/%Y")}',
        template_name="payment_email_template.html",
        context={
            "payments": payments,
            "total_value": total_value,
            "final_date": final_date.strftime("%d/%m/%Y"),
            "ai_intro": ai_copy.get("intro") if ai_copy else "",
            "ai_highlights": ai_copy.get("highlights", []) if ai_copy else [],
        },
        email_type=EmailQueue.TYPE_PAYMENT_NOTIFICATION,
        category=EmailQueue.CATEGORY_NOTIFICATION,
        priority=EmailQueue.PRIORITY_NORMAL,
        user=user,
        context_data={
            "ai_dedupe_key": ai_copy.get("dedupe_key") if ai_copy else "",
            "ai_copy": {
                "subject_prefix": ai_copy.get("subject_prefix") if ai_copy else "",
                "intro": ai_copy.get("intro") if ai_copy else "",
                "highlights": ai_copy.get("highlights", []) if ai_copy else [],
                "source": ai_copy.get("source") if ai_copy else "none",
            },
        },
    )
