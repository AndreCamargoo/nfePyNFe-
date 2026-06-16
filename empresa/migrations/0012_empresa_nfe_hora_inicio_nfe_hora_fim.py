from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('empresa', '0011_alter_funcionario_role'),
    ]

    operations = [
        migrations.AddField(
            model_name='empresa',
            name='nfe_hora_inicio',
            field=models.IntegerField(default=0, help_text='Hora de início da automação NFe (0-23)'),
        ),
        migrations.AddField(
            model_name='empresa',
            name='nfe_hora_fim',
            field=models.IntegerField(default=6, help_text='Hora de fim da automação NFe (0-23)'),
        ),
    ]
