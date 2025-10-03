from django.db import models
from django.contrib.auth.hashers import make_password, check_password
from django.core.exceptions import ValidationError

from empresa.models import Empresa
from sistema.models import Sistema, RotaSistema, GrupoRotaSistema


CARGOS_CHOICES = (
    ('DIR', 'Diretor'), ('GER', 'Gerente'), ('SUP', 'Supervisor'), ('COORD', 'Coordenador'),
    ('ASS', 'Assistente'), ('AUX', 'Auxiliar'), ('ADM', 'Administrador'), ('ANL', 'Analista'),
    ('ENG', 'Engenheiro'), ('TEC', 'Técnico'), ('EST', 'Estagiário'), ('CONS', 'Consultor'),
    ('DEV', 'Desenvolvedor'), ('PROF', 'Professor'), ('MED', 'Médico'), ('ENF', 'Enfermeiro'),
    ('ADV', 'Advogado'), ('JUR', 'Jurídico'), ('PSI', 'Psicólogo'), ('VEND', 'Vendedor'),
    ('REP', 'Representante'), ('MKT', 'Marketing'), ('RH', 'Recursos Humanos'),
    ('FIN', 'Financeiro'), ('CONT', 'Contador'), ('TI', 'TI - Tecnologia da Informação'),
    ('OPR', 'Operador'), ('MEC', 'Mecânico'), ('MOT', 'Motorista'), ('ZEL', 'Zelador'),
    ('SEG', 'Segurança'), ('LIM', 'Serviços Gerais / Limpeza'), ('RECP', 'Recepcionista'),
    ('ATD', 'Atendente'),
)


class UsuarioEmpresa(models.Model):
    nome = models.CharField(max_length=100, null=True, blank=True)
    email = models.EmailField(max_length=100, unique=True, null=True, blank=True)
    username = models.CharField(max_length=150, unique=True, null=True, blank=True)
    password = models.CharField(max_length=128, null=True, blank=True)
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name="usuarios")
    cargo = models.CharField(max_length=10, choices=CARGOS_CHOICES, null=True, blank=True)
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    atualizado_em = models.DateTimeField(auto_now=True, null=True, blank=True)

    def set_password(self, raw_password):
        """Define a senha de forma segura."""
        self.password = make_password(raw_password)

    def check_password(self, raw_password):
        """Verifica a senha de forma segura."""
        return check_password(raw_password, self.password)

    def __str__(self):
        return f"{self.username} - {self.empresa.razao_social}"


class UsuarioSistema(models.Model):
    usuario_empresa = models.ForeignKey(UsuarioEmpresa, on_delete=models.CASCADE, related_name="sistemas")
    sistema = models.ForeignKey(Sistema, on_delete=models.CASCADE, related_name="usuarios")
    ativo = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.usuario_empresa} -> {self.sistema.nome}"


# acesso/models.py
class UsuarioPermissaoRota(models.Model):
    usuario_sistema = models.ForeignKey(UsuarioSistema, on_delete=models.CASCADE, related_name="permissoes_rotas")
    rota = models.ForeignKey(RotaSistema, on_delete=models.CASCADE, related_name="permissoes", null=True, blank=True)
    grupo = models.ForeignKey(GrupoRotaSistema, on_delete=models.CASCADE, related_name="permissoes", null=True, blank=True)
    permitido = models.BooleanField(default=True)

    class Meta:
        unique_together = [
            ("usuario_sistema", "rota"),
            ("usuario_sistema", "grupo")
        ]

    def clean(self):
        """Valida que pelo menos rota ou grupo deve ser fornecido, mas não ambos."""

        if not self.rota and not self.grupo:
            raise ValidationError("Pelo menos uma rota ou um grupo deve ser fornecido.")

        if self.rota and self.grupo:
            raise ValidationError("Apenas uma rota ou um grupo pode ser fornecido, não ambos.")

    def save(self, *args, **kwargs):
        """Chama clean() antes de salvar para validação."""
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        if self.rota:
            return f"{self.usuario_sistema.usuario_empresa.username} -> {self.rota.path} ({'Permitido' if self.permitido else 'Negado'})"
        elif self.grupo:
            return f"{self.usuario_sistema.usuario_empresa.username} -> Grupo: {self.grupo.nome} ({'Permitido' if self.permitido else 'Negado'})"
        return f"{self.usuario_sistema.usuario_empresa.username} -> Permissão"
