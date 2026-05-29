from django.db import models
import random
import string


def gerar_codigo():
    """Gera código único de 6 dígitos numéricos."""
    return ''.join(random.choices(string.digits, k=6))


class EventoSorteio(models.Model):
    nome = models.CharField(max_length=255)
    descricao = models.TextField(blank=True)
    local = models.CharField(max_length=300, blank=True)
    data_evento = models.DateField()
    ativo = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-data_evento']

    def __str__(self):
        return f"{self.nome} ({self.data_evento})"


class ParticipanteSorteio(models.Model):
    evento = models.ForeignKey(EventoSorteio, on_delete=models.CASCADE, related_name='participantes')
    empresa = models.CharField(max_length=500)
    cnes = models.CharField(max_length=50, blank=True)
    cnpj = models.CharField(max_length=50, blank=True)
    cidade = models.CharField(max_length=200, blank=True)
    estado = models.CharField(max_length=2, blank=True)
    contato_nome = models.CharField(max_length=300)
    email = models.EmailField(blank=True)
    telefone = models.CharField(max_length=100, blank=True)
    cargo = models.CharField(max_length=200, blank=True)
    codigo = models.CharField(max_length=6, unique=True)
    vencedor = models.BooleanField(default=False)
    sorteado_em = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.codigo:
            while True:
                codigo = gerar_codigo()
                if not ParticipanteSorteio.objects.filter(codigo=codigo).exists():
                    self.codigo = codigo
                    break
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.contato_nome} — {self.empresa} [{self.codigo}]"
