from django.urls import path
from . import views


urlpatterns = [
    path('cloud/circularizacoes/', views.CircularizacaoClienteListCreateAPIView.as_view(), name='circularizacao-create-list'),
    path('cloud/circularizacao/<int:pk>/', views.CircularizacaoClienteRetrieveUpdateDestroyAPIView.as_view(), name='circularizacao-detail'),

    path('cloud/circularizacao-acessos/', views.CircularizacaoAcessoListCreateAPIView.as_view(), name='circularizacao-acesso-create-list'),
    path('cloud/circularizacao-acesso/<int:pk>/', views.CircularizacaoAcessoRetrieveUpdateDestroyAPIView.as_view(), name='circularizacao-acesso-detail'),

    path('cloud/circularizacao-arquivos-recebidos/', views.CircularizacaoArquivoRecebidoListCreateAPIView.as_view(), name='circularizacao-arquivo-recebido-create-list'),
    path('cloud/circularizacao-arquivo-recebido/<int:pk>/', views.CircularizacaoArquivoRecebidoRetrieveUpdateDestroyAPIView.as_view(), name='circularizacao-arquivo-recebido-detail'),
]
