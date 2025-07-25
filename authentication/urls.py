from django.urls import path
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView
)
from .views import UserProfileView, UserProfileCreateView, UserUpdateProfile

urlpatterns = [
    path('authentication/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('authentication/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('authentication/token/verify/', TokenVerifyView.as_view(), name='token_verify'),
    path('authentication/token/me/', UserProfileView.as_view(), name='user_profile'),
    path('accounts/signup/', UserProfileCreateView.as_view(), name='user_profile_create'),
    path('accounts/users/<int:pk>/', UserUpdateProfile.as_view(), name='user_profile_update'),
]
