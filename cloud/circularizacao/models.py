import uuid

from cryptography.fernet import Fernet

from django.contrib.auth.models import User
from django.conf import settings

from django.db import models


STATUS_CHOICES = (
    ('1', 'Ativo'), ('2', 'Inativo'),
)


def get_fernet():
    key = getattr(settings, 'FERNET_SECRET_KEY', None)
    if not key:
        raise Exception("FERNET_SECRET_KEY não está configurada no settings.")
    return Fernet(key.encode())


class CircularizacaoCliente(models.Model):
    def generate_unique_code():
        return str(uuid.uuid4().hex[:12])  # Gera um código de 12 caracteres

    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='circularizacao')
    uri = models.CharField(max_length=255, default=generate_unique_code, unique=True)
    _senha = models.BinaryField(db_column='senha')
    ano_vigente = models.IntegerField()
    status = models.CharField(max_length=1, choices=STATUS_CHOICES)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'cloud_circularizacao_cliente'
        verbose_name = 'Cliente de Circularização'
        verbose_name_plural = 'Clientes de Circularização'

    def __str__(self):
        return f"{self.usuario.username} - {self.uri} ({self.ano_vigente})"

    def _set_field(self, field_name: str, value: str) -> None:
        fernet = get_fernet()
        encrypted_value = fernet.encrypt(value.encode())  # O valor é armazenado como bytes
        setattr(self, field_name, encrypted_value)

    def _get_field(self, field_name: str) -> str:
        fernet = get_fernet()
        field_value = getattr(self, field_name)

        # Garantindo que o tipo do valor seja bytes
        if isinstance(field_value, memoryview):
            field_value = field_value.tobytes()  # Convertendo para bytes

        if not isinstance(field_value, bytes):
            raise ValueError(f"O valor de {field_name} não está no formato correto (bytes): {field_value}")

        decrypted_value = fernet.decrypt(field_value).decode()
        return decrypted_value

    # Métodos específicos para setar e pegar os valores
    def set_senha(self, senha_plana: str):
        self._set_field('_senha', senha_plana)

    def get_senha(self) -> str:
        return self._get_field('_senha')

    # Propriedades para facilitar o acesso aos campos
    @property
    def password(self):
        return self.get_senha()

    @password.setter
    def password(self, value):
        self.set_senha(value)


class CircularizacaoAcesso(models.Model):
    cliente = models.ForeignKey(CircularizacaoCliente, on_delete=models.CASCADE, related_name='circularizacao_acesso')
    tipo = models.CharField(max_length=4)
    codigo = models.CharField(max_length=7)
    ordem = models.IntegerField()
    destinatario_nome = models.CharField(max_length=255)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    deletado_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'cloud_circularizacao_acesso'
        verbose_name = 'Acesso de Circularização'
        verbose_name_plural = 'Acessos de Circularização'

    def __str__(self):
        return f"Acesso por {self.cliente.usuario.username}: {self.tipo} - {self.codigo}"


class CircularizacaoArquivoRecebido(models.Model):
    acesso = models.ForeignKey('CircularizacaoAcesso', on_delete=models.CASCADE, related_name='arquivos_recebidos')
    nome_arquivo_original = models.CharField(max_length=255, blank=True)
    extensao_arquivo = models.CharField(max_length=10, blank=True)
    arquivo = models.FileField(upload_to='circularizacao/arquivos_recebidos/')
    criado_em = models.DateTimeField(auto_now_add=True)
    deletado_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'cloud_circularizacao_arquivo_recebido'
        verbose_name = 'Arquivo Recebido de Circularização'
        verbose_name_plural = 'Arquivos Recebidos de Circularização'

    def __str__(self):
        return f"Arquivo {self.nome_arquivo_original} para acesso {self.acesso.tipo} - {self.acesso.codigo}"

    def save(self, *args, **kwargs):
        # Se o arquivo foi enviado e nome/extensão não foram fornecidos, preenche automaticamente
        if self.arquivo and not self.nome_arquivo_original:
            self.nome_arquivo_original = self.arquivo.name

        if self.arquivo and not self.extensao_arquivo:
            import os
            nome, extensao = os.path.splitext(self.arquivo.name)
            self.extensao_arquivo = extensao.lower().replace('.', '')

        super().save(*args, **kwargs)
