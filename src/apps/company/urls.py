from django.urls import path

from . import views

app_name = 'company'

urlpatterns = [
    path('', views.company_settings, name='settings'),
    path('channels/new/', views.save_channel, name='channel_create'),
    path('channels/<int:pk>/', views.save_channel, name='channel_update'),
    path('preview/<str:kind>/', views.preview_pdf, name='preview_pdf'),
]
