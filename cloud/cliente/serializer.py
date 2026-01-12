import os
import logging
import hashlib
import time
import uuid as uuid_lib

from django.core.files.storage import default_storage


from django.conf import settings
from django.core.files.uploadedfile import UploadedFile

from rest_framework import serializers

from .models import (
    Pasta, TipoArquivoChoices, Arquivo, Cliente,
    AdministradorPasta, PastaFixada, PastaRecente,
    TipoDrive, User
)

from empresa.models import Empresa
from empresa.serializer import EmpresaModelSerializer

logger = logging.getLogger(__name__)


class RecursiveField(serializers.Serializer):
    def to_representation(self, value):
        serializer = self.parent.parent.__class__(value, context=self.context)
        return serializer.data


class PastaContentModelSerializer(serializers.ModelSerializer):
    size = serializers.SerializerMethodField()  # Tamanho INDIVIDUAL da pasta
    filesCount = serializers.SerializerMethodField()  # Arquivos INDIVIDUAIS da pasta
    totalSize = serializers.SerializerMethodField()  # Tamanho TOTAL (com subpastas)
    totalFilesCount = serializers.SerializerMethodField()  # Total de arquivos (com subpastas)

    class Meta:
        model = Pasta
        fields = [
            'id',
            'nome',
            'pasta_pai',
            'status',
            'criado_em',
            'atualizado_em',
            'deletado_em',
            'segmento',
            'size',            # Tamanho INDIVIDUAL (somente desta pasta)
            'filesCount',      # Arquivos INDIVIDUAIS (somente desta pasta)
            'totalSize',       # Tamanho TOTAL (incluindo subpastas) - opcional
            'totalFilesCount'  # Total de arquivos (incluindo subpastas) - opcional
        ]

    def get_size(self, obj):
        """Retorna tamanho INDIVIDUAL (somente desta pasta)"""
        return obj.get_individual_size()

    def get_filesCount(self, obj):
        """Retorna contagem INDIVIDUAL (somente desta pasta)"""
        return obj.get_immediate_files_count()

    def get_totalSize(self, obj):
        """Retorna tamanho TOTAL (incluindo subpastas) - opcional"""
        return obj.get_total_size()

    def get_totalFilesCount(self, obj):
        """Retorna contagem TOTAL (incluindo subpastas) - opcional"""
        return obj.get_total_files_count()


class FuncionarioPastaSerializer(serializers.ModelSerializer):
    funcionario_id = serializers.IntegerField(source='funcionario.id')
    nome = serializers.CharField(source='funcionario.get_full_name')
    email = serializers.CharField(source='funcionario.email')
    username = serializers.CharField(source='funcionario.username')
    data_designacao = serializers.DateTimeField()

    class Meta:
        model = AdministradorPasta
        fields = ['funcionario_id', 'nome', 'email', 'username', 'data_designacao']


class PastaModelSerializer(serializers.ModelSerializer):
    sub_pastas = RecursiveField(many=True, source='subpastas', read_only=True)
    funcionarios = serializers.SerializerMethodField()
    size = serializers.SerializerMethodField()
    filesCount = serializers.SerializerMethodField()

    class Meta:
        model = Pasta
        fields = [
            'id',
            'nome',
            'pasta_pai',
            'sub_pastas',
            'status',
            'criado_em',
            'atualizado_em',
            'deletado_em',
            'segmento',
            'funcionarios',
            'size',  # Tamanho INDIVIDUAL
            'filesCount'  # Arquivos INDIVIDUAIS
        ]

    def get_size(self, obj):
        """Retorna tamanho INDIVIDUAL"""
        if hasattr(obj, 'individual_size'):
            return obj.individual_size or 0
        return obj.get_individual_size()

    def get_filesCount(self, obj):
        """Retorna contagem INDIVIDUAL"""
        if hasattr(obj, 'individual_files_count'):
            return obj.individual_files_count or 0
        return obj.get_immediate_files_count()

    def get_funcionarios(self, obj):
        # Busca todos os administradores desta pasta
        administradores = AdministradorPasta.objects.filter(pasta=obj).distinct('funcionario_id')
        return FuncionarioPastaSerializer(administradores, many=True).data


