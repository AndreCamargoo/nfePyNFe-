from django.db import models

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

ORIGEM_LEAD_CHOICES = (
    ('Allnube', 'Allnube'), ('Auditoria', 'Auditoria'),
    ('Numb3rs', 'Numb3rs'), ('Balanço Padrão', 'Balanço Padrão'),
)


class EventoContato(models.Model):
    nome = models.CharField(max_length=255)
    cargo = models.CharField(max_length=100)
    email = models.EmailField(max_length=254)
    telefone = models.CharField(max_length=15)
    origem_lead = models.CharField(max_length=20, choices=ORIGEM_LEAD_CHOICES)
    status = models.CharField(max_length=1, choices=STATUS_CHOICES, default='1')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'agenda_evento_contato'
        verbose_name = 'Evento de Contato'
        verbose_name_plural = 'Eventos de Contato'

    def __str__(self):
        return self.nome


class EventoCadastroEmpresa(models.Model):
    contato = models.ForeignKey(
        EventoContato,
        on_delete=models.CASCADE,
        related_name='empresas'
    )
    documento = models.CharField(max_length=18, unique=True)
    nome_empresa = models.CharField(max_length=255)
    telefone = models.CharField(max_length=15)
    email = models.EmailField(max_length=254)
    endereco = models.CharField(max_length=255)
    cidade = models.CharField(max_length=100)
    uf = models.CharField(max_length=2, choices=ESTADOS_CHOICES)
    status = models.CharField(max_length=1, choices=STATUS_CHOICES, default='1')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'agenda_evento_cadastro_empresa'
        verbose_name = 'Evento de Cadastro de Empresa'
        verbose_name_plural = 'Eventos de Cadastro de Empresas'

    def __str__(self):
        return f"{self.nome_empresa} - {self.documento}"
