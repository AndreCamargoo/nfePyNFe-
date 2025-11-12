from django.urls import path
from . import views


urlpatterns = [
    path('cloud/segmentos/', views.SegmentoListCreateAPIView.as_view(), name='segmento-create-list'),
    path('cloud/segmento/<int:pk>/', views.SegmengoRetrieveUpdateDestroyAPIView.as_view(), name='segmento-detail'),
]
