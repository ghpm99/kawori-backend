from django.urls import path
from . import views

urlpatterns = [
    path('', views.get_facetexture_config, name='facetexture_get_config'),
    path('save', views.save_detail_view, name='facetexture_save'),
    path('class', views.get_bdo_class, name='facetexture_bdo_class'),
    path('preview', views.preview_background, name='facetexture_preview_background'),
    path('download', views.download_background, name='facetexture_download_background'),
    path('reorder', views.reorder_character, name='facetexture_reorder_character'),
]
