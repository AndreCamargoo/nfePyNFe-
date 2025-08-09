from rest_framework import serializers


class CustoMedioFornecedorSerializer(serializers.Serializer):
    cnpj_fornecedor = serializers.CharField()
    nome_fornecedor = serializers.CharField()
    valor_total_comprado = serializers.DecimalField(max_digits=20, decimal_places=2)
    quantidade_total_itens = serializers.IntegerField()
    custo_medio_por_item = serializers.DecimalField(max_digits=20, decimal_places=2)


class ParticipacaoFornecedoresSerializer(serializers.Serializer):
    cnpj_fornecedor = serializers.CharField()
    nome_fornecedor = serializers.CharField()
    valor_comprado_fornecedor = serializers.DecimalField(max_digits=20, decimal_places=2)
    percentual_participacao = serializers.DecimalField(max_digits=20, decimal_places=2)


class ConcentracaoProdutosSerializer(serializers.Serializer):
    cean = serializers.CharField()
    cprod = serializers.CharField()
    xprod = serializers.CharField()
    valor_comprado_produto = serializers.DecimalField(max_digits=20, decimal_places=2)
    percentual_individual = serializers.DecimalField(max_digits=20, decimal_places=2)
    percentual_acumulado = serializers.DecimalField(max_digits=20, decimal_places=2)


class FrequenciaComprasQuerySerializer(serializers.Serializer):
    mes_ou_semana = serializers.ChoiceField(choices=["mensal", "semanal"])
    ano_inicio = serializers.DateField(required=False)
    ano_fim = serializers.DateField(required=False)


class FrequenciaComprasSerializer(serializers.Serializer):
    periodo = serializers.CharField()
    ano = serializers.IntegerField()
    mes_ou_semana = serializers.IntegerField()
    quantidade_pedidos = serializers.IntegerField()
