from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('empresa', '0010_alter_funcionario_role'),
    ]

    operations = [
        migrations.AlterField(
            model_name='funcionario',
            name='role',
            field=models.CharField(choices=[('admin', 'Administrador'), ('cliente', 'Cliente'), ('funcionario', 'Funcionário'), ('auditor', 'Auditor'), ('administrativo', 'Administrativo'), ('estagiario', 'Estagiário'), ('cliente_externo', 'Cliente Externo'), ('secretaria', 'Secretaria'), ('financeiro', 'Financeiro'), ('auxiliar_geral', 'Auxiliar geral')], max_length=20),
        ),
    ]
