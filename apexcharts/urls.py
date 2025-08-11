from django.urls import path
from . import views


urlpatterns = [
    path('apexcharts/custo-medio-fornecedor/', views.CustoMedioFornecedorAPIView.as_view(), name='apexcharts-custo-medio-fornecedor'),
    path('apexcharts/participacao-fornecedores/', views.ParticipacaoFornecedoresAPIView.as_view(), name='apexcharts-participacao-fornecedores'),
    path('apexcharts/concentracao-produtos/', views.ConcentracaoProdutosAPIView.as_view(), name='apexcharts-concentracao-produtos'),
    path('apexcharts/frequencia-compras/', views.FrequenciaComprasAPIView.as_view(), name='apexcharts-frequencia-compras'),
]
