from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('chat', '0002_clientes_bloqueado_clientes_fecha_nacimiento'),
    ]

    operations = [
        migrations.AddField(
            model_name='clientes',
            name='correo',
            field=models.EmailField(blank=True, max_length=254, null=True),
        ),
        migrations.RemoveField(
            model_name='clientes',
            name='password',
        ),
    ]