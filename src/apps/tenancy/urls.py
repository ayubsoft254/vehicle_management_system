from django.urls import path

from . import views

urlpatterns = [
    path('login/', views.PlatformLoginView.as_view(), name='login'),
    path('logout/', views.PlatformLogoutView.as_view(), name='logout'),
    path('', views.company_list, name='company_list'),
    path('companies/new/', views.company_create, name='company_create'),
    path('companies/<int:pk>/', views.company_detail, name='company_detail'),
    path('companies/<int:pk>/status/', views.company_status, name='company_status'),
    path('companies/<int:pk>/suspend/', views.company_suspend, name='company_suspend'),
    path('companies/<int:pk>/reactivate/', views.company_reactivate, name='company_reactivate'),
    path('companies/<int:pk>/retry/', views.company_retry, name='company_retry'),
    path('companies/<int:pk>/resend-login/', views.company_resend_login, name='company_resend_login'),
    path('companies/<int:pk>/open/', views.company_open, name='company_open'),
    path('companies/<int:pk>/domains/add/', views.domain_add, name='domain_add'),
    path('companies/<int:pk>/domains/<int:domain_id>/remove/', views.domain_remove, name='domain_remove'),
    path('companies/<int:pk>/domains/<int:domain_id>/primary/', views.domain_make_primary,
         name='domain_make_primary'),
]
