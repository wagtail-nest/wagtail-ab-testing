from django.urls import path

from . import views

app_name = 'wagtail_ab_testing'
urlpatterns = [
    path('register-participant/', views.register_participant, name='register_participant'),
    path('goal-reached/', views.goal_reached, name='goal_reached'),
]
