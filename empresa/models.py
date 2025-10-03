from django.contrib.auth.models import User
from django.db import models

from django.conf import settings
from cryptography.fernet import Fernet
import base64
import os


ESTADOS_CHOICES = (
    ('AC', 'Acre'), ('AL', 'Alagoas'), ('AP', 'Amapá'), ('AM', 'Amazonas'),
    ('BA', 'Bahia'), ('CE', 'Ceará'), ('DF', 'Distrito Federal'),
    ('ES', 'Espírito Santo'), ('GO', 'Goiás'), ('MA', 'Maranhão'),
    ('MT', 'Mato Grosso'), ('MS', 'Mato Grosso do Sul'),
    ('MG', 'Minas Gerais'), ('PA', 'Pará'), ('PB', 'Paraíba'),
    ('PR', 'Paraná'), ('PE', 'Pernambuco'), ('PI', 'Piauí'),
    ('RJ', 'Rio de Janeiro'), ('RN', 'Rio Grande do Norte'),
    ('RS', 'Rio Grande do Sul'), ('RO', 'Rondônia'), ('RR', 'Roraima'),
    ('SC', 'Santa Catarina'), ('SP', 'São Paulo'),
    ('SE', 'Sergipe'), ('TO', 'Tocantins'),
)

STATUS_CHOICES = (
    ('1', 'Ativo'), ('2', 'Inativo'),
)


def get_fernet():
    key = getattr(settings, 'FERNET_SECRET_KEY', None)
    if not key:
        raise Exception("FERNET_SECRET_KEY não está configurada no settings.")
    return Fernet(key.encode())


class CategoriaEmpresa(models.Model):
    nome = models.CharField(max_length=100)
    descricao = models.TextField(blank=True, null=True)
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='subcategorias'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.nome


class Empresa(models.Model):
    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='empresas')
    categoria = models.ForeignKey(CategoriaEmpresa, on_delete=models.SET_NULL, null=True, blank=True, related_name='empresas_categoria')
    matriz_filial = models.ForeignKey('self', on_delete=models.CASCADE, blank=True, null=True, related_name='filiais')
    razao_social = models.CharField(max_length=200)
    documento = models.CharField(max_length=18, unique=True)
    ie = models.CharField(max_length=15, null=True, blank=True)
    uf = models.CharField(max_length=2, choices=ESTADOS_CHOICES)
    senha = models.CharField(max_length=255)
    file = models.FileField(upload_to='certificados/', null=True, blank=True)
    status = models.CharField(max_length=1, choices=STATUS_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.razao_social


class HistoricoNSU(models.Model):
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name='historico_empresa')
    nsu = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.empresa.razao_social


class ConexaoBanco(models.Model):
    empresa = models.OneToOneField('Empresa', on_delete=models.CASCADE, related_name='conexao_banco', unique=True)
    _host = models.BinaryField(db_column='host')
    _porta = models.BinaryField(db_column='porta')
    _usuario = models.BinaryField(db_column='usuario')
    _senha = models.BinaryField(db_column='senha')
    _database = models.BinaryField(db_column='database')
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'Conexão - {self.empresa.razao_social}'

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
    def set_host(self, host_plano: str):
        self._set_field('_host', host_plano)

    def get_host(self) -> str:
        return self._get_field('_host')

    def set_porta(self, porta_plano: int):
        self._set_field('_porta', str(porta_plano))

    def get_porta(self) -> int:
        return int(self._get_field('_porta'))

    def set_usuario(self, usuario_plano: str):
        self._set_field('_usuario', usuario_plano)

    def get_usuario(self) -> str:
        return self._get_field('_usuario')

    def set_database(self, database_plano: str):
        self._set_field('_database', database_plano)

    def get_database(self) -> str:
        return self._get_field('_database')

    def set_senha(self, senha_plana: str):
        self._set_field('_senha', senha_plana)

    def get_senha(self) -> str:
        return self._get_field('_senha')

    # Propriedades para facilitar o acesso aos campos
    @property
    def host(self):
        return self.get_host()

    @host.setter
    def host(self, value):
        self.set_host(value)

    @property
    def porta(self):
        return self.get_porta()

    @porta.setter
    def porta(self, value):
        self.set_porta(value)

    @property
    def usuario(self):
        return self.get_usuario()

    @usuario.setter
    def usuario(self, value):
        self.set_usuario(value)

    @property
    def database(self):
        return self.get_database()

    @database.setter
    def database(self, value):
        self.set_database(value)

    @property
    def password(self):
        return self.get_senha()

    @password.setter
    def password(self, value):
        self.set_senha(value)
