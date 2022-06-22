from django.urls import path
from . import views

urlpatterns = [
    path('', views.get_facetexture_config, name='facetexture_get_config'),
    path('save', views.save_detail_view, name='facetexture_save'),
    path('class', views.get_bdo_class, name='facetexture_bdo_class'),
]
