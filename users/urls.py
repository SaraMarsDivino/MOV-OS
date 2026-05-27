from django.urls import path

from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('admin/', views.admin_dashboard, name='admin_dashboard'),
    path('profile/', views.profile, name='profile'),
    path('login/', views.custom_login, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('management/', views.user_management, name='user_management'),
    path('api/users/', views.api_users_list, name='api_users_list'),
    path('api/user-sucursales/', views.api_user_sucursales_list, name='api_user_sucursales_list'),
    path('api/users/<int:user_id>/', views.api_user_detail, name='api_user_detail'),
    path('api/users/<int:user_id>/update/', views.api_user_update, name='api_user_update'),
    path('api/users/create/', views.api_user_create, name='api_user_create'),
    path('api/users/<int:user_id>/set-active/', views.set_user_active, name='api_set_user_active'),
    path('management/create/', views.create_user, name='create_user'),
    path('management/edit/<int:user_id>/', views.edit_user, name='edit_user'),
    path('management/delete/<int:user_id>/', views.delete_user, name='delete_user'),
]

