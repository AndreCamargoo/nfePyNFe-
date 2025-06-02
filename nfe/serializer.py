from rest_framework import serializers
from . import models
from empresa.serializer import EmpresaModelSerializer


class NfeSerializer(serializers.ModelSerializer):
    # Dados body json
    empresa_id = serializers.IntegerField(write_only=True)
    xml = serializers.CharField(write_only=True)
    nus = serializers.CharField(write_only=True)
    fileXml = serializers.CharField(write_only=True)
    filePdf = serializers.CharField(write_only=True)


class NfeModelSerializer(serializers.ModelSerializer):
    empresa = EmpresaModelSerializer()
    ide = serializers.SerializerMethodField()
    emitente = serializers.SerializerMethodField()
    destinatario = serializers.SerializerMethodField()
    produtos = serializers.SerializerMethodField()
    total = serializers.SerializerMethodField()
    transporte = serializers.SerializerMethodField()
    cobranca = serializers.SerializerMethodField()
    pagamentos = serializers.SerializerMethodField()

    class Meta:
        model = models.NotaFiscal
        fields = [
            'id', 'chave', 'versao', 'dhEmi', 'dhSaiEnt', 'fileXml', 'filePdf',
            'empresa', 'ide', 'emitente', 'destinatario', 'produtos', 'total',
            'transporte', 'cobranca', 'pagamentos'
        ]

    def get_ide(self, obj):
        if hasattr(obj, 'ide') and obj.ide:
            return IdeModelSerializer(obj.ide).data
        return None

    def get_emitente(self, obj):
        if hasattr(obj, 'emitente') and obj.emitente:
            return EmitenteModelSerializer(obj.emitente).data
        return None

    def get_destinatario(self, obj):
        if hasattr(obj, 'destinatario') and obj.destinatario:
            return DestinatarioModelSerializer(obj.destinatario).data
        return None

    def get_produtos(self, obj):
        if hasattr(obj, 'produtos') and obj.produtos:
            return ProdutoModelSerializer(obj.produtos.all(), many=True).data
        return None

    def get_total(self, obj):
        if hasattr(obj, 'total') and obj.total:
            return TotalModelSerializer().data
        return None

    def get_transporte(self, obj):
        if hasattr(obj, 'transporte') and obj.transporte:
            return TransporteModelSerializer().data
        return None

    def get_cobranca(self, obj):
        if hasattr(obj, 'cobranca') and obj.cobranca:
            return CobrancaModelSerializer().data
        return None

    def get_pagamentos(self, obj):
        if hasattr(obj, 'pagamentos') and obj.pagamentos:
            return PagamentoModelSerializer(obj.pagamentos.all(), many=True).data
        return None


class IdeModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Ide
        fields = '__all__'


class EmitenteModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Emitente
        fields = '__all__'


class DestinatarioModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Destinatario
        fields = '__all__'


class ProdutoModelSerializer(serializers.ModelSerializer):
    imposto = serializers.SerializerMethodField()

    class Meta:
        model = models.Produto
        fields = [
            'id', 'nItem', 'cProd', 'cEAN', 'xProd', 'NCM', 'CFOP',
            'uCom', 'qCom', 'vUnCom', 'vProd', 'uTrib', 'qTrib',
            'vUnTrib', 'indTot', 'nota_fiscal', 'imposto'
        ]

    def get_imposto(self, obj):
        if hasattr(obj, 'imposto') and obj.imposto:
            return ImpostoModelSerializer(obj.imposto).data
        return None


class ImpostoModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Imposto
        fields = '__all__'


class TotalModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Total
        fields = '__all__'


class TransporteModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Transporte
        fields = '__all__'


class CobrancaModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Cobranca
        fields = '__all__'


class PagamentoModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Pagamento
        fields = '__all__'
