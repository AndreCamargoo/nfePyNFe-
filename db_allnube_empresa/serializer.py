# serializer.py
from rest_framework import serializers
from . import models
from empresa.serializer import EmpresaModelSerializer


class IdeFlatModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.IdeFlat
        fields = '__all__'


class EmitenteFlatModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.EmitenteFlat
        fields = '__all__'


class DestinatarioFlatModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.DestinatarioFlat
        fields = '__all__'


class ImpostoFlatModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.ImpostoFlat
        fields = '__all__'


class ProdutoFlatModelSerializer(serializers.ModelSerializer):
    imposto = serializers.SerializerMethodField()

    class Meta:
        model = models.ProdutoFlat
        fields = [
            'id', 'nItem', 'cProd', 'cEAN', 'xProd', 'NCM', 'CFOP',
            'uCom', 'qCom', 'vUnCom', 'vProd', 'uTrib', 'qTrib',
            'vUnTrib', 'indTot', 'nota_fiscal_id', 'imposto'
        ]

    def get_imposto(self, obj):
        try:
            imposto = models.ImpostoFlat.objects.filter(produto_id=obj.id).first()
            return ImpostoFlatModelSerializer(imposto).data if imposto else None
        except models.ImpostoFlat.DoesNotExist:
            return None


class TotalFlatModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.TotalFlat
        fields = '__all__'


class TransporteFlatModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.TransporteFlat
        fields = '__all__'


class CobrancaFlatModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.CobrancaFlat
        fields = '__all__'


class PagamentoFlatModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.PagamentoFlat
        fields = '__all__'


class NfeFlatModelSerializer(serializers.ModelSerializer):
    # Campos para criação (write_only)
    empresa_id = serializers.IntegerField(write_only=True)
    nsu = serializers.CharField(write_only=True, required=False)
    fileXml = serializers.CharField(write_only=True, required=False)
    filePdf = serializers.CharField(write_only=True, required=False)
    tipo = serializers.CharField(write_only=True, required=False)

    # Campos relacionados (read_only)
    ide = serializers.SerializerMethodField()
    emitente = serializers.SerializerMethodField()
    destinatario = serializers.SerializerMethodField()
    produtos = serializers.SerializerMethodField()
    total = serializers.SerializerMethodField()
    transporte = serializers.SerializerMethodField()
    cobranca = serializers.SerializerMethodField()
    pagamentos = serializers.SerializerMethodField()

    class Meta:
        model = models.NotaFiscalFlat
        fields = [
            'id', 'chave', 'versao', 'dhEmi', 'dhSaiEnt', 'tpAmb',
            'fileXml', 'filePdf', 'created_at', 'updated_at', 'deleted_at',
            'empresa_id', 'nsu', 'tipo',  # Campos write_only
            'ide', 'emitente', 'destinatario', 'produtos', 'total',
            'transporte', 'cobranca', 'pagamentos'  # Campos read_only
        ]

    def get_ide(self, obj):
        try:
            ide = models.IdeFlat.objects.filter(nota_fiscal_id=obj.id).first()
            return IdeFlatModelSerializer(ide).data if ide else None
        except Exception:
            return None

    def get_emitente(self, obj):
        try:
            emitente = models.EmitenteFlat.objects.filter(nota_fiscal_id=obj.id).first()
            return EmitenteFlatModelSerializer(emitente).data if emitente else None
        except Exception:
            return None

    def get_destinatario(self, obj):
        try:
            destinatario = models.DestinatarioFlat.objects.filter(nota_fiscal_id=obj.id).first()
            return DestinatarioFlatModelSerializer(destinatario).data if destinatario else None
        except Exception:
            return None

    def get_produtos(self, obj):
        try:
            produtos = models.ProdutoFlat.objects.filter(nota_fiscal_id=obj.id)
            return ProdutoFlatModelSerializer(produtos, many=True).data
        except Exception:
            return []

    def get_total(self, obj):
        try:
            total = models.TotalFlat.objects.filter(nota_fiscal_id=obj.id).first()
            return TotalFlatModelSerializer(total).data if total else None
        except Exception:
            return None

    def get_transporte(self, obj):
        try:
            transporte = models.TransporteFlat.objects.filter(nota_fiscal_id=obj.id).first()
            return TransporteFlatModelSerializer(transporte).data if transporte else None
        except Exception:
            return None

    def get_cobranca(self, obj):
        try:
            cobranca = models.CobrancaFlat.objects.filter(nota_fiscal_id=obj.id).first()
            return CobrancaFlatModelSerializer(cobranca).data if cobranca else None
        except Exception:
            return None

    def get_pagamentos(self, obj):
        try:
            # Pagamentos são relacionados via cobranca
            cobranca = models.CobrancaFlat.objects.filter(nota_fiscal_id=obj.id).first()
            if cobranca:
                pagamentos = models.PagamentoFlat.objects.filter(cobranca_id=cobranca.id)
                return PagamentoFlatModelSerializer(pagamentos, many=True).data
            return []
        except Exception:
            return []


class NfeFlatSerializer(serializers.ModelSerializer):
    # Dados body json
    empresa_id = serializers.IntegerField(write_only=True)
    nsu = serializers.CharField(write_only=True)
    fileXml = serializers.CharField(write_only=True)
    filePdf = serializers.CharField(write_only=True)
    tipo = serializers.CharField(write_only=True)

    class Meta:
        model = models.NotaFiscalFlat
        fields = '__all__'
