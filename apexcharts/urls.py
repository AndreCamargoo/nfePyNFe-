from django.urls import path
from . import views


urlpatterns = [
    path('apexcharts/custo-medio-fornecedo/', views.CustoMedioFornecedorAPIView.as_view(), name='apexcharts-custo-medio-fornecedor'),
]
