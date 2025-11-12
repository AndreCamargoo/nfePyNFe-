import os

from django.core.files.uploadedfile import UploadedFile

from rest_framework import serializers

from .models import Pasta, TipoArquivoChoices, Arquivo, Cliente, AdministradorPasta


class PastaModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = Pasta
        fields = '__all__'


class ArquivoModelSerializer(serializers.ModelSerializer):
    # Campo para upload do arquivo (obrigatório no POST)
    arquivo = serializers.FileField(write_only=True, required=True)

    # Nome agora é opcional
    nome = serializers.CharField(required=False, allow_blank=True, max_length=255)

    # Campos read-only para mostrar após criação
    nome_original = serializers.CharField(read_only=True)
    extensao = serializers.CharField(read_only=True)
    tamanho = serializers.IntegerField(read_only=True)
    tipo = serializers.CharField(read_only=True)
    tipo_display = serializers.CharField(source='get_tipo_display', read_only=True)

    class Meta:
        model = Arquivo
        fields = [
            'id', 'nome', 'arquivo', 'nome_original', 'pasta',
            'tipo', 'tipo_display', 'extensao', 'tamanho', 'empresa', 'criado_por',
            'status', 'criado_em', 'atualizado_em'
        ]
        read_only_fields = ['criado_em', 'atualizado_em', 'criado_por']

    def create(self, validated_data):
        # Pega o arquivo do validated_data
        arquivo_file = validated_data.pop('arquivo')

        # Auto-detecta informações do arquivo
        nome_original = arquivo_file.name
        extensao = self._get_extensao(nome_original)
        tipo = self._detectar_tipo_arquivo(extensao, arquivo_file.content_type)

        # Se nome não foi fornecido ou está vazio, usa o nome original sem extensão
        if not validated_data.get('nome'):
            validated_data['nome'] = self._get_nome_sem_extensao(nome_original)

        # Cria o objeto Arquivo
        arquivo = Arquivo(
            **validated_data,
            nome_original=nome_original,
            extensao=extensao,
            tipo=tipo,
            arquivo=arquivo_file  # Salva o arquivo
        )

        # O tamanho será calculado automaticamente no save()
        arquivo.save()
        return arquivo

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
        # Mapeamento de extensões para tipos
        extensoes_tipo = {
            # Documentos
            'pdf': TipoArquivoChoices.PDF,
            'doc': TipoArquivoChoices.DOCUMENTO,
            'docx': TipoArquivoChoices.DOCUMENTO,
            'txt': TipoArquivoChoices.DOCUMENTO,
            'rtf': TipoArquivoChoices.DOCUMENTO,
            'odt': TipoArquivoChoices.DOCUMENTO,

            # Planilhas
            'xls': TipoArquivoChoices.PLANILHA,
            'xlsx': TipoArquivoChoices.PLANILHA,
            'csv': TipoArquivoChoices.PLANILHA,
            'ods': TipoArquivoChoices.PLANILHA,

            # Imagens
            'jpg': TipoArquivoChoices.IMAGEM,
            'jpeg': TipoArquivoChoices.IMAGEM,
            'png': TipoArquivoChoices.IMAGEM,
            'gif': TipoArquivoChoices.IMAGEM,
            'bmp': TipoArquivoChoices.IMAGEM,
            'svg': TipoArquivoChoices.IMAGEM,
            'webp': TipoArquivoChoices.IMAGEM,
            'tiff': TipoArquivoChoices.IMAGEM,
        }

        # Tenta detectar pela extensão primeiro
        if extensao in extensoes_tipo:
            return extensoes_tipo[extensao]

        # Se não encontrou pela extensão, tenta pelo content_type
        if content_type:
            if content_type.startswith('image/'):
                return TipoArquivoChoices.IMAGEM
            elif content_type.startswith('application/pdf'):
                return TipoArquivoChoices.PDF
            elif 'spreadsheet' in content_type or 'excel' in content_type:
                return TipoArquivoChoices.PLANILHA
            elif 'word' in content_type or 'document' in content_type:
                return TipoArquivoChoices.DOCUMENTO

        # Padrão é OUTRO
        return TipoArquivoChoices.OUTRO

    def validate_arquivo(self, value):
        """Validação do arquivo"""
        if not isinstance(value, UploadedFile):
            raise serializers.ValidationError("Arquivo inválido")

        # Tamanho máximo: 100MB
        max_size = 100 * 1024 * 1024
        if value.size > max_size:
            raise serializers.ValidationError("Arquivo muito grande. Tamanho máximo: 100MB")

        # Extensões permitidas (opcional - você pode personalizar)
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

        # Se for criação, define o criado_por como o usuário logado
        if request and request.method == 'POST':
            attrs['criado_por'] = request.user

            # Se empresa não foi fornecida, tenta pegar do usuário logado
            if not attrs.get('empresa') and hasattr(request.user, 'empresa'):
                attrs['empresa'] = request.user.empresa

        return attrs


class ClienteModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = Cliente
        fields = '__all__'


class AdministradorPastaModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = AdministradorPasta
        fields = '__all__'
