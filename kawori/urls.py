
from django.contrib import admin
from django.urls import path, include
from django.conf.urls.static import static
from django.conf import settings

urlpatterns = [
    path('admin/', admin.site.urls),
    path('auth/', include('authentication.urls')),
    path('pusher/', include('pusher_webhook.urls')),
    path('remote/', include('remote.urls')),
    path('financial/', include('financial.urls')),
    path('discord/', include('discord.urls')),
    path('facetexture/', include('facetexture.urls')),
    path('classification/', include('classification.urls')),
    path('profile/', include('user_profile.urls')),
]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
