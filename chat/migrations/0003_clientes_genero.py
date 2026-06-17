from django.db import migrations, models


class Migration(migrations.Migration):

    atomic = False

    dependencies = [
        ('chat', '0002_login_tables'),
    ]

    operations = [
        migrations.AddField(
            model_name='clientes',
            name='genero',
            field=models.CharField(
                blank=True,
                choices=[('hombre', 'Hombre'), ('mujer', 'Mujer')],
                max_length=10,
                null=True,
            ),
        ),
    ]