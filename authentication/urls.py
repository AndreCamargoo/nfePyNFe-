from django.urls import path
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView
)
from .views import (
    CustomTokenObtainPairView, CustomTokenRefreshView, CustomTokenVerifyView,
    UserProfileView, UserProfileCreateView, UserUpdateProfile,
    PasswordResetRequestAPIView, PasswordResetConfirmAPIView, UsersList
)

urlpatterns = [
    path('authentication/token/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('authentication/token/refresh/', CustomTokenRefreshView.as_view(), name='token_refresh'),
    path('authentication/token/verify/', CustomTokenVerifyView.as_view(), name='token_verify'),

    path('accounts/signup/', UserProfileCreateView.as_view(), name='user_profile_create'),
    path('accounts/password-reset/', PasswordResetRequestAPIView.as_view(), name='password_reset_request'),
    path('accounts/change-password/', PasswordResetConfirmAPIView.as_view(), name='change_password_confirm'),

    path('authentication/token/me/', UserProfileView.as_view(), name='user_profile'),
    path('accounts/users/<int:pk>/', UserUpdateProfile.as_view(), name='user_profile_update'),

    path('authentication/users/', UsersList.as_view(), name='list-users-view'),
]
