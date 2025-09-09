from django.urls import path
from . import views

urlpatterns = [
    path('nfes/resumo/', views.ResumoNFeProcessAPIView.as_view(), name='nfe-resumo-create'),
    path('nfes/resumo/<int:pk>/', views.ResumoNFeRetriveUpdateDestroyAPIView.as_view(), name='nfe-resumo-detail'),
]
