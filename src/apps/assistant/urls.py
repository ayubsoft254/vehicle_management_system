"""
Assistant App - URL Configuration
"""

from django.urls import path
from . import views

app_name = 'assistant'

urlpatterns = [
    path('ask/', views.ask, name='ask'),
    path('suggestions/', views.suggestions, name='suggestions'),
]
