# urls.py

from django.urls import path
from .views import (
    CustomTokenObtainAPIView, CustomTokenRefreshAPIView, LogoutView,
    UserProfileView, UserProfileCreateView, UserUpdateProfile,
    PasswordResetRequestAPIView, PasswordResetConfirmAPIView,
    UsersList, UserPermissionsView, UserDetailAdminView, UserAdminManageView,
    UserAdminDeleteView
)

urlpatterns = [
    # Login/Logout com HttpOnly cookies
    path('authentication/token/', CustomTokenObtainAPIView.as_view(), name='login'),
    path('authentication/token/refresh/', CustomTokenRefreshAPIView.as_view(), name='token_refresh'),
    path('authentication/logout/', LogoutView.as_view(), name='logout'),

    # User management (público)
    path('accounts/signup/', UserProfileCreateView.as_view(), name='user_profile_create'),
    path('accounts/password-reset/', PasswordResetRequestAPIView.as_view(), name='password_reset_request'),
    path('accounts/change-password/', PasswordResetConfirmAPIView.as_view(), name='change_password_confirm'),

    # Profile (próprio usuário)
    path('authentication/token/me/', UserProfileView.as_view(), name='user_profile'),
    path('accounts/users/<int:pk>/', UserUpdateProfile.as_view(), name='user_profile_update'),

    # Admin - buscar usuário por ID
    path('authentication/users/<int:pk>/', UserDetailAdminView.as_view(), name='user-detail-admin'),

    # Admin - criar/atualizar usuário (NOVAS ROTAS)
    path('admin/users/', UserAdminManageView.as_view(), name='admin-user-create'),
    path('admin/users/<int:pk>/', UserAdminManageView.as_view(), name='admin-user-update'),

    # Permissions
    path('authentication/permissions/', UserPermissionsView.as_view(), name='user_permissions'),

    # Users list (admin only)
    path('authentication/users/', UsersList.as_view(), name='list-users-view'),

    # Admin - deletar usuário
    path('admin/users/<int:pk>/delete/', UserAdminDeleteView.as_view(), name='admin-user-delete'),
]
