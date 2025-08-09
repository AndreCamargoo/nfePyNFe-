from rest_framework import serializers


class CustoMedioFornecedorSerializer(serializers.Serializer):
    cnpj_fornecedor = serializers.CharField()
    nome_fornecedor = serializers.CharField()
    valor_comprado_fornecedor = serializers.DecimalField(max_digits=20, decimal_places=2)
    percentual_participacao = serializers.DecimalField(max_digits=20, decimal_places=2)
