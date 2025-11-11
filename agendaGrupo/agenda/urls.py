from django.urls import path
from . import views


urlpatterns = [
    path('agenda/evento-cadastros/', views.EventoCadastroListCreateAPIView.as_view(), name='evento-cadastro-create-list'),
    path('agenda/evento-cadastro/<int:pk>/', views.EventoCadastroRetrieveUpdateDestroyAPIView.as_view(), name='evento-cadastro-detail'),

    path('agenda/evento-contatos/', views.EventoContatoListCreateAPIView.as_view(), name='evento-contato-create-list'),
    path('agenda/evento-contato/<int:pk>/', views.EventoContatoRetrieveUpdateDestroyAPIView.as_view(), name='evento-contato-detail'),
]
