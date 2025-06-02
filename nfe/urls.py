from django.urls import path
from . import views


urlpatterns = [
    path('nfes/', views.NfeListCreateAPIView.as_view(), name='nfe-create-list'),
    path('nfes/<int:pk>/', views.NfeRetrieveUpdateDestroyAPIView.as_view(), name='nfe-detail-view'),
]
