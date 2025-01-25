from django.urls import path, include
from . import views

urlpatterns = [
    path('', views.get_facetexture_config, name='facetexture_get_config'),
    path('save', views.save_detail_view, name='facetexture_save'),
    path('class', views.get_bdo_class, name='facetexture_bdo_class'),
    path('preview', views.preview_background, name='facetexture_preview_background'),
    path('download', views.download_background, name='facetexture_download_background'),
    path('new', views.new_character, name='facetexture_new_character'),
    path('<int:id>/', include([
        path('reorder', views.reorder_character, name='facetexture_reorder_character'),
        path('change-class', views.change_class_character, name='facetexture_change_class'),
        path('change-name', views.change_character_name, name='facetexture_change_name'),
        path('change-visible', views.change_show_class_icon, name='facetexture_change_show_class_icon'),
        path('delete', views.delete_character, name='facetexture_delete_character'),
        path('get-symbol-class', views.get_symbol_class_view, name='facetexture_get_symbol_class'),
        path('get-image-class', views.get_image_class_view, name='facetexture_get_image_class'),
    ]))
]