class ArquivoModelSerializer(serializers.ModelSerializer):
    arquivo = serializers.FileField(write_only=True, required=True)
    empresa_id = serializers.IntegerField(write_only=True, required=False)
    pasta_id = serializers.IntegerField(write_only=True, required=True)

    # Campos de leitura
    empresa = serializers.SerializerMethodField()
    pasta = serializers.SerializerMethodField()
    nome = serializers.CharField(required=False, allow_blank=True, max_length=255)
    nome_original = serializers.CharField(read_only=True)
    extensao = serializers.CharField(read_only=True)
    tamanho = serializers.IntegerField(read_only=True)
    tipo = serializers.CharField(read_only=True)
    tipo_display = serializers.CharField(source='get_tipo_display', read_only=True)
    drive = serializers.CharField(read_only=True)
    drive_display = serializers.CharField(source='get_drive_display', read_only=True)
    url = serializers.SerializerMethodField()
    drive_info = serializers.SerializerMethodField()

    class Meta:
        model = Arquivo
        fields = [
            'id', 'nome', 'arquivo', 'nome_original',
            'empresa_id', 'empresa',
            'pasta_id', 'pasta',
            'tipo', 'tipo_display', 'extensao', 'tamanho',
            'drive', 'drive_display', 'drive_info',
            'criado_por', 'status', 'criado_em', 'atualizado_em',
            'url'
        ]
        read_only_fields = ['criado_em', 'atualizado_em', 'criado_por', 'status', 'drive']

    def get_url(self, obj):
        """Retorna a URL do arquivo"""
        if obj.arquivo:
            try:
                return obj.arquivo.url
            except:
                # Se não conseguir obter URL, tenta construir manualmente
                if obj.drive == TipoDrive.S3:
                    return f"https://{settings.AWS_BUCKET}.s3.{settings.AWS_DEFAULT_REGION}.amazonaws.com/{obj.arquivo.name}"
                else:
                    return f"/media/{obj.arquivo.name}"
        return None

    def get_drive_info(self, obj):
        """Retorna informações detalhadas sobre o drive"""
        return {
            'code': obj.drive,
            'display': obj.get_drive_display(),
            'is_s3': obj.drive == TipoDrive.S3,
            'is_local': obj.drive == TipoDrive.LOCAL,
            'icon': 'cloud' if obj.drive == TipoDrive.S3 else 'storage'
        }

    def create(self, validated_data):
        arquivo_file = validated_data.pop('arquivo')

        # Empresa vem do usuário se não fornecida
        if 'empresa_id' in validated_data:
            empresa_id = validated_data.pop('empresa_id')
            validated_data['empresa_id'] = empresa_id
        elif 'empresa' not in validated_data and self.context.get('request'):
            user = self.context['request'].user
            if hasattr(user, 'empresa') and user.empresa:
                validated_data['empresa'] = user.empresa
            else:
                raise serializers.ValidationError({
                    'empresa': 'Usuário não tem uma empresa associada'
                })

        # Pasta é obrigatória
        if 'pasta_id' in validated_data:
            pasta_id = validated_data.pop('pasta_id')
            validated_data['pasta_id'] = pasta_id

        # Usuário que criou
        if self.context.get('request'):
            validated_data['criado_por'] = self.context['request'].user

        # Campos derivados do arquivo
        nome_original = arquivo_file.name
        extensao = self._get_extensao(nome_original)
        tipo = self._detectar_tipo_arquivo(extensao, arquivo_file.content_type)

        # Nome do arquivo (se não fornecido)
        if not validated_data.get('nome'):
            validated_data['nome'] = self._get_nome_sem_extensao(nome_original)

        # Determina drive inicial baseado na configuração
        if getattr(settings, 'AWS_USE_S3_UPLOAD', False):
            drive_inicial = TipoDrive.S3
        else:
            drive_inicial = TipoDrive.LOCAL

        # Tenta salvar o arquivo
        try:
            # Cria a instância do Arquivo
            arquivo = Arquivo(
                **validated_data,
                nome_original=nome_original,
                extensao=extensao,
                tipo=tipo,
                tamanho=arquivo_file.size,
                drive=drive_inicial,
                arquivo=arquivo_file
            )

            # Salva novamente para trigger do FileField
            arquivo.save()

            logger.info(f"Serializer: Arquivo salvo com ID {arquivo.id}, nome: {arquivo.nome_original}")

            # Atualiza o drive baseado no storage usado
            if arquivo.update_drive_from_storage():
                logger.info(f"Serializer: Drive atualizado para {arquivo.get_drive_display()}")

            return arquivo

        except Exception as e:
            logger.error(f"Serializer: Erro ao salvar arquivo: {e}")

            # Se o arquivo foi criado mas falhou, tenta deletar
            if arquivo.pk:
                try:
                    arquivo.delete()
                except:
                    pass

            # Tenta salvar localmente como último recurso
            try:
                logger.info("Serializer: Tentando salvar localmente como último recurso...")

                # Cria novo objeto sem FileField primeiro
                arquivo_fallback = Arquivo(
                    **validated_data,
                    nome_original=nome_original,
                    extensao=extensao,
                    tipo=tipo,
                    tamanho=arquivo_file.size,
                    drive=TipoDrive.LOCAL  # Força local
                )
                arquivo_fallback.save()

                # Salva o arquivo localmente
                # Gera nome único
                timestamp = int(time.time() * 1000)
                unique_hash = hashlib.md5(
                    f"{nome_original}_{timestamp}_{uuid_lib.uuid4()}".encode()
                ).hexdigest()[:8]

                nome_base, extensao_arquivo = os.path.splitext(nome_original)
                novo_nome = f"{nome_base}_{unique_hash}{extensao_arquivo}"
                caminho_completo = f"arquivos/{time.strftime('%Y/%m/%d')}/{novo_nome}"

                # Salva usando storage padrão
                nome_salvo = default_storage.save(caminho_completo, arquivo_file)
                arquivo_fallback.arquivo = nome_salvo
                arquivo_fallback.save()

                logger.info(f"Serializer: ✓ Arquivo salvo localmente após falha: {nome_salvo}")
                return arquivo_fallback

            except Exception as ultimo_erro:
                logger.error(f"Serializer: ✗ Falha total ao salvar arquivo: {ultimo_erro}")
                raise serializers.ValidationError({
                    'arquivo': f'Não foi possível salvar o arquivo: {str(ultimo_erro)}'
                })

    def _get_extensao(self, filename):
        """Extrai a extensão do arquivo"""
        _, ext = os.path.splitext(filename)
        return ext.lower().replace('.', '') if ext else ''

    def _get_nome_sem_extensao(self, filename):
        """Remove a extensão do nome do arquivo"""
        nome, _ = os.path.splitext(filename)
        return nome

    def _detectar_tipo_arquivo(self, extensao, content_type=None):
        """Detecta o tipo do arquivo baseado na extensão e content_type"""
        extensoes_tipo = {
            'pdf': TipoArquivoChoices.PDF,
            'doc': TipoArquivoChoices.DOCUMENTO,
            'docx': TipoArquivoChoices.DOCUMENTO,
            'txt': TipoArquivoChoices.DOCUMENTO,
            'rtf': TipoArquivoChoices.DOCUMENTO,
            'odt': TipoArquivoChoices.DOCUMENTO,
            'xls': TipoArquivoChoices.PLANILHA,
            'xlsx': TipoArquivoChoices.PLANILHA,
            'csv': TipoArquivoChoices.PLANILHA,
            'ods': TipoArquivoChoices.PLANILHA,
            'jpg': TipoArquivoChoices.IMAGEM,
            'jpeg': TipoArquivoChoices.IMAGEM,
            'png': TipoArquivoChoices.IMAGEM,
            'gif': TipoArquivoChoices.IMAGEM,
            'bmp': TipoArquivoChoices.IMAGEM,
            'svg': TipoArquivoChoices.IMAGEM,
            'webp': TipoArquivoChoices.IMAGEM,
            'tiff': TipoArquivoChoices.IMAGEM,
        }

        if extensao in extensoes_tipo:
            return extensoes_tipo[extensao]

        if content_type:
            if content_type.startswith('image/'):
                return TipoArquivoChoices.IMAGEM
            elif content_type.startswith('application/pdf'):
                return TipoArquivoChoices.PDF
            elif 'spreadsheet' in content_type or 'excel' in content_type:
                return TipoArquivoChoices.PLANILHA
            elif 'word' in content_type or 'document' in content_type:
                return TipoArquivoChoices.DOCUMENTO

        return TipoArquivoChoices.OUTRO

    def validate_arquivo(self, value):
        """Validação do arquivo"""
        if not isinstance(value, UploadedFile):
            raise serializers.ValidationError("Arquivo inválido")

        max_size = 100 * 1024 * 1024  # 100MB
        if value.size > max_size:
            raise serializers.ValidationError("Arquivo muito grande. Tamanho máximo: 100MB")

        extensoes_permitidas = [
            'pdf', 'doc', 'docx', 'xls', 'xlsx', 'csv', 'txt',
            'jpg', 'jpeg', 'png', 'gif', 'bmp', 'svg', 'webp'
        ]

        extensao = self._get_extensao(value.name)
        if extensao and extensao not in extensoes_permitidas:
            raise serializers.ValidationError(
                f"Tipo de arquivo não permitido. Extensões permitidas: {', '.join(extensoes_permitidas)}"
            )

        return value

    def validate(self, attrs):
        """Validações gerais"""
        request = self.context.get('request')

        if request and request.method == 'POST':
            if 'pasta_id' in attrs:
                try:
                    pasta = Pasta.objects.get(id=attrs['pasta_id'])
                    # Verificação de permissão pode ser adicionada aqui
                except Pasta.DoesNotExist:
                    raise serializers.ValidationError({
                        'pasta_id': 'Pasta não encontrada'
                    })

        return attrs

    def get_empresa(self, obj):
        if hasattr(obj, 'empresa') and obj.empresa:
            return EmpresaModelSerializer(obj.empresa).data
        return None

    def get_pasta(self, obj):
        if hasattr(obj, 'pasta') and obj.pasta:
            return PastaContentModelSerializer(obj.pasta).data
        return None


