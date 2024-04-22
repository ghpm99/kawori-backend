from django.urls import path
from . import views

urlpatterns = [
    path('get-question/', views.get_all_questions, name='classification_get_all_questions'),
    path('get-answer/', views.get_all_answers, name='classification_get_all_answers'),
    path('register-answer/', views.register_answer, name='classification_register_answer'),
]
