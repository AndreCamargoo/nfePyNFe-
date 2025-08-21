from django.urls import path
from . import views


urlpatterns = [
    path('notifications/sendmessage/', views.SendNotificationAPIView.as_view(), name='notifications-sendmessage-create-list'),
]
