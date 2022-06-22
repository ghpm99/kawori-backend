from django.urls import path
from . import views

urlpatterns = [
    path('', views.get_facetexture_config, name='facetexture_get_config'),
]
