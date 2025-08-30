from django.urls import path
from . import views

urlpatterns = [
    path('nfes/resumo/', views.ResumoNFeProcessAPIView.as_view(), name='nfe-resumo-create'),
]
