from django.urls import include, path
from . import views

tag_details_urls = [
    path("", views.detail_tag_view, name="tag_detail"),
]
urlpatterns = [
    path("", views.get_all_tag_view, name="financial_get_all_tags"),
    path("new", views.include_new_tag_view, name="financial_include_tag"),
    path("<int:id>/", include(tag_details_urls)),
]
