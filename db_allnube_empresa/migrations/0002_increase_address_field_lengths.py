from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('db_allnube_empresa', '0001_initial'),
    ]

    operations = [
        # EmitenteFlat
        migrations.AlterField(model_name='emitenteflat', name='xLgr', field=models.CharField(max_length=200, null=True, blank=True)),
        migrations.AlterField(model_name='emitenteflat', name='nro', field=models.CharField(max_length=60, null=True, blank=True)),
        migrations.AlterField(model_name='emitenteflat', name='xBairro', field=models.CharField(max_length=120, null=True, blank=True)),
        migrations.AlterField(model_name='emitenteflat', name='xMun', field=models.CharField(max_length=120, null=True, blank=True)),
        migrations.AlterField(model_name='emitenteflat', name='xPais', field=models.CharField(max_length=60, null=True, blank=True)),
        migrations.AlterField(model_name='emitenteflat', name='fone', field=models.CharField(max_length=20, null=True, blank=True)),
        # DestinatarioFlat
        migrations.AlterField(model_name='destinatarioflat', name='xLgr', field=models.CharField(max_length=200, null=True, blank=True)),
        migrations.AlterField(model_name='destinatarioflat', name='nro', field=models.CharField(max_length=60, null=True, blank=True)),
        migrations.AlterField(model_name='destinatarioflat', name='xCpl', field=models.CharField(max_length=120, null=True, blank=True)),
        migrations.AlterField(model_name='destinatarioflat', name='xBairro', field=models.CharField(max_length=120, null=True, blank=True)),
        migrations.AlterField(model_name='destinatarioflat', name='xMun', field=models.CharField(max_length=120, null=True, blank=True)),
        migrations.AlterField(model_name='destinatarioflat', name='xPais', field=models.CharField(max_length=60, null=True, blank=True)),
    ]
