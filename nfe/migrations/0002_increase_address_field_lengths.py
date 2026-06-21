from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('nfe', '0001_initial'),
    ]

    operations = [
        # Emitente
        migrations.AlterField(model_name='emitente', name='xLgr', field=models.CharField(max_length=200, null=True, blank=True)),
        migrations.AlterField(model_name='emitente', name='nro', field=models.CharField(max_length=60, null=True, blank=True)),
        migrations.AlterField(model_name='emitente', name='xBairro', field=models.CharField(max_length=120, null=True, blank=True)),
        migrations.AlterField(model_name='emitente', name='xMun', field=models.CharField(max_length=120, null=True, blank=True)),
        migrations.AlterField(model_name='emitente', name='xPais', field=models.CharField(max_length=60, null=True, blank=True)),
        migrations.AlterField(model_name='emitente', name='fone', field=models.CharField(max_length=20, null=True, blank=True)),
        # Destinatario
        migrations.AlterField(model_name='destinatario', name='xLgr', field=models.CharField(max_length=200, null=True, blank=True)),
        migrations.AlterField(model_name='destinatario', name='nro', field=models.CharField(max_length=60, null=True, blank=True)),
        migrations.AlterField(model_name='destinatario', name='xCpl', field=models.CharField(max_length=120, null=True, blank=True)),
        migrations.AlterField(model_name='destinatario', name='xBairro', field=models.CharField(max_length=120, null=True, blank=True)),
        migrations.AlterField(model_name='destinatario', name='xMun', field=models.CharField(max_length=120, null=True, blank=True)),
        migrations.AlterField(model_name='destinatario', name='xPais', field=models.CharField(max_length=60, null=True, blank=True)),
    ]
