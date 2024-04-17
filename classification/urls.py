from django.urls import path
from . import views

urlpatterns = [
    path('get-question', views.get_all_questions, name='classification_get_all_questions')
]
