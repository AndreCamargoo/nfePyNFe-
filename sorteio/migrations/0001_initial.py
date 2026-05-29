from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='EventoSorteio',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nome', models.CharField(max_length=255)),
                ('descricao', models.TextField(blank=True)),
                ('local', models.CharField(blank=True, max_length=300)),
                ('data_evento', models.DateField()),
                ('ativo', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={'ordering': ['-data_evento']},
        ),
        migrations.CreateModel(
            name='ParticipanteSorteio',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('empresa', models.CharField(max_length=500)),
                ('cnes', models.CharField(blank=True, max_length=50)),
                ('cnpj', models.CharField(blank=True, max_length=50)),
                ('cidade', models.CharField(blank=True, max_length=200)),
                ('estado', models.CharField(blank=True, max_length=2)),
                ('contato_nome', models.CharField(max_length=300)),
                ('email', models.EmailField(blank=True, max_length=254)),
                ('telefone', models.CharField(blank=True, max_length=100)),
                ('cargo', models.CharField(blank=True, max_length=200)),
                ('codigo', models.CharField(max_length=6, unique=True)),
                ('vencedor', models.BooleanField(default=False)),
                ('sorteado_em', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('evento', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='participantes', to='sorteio.eventosorteio')),
            ],
            options={'ordering': ['-created_at']},
        ),
    ]
