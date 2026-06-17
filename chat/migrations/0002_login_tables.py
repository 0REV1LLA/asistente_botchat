from django.db import migrations
from django.contrib.auth.hashers import make_password


def create_demo_accounts(apps, schema_editor):
    Clientes = apps.get_model('chat', 'Clientes')

    Clientes.objects.get_or_create(
        cedula='SuperAdminFarmaLuz',
        defaults={
            'password': make_password('SuperAdminFarmaLuz'),
            'nombre': 'Super',
            'apellido': 'Admin',
        },
    )

    Clientes.objects.get_or_create(
        cedula='12345678',
        defaults={
            'password': make_password('12345678'),
            'nombre': 'Cliente',
            'apellido': 'Demo',
        },
    )
class Migration(migrations.Migration):

    atomic = False

    dependencies = [
        ('chat', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(create_demo_accounts, migrations.RunPython.noop),
    ]
