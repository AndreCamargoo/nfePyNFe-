from django.urls import path
from . import views


urlpatterns = [
    path('agenda/evento-cadastros/', views.EventoCadastroListCreateAPIView.as_view(), name='evento-cadastro-create-list'),
    path('agenda/evento-cadastro/<int:pk>/', views.EventoCadastroRetrieveUpdateDestroyAPIView.as_view(), name='evento-cadastro-detail'),

    path('agenda/evento-contatos/', views.EventoContatoListCreateAPIView.as_view(), name='evento-contato-create-list'),
    path('agenda/evento-contato/<int:pk>/', views.EventoContatoRetrieveUpdateDestroyAPIView.as_view(), name='evento-contato-detail'),

    path('agenda/importar/evento-cadastros/', views.EventoImportXLSX.as_view(), name='import-evento-cadastros'),
    path('agenda/download/evento-cadastros/', views.EventoDownload.as_view(), name='download-evento-cadastros'),
]
