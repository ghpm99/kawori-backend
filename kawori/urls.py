
from django.contrib import admin
from django.urls import path, include
from django.conf.urls.static import static
from django.conf import settings

urlpatterns = [
    path('admin/', admin.site.urls),
    path('pusher/', include('pusher_webhook.urls')),
    path('remote/', include('remote.urls')),
    path('auth/', include('authentication.urls')),
    path('financial/', include('financial.urls')),
]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)