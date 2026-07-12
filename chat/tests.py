import json
from datetime import date

from django.test import TestCase
from django.urls import reverse

from .models import Clientes


class SuperadminLoginTests(TestCase):
    def test_login_creates_superadmin_when_missing(self):
        Clientes.objects.filter(cedula='SuperAdminFarmaLuz').delete()

        response = self.client.post(reverse('chat:login'), {'cedula': 'SuperAdminFarmaLuz'})

        self.assertEqual(response.status_code, 302)
        self.assertTrue(Clientes.objects.filter(cedula='SuperAdminFarmaLuz').exists())
        self.assertRedirects(response, reverse('chat:admin_dashboard'))


class ClienteRegistrationTests(TestCase):
    def test_registration_saves_birth_date_and_phone(self):
        response = self.client.post(reverse('chat:registro'), {
            'nombre': 'Ana',
            'apellido': 'Pérez',
            'cedula': '12345678',
            'correo': 'ana@correo.com',
            'patologia': 'Asma',
            'genero': 'mujer',
            'direccion': 'Calle 1',
            'n_telefono': '04121234567',
            'fecha_nacimiento': '2000-01-15',
        })

        self.assertEqual(response.status_code, 302)
        cliente = Clientes.objects.get(cedula='12345678')
        self.assertEqual(cliente.fecha_nacimiento, date(2000, 1, 15))
        self.assertEqual(cliente.n_telefono, '04121234567')
        self.assertEqual(cliente.correo, 'ana@correo.com')


class ChatBlockTests(TestCase):
    def test_blocked_client_cannot_send_messages(self):
        cliente = Clientes.objects.create(
            cedula='99999999',
            nombre='Luis',
            apellido='Márquez',
            fecha_nacimiento=date(1990, 1, 1),
            n_telefono='04121234567',
            bloqueado=True,
        )

        session = self.client.session
        session['user_type'] = 'client'
        session['cliente_id'] = cliente.cliente_id
        session['cliente_cedula'] = cliente.cedula
        session.save()

        response = self.client.post(
            reverse('chat:enviar_mensaje'),
            data=json.dumps({'mensaje': 'hola'}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 403)
        self.assertTrue(json.loads(response.content)['blocked'])
