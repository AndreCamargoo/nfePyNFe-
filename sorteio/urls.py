from django.urls import path
from . import views

urlpatterns = [
    # Eventos
    path('sorteio/eventos/', views.EventoSorteioListCreateView.as_view(), name='sorteio-evento-list'),
    path('sorteio/eventos/<int:pk>/', views.EventoSorteioDetailView.as_view(), name='sorteio-evento-detail'),
    path('sorteio/eventos/<int:pk>/toggle/', views.EventoToggleView.as_view(), name='sorteio-evento-toggle'),
    path('sorteio/eventos/ativo/', views.EventoAtivoView.as_view(), name='sorteio-evento-ativo'),

    # Participantes
    path('sorteio/participar/', views.ParticipanteSorteioCreateView.as_view(), name='sorteio-participar'),
    path('sorteio/participantes/', views.ParticipanteSorteioListView.as_view(), name='sorteio-participantes'),

    # Sorteio
    path('sorteio/sortear/<int:pk>/', views.SortearView.as_view(), name='sorteio-sortear'),
    path('sorteio/ganhadores/', views.GanhadoresListView.as_view(), name='sorteio-ganhadores'),
]
