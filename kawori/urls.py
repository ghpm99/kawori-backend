from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

financial_urls = [
    path("contract/", include("contract.urls")),
    path("invoice/", include("invoice.urls")),
    path("payment/", include("payment.urls")),
    path("tag/", include("tag.urls")),
    path("report/", include("financial.urls")),
    path("earnings/", include("earnings.urls")),
    path("budget/", include("budget.urls")),
]

urlpatterns = [
    path("admin/", admin.site.urls),
    path("auth/", include("authentication.urls")),
    path("pusher/", include("pusher_webhook.urls")),
    path("remote/", include("remote.urls")),
    path("financial/", include(financial_urls)),
    path("discord/", include("discord.urls")),
    path("facetexture/", include("facetexture.urls")),
    path("classification/", include("classification.urls")),
    path("profile/", include("user_profile.urls")),
    path("analytics/", include("analytics.urls")),
    path("audit/", include("audit.urls")),
    path("mailer/", include("mailer.urls")),
    path("ai/", include("ai.urls")),
]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