class DownloadMultiplosSerializer(serializers.Serializer):
    """Serializer para validação de download múltiplo"""
    arquivos_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=True,
        min_length=1,
        max_length=100  # Limite máximo de arquivos por download
    )
    pasta_id = serializers.IntegerField(required=False)

    def validate_arquivos_ids(self, value):
        """Valida se os IDs existem"""
        arquivos_existentes = Arquivo.objects.filter(id__in=value, status='1').count()
        if arquivos_existentes != len(value):
            raise serializers.ValidationError("Alguns arquivos não existem ou não estão ativos")
        return value


class ClienteModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = Cliente
        fields = '__all__'


class AdministradorPastaModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = AdministradorPasta
        fields = '__all__'


class AdministradorPastaBulkSerializer(serializers.Serializer):
    empresa = serializers.ListField(
        child=serializers.IntegerField(), allow_empty=False
    )
    pasta = serializers.IntegerField()
    funcionario = serializers.ListField(
        child=serializers.IntegerField(), allow_empty=False
    )

    def create(self, validated_data):
        empresas = validated_data['empresa']
        funcionarios = validated_data['funcionario']
        pasta_id = validated_data['pasta']

        pasta = Pasta.objects.get(id=pasta_id)

        registros = []
        for empresa_id in empresas:
            empresa = Empresa.objects.get(id=empresa_id)

            for funcionario_id in funcionarios:
                funcionario = User.objects.get(id=funcionario_id)

                # Evita duplicatas
                obj, created = AdministradorPasta.objects.get_or_create(
                    empresa=empresa,
                    pasta=pasta,
                    funcionario=funcionario
                )
                registros.append(obj)

        return registros


