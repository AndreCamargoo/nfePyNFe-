from django.urls import path
from . import views


urlpatterns = [
    path('nfes/evento/', views.EventoNFeProcessAPIView.as_view(), name='nfe-evento-create-list'),
]