class AdministradorFuncionarioPastaModelSerializer(serializers.ModelSerializer):
    empresa = serializers.SerializerMethodField()
    pasta = serializers.SerializerMethodField()

    class Meta:
        model = AdministradorPasta
        fields = ['pasta', 'empresa', 'funcionario', 'data_designacao']

    def get_empresa(self, obj):
        if hasattr(obj, 'empresa') and obj.empresa:
            return EmpresaModelSerializer(obj.empresa).data
        return None

    def get_pasta(self, obj):
        if hasattr(obj, 'pasta') and obj.pasta:
            return PastaContentModelSerializer(obj.pasta).data
        return None


class PastaFixadaSerializer(serializers.ModelSerializer):
    pasta = PastaContentModelSerializer(read_only=True)
    empresa = EmpresaModelSerializer(read_only=True)

    class Meta:
        model = PastaFixada
        fields = ['id', 'usuario', 'pasta', 'empresa', 'ordem', 'fixado_em']


class PastaRecenteSerializer(serializers.ModelSerializer):
    pasta = PastaContentModelSerializer(read_only=True)
    empresa = EmpresaModelSerializer(read_only=True)

    class Meta:
        model = PastaRecente
        fields = ['id', 'usuario', 'pasta', 'empresa', 'acessado_em']


class PastaFixadaCreateSerializer(serializers.ModelSerializer):
    pasta_id = serializers.IntegerField(write_only=True)
    empresa_id = serializers.IntegerField(write_only=True, required=True)

    class Meta:
        model = PastaFixada
        fields = ['pasta_id', 'empresa_id']

    def validate(self, attrs):
        request = self.context.get('request')
        pasta_id = attrs.get('pasta_id')
        empresa_id = attrs.get('empresa_id')

        # Verifica se a pasta existe
        try:
            pasta = Pasta.objects.get(id=pasta_id)
            attrs['pasta'] = pasta
        except Pasta.DoesNotExist:
            raise serializers.ValidationError("Pasta não encontrada")

        # Verifica se a empresa existe
        try:
            empresa = Empresa.objects.get(id=empresa_id)
            attrs['empresa'] = empresa
        except Empresa.DoesNotExist:
            raise serializers.ValidationError("Empresa não encontrada")

        # Verifica se usuário tem permissão para acessar esta pasta na empresa especificada
        user = request.user
        if not user.is_superuser:
            # Verifica se é administrador da pasta na empresa especificada
            tem_permissao_admin = AdministradorPasta.objects.filter(
                funcionario=user,
                pasta=pasta,
                empresa=empresa
            ).exists()

            # Verifica se a empresa pertence ao usuário e tem acesso à pasta
            tem_permissao_cliente = (
                hasattr(user, 'empresa') and
                user.empresa.id == empresa.id and
                Cliente.objects.filter(
                    empresa=empresa,
                    pastas=pasta
                ).exists()
            )

            if not tem_permissao_admin and not tem_permissao_cliente:
                raise serializers.ValidationError("Você não tem permissão para acessar esta pasta nesta empresa")

        return attrs

    def create(self, validated_data):
        validated_data.pop('pasta_id', None)
        validated_data.pop('empresa_id', None)
        validated_data['usuario'] = self.context['request'].user
        return super().create(validated_data)
