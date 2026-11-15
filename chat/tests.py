import json
import re
from datetime import date

from captcha.models import CaptchaStore
from django.contrib.auth.hashers import check_password, make_password
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Almacen, ChatMessage, Clientes, Productos


def captcha_response():
    key = CaptchaStore.generate_key()
    challenge = CaptchaStore.objects.get(hashkey=key)
    return {'captcha_0': key, 'captcha_1': challenge.response}


class SuperadminLoginTests(TestCase):
    def test_superadmin_login_requires_password_and_captcha(self):
        Clientes.objects.create(
            cedula='SuperAdminFarmaLuz',
            password=make_password('Old-SuperAdmin-Password-1'),
        )

        response = self.client.post(reverse('chat:login'), {
            'cedula': 'SuperAdminFarmaLuz',
            'password': 'Old-SuperAdmin-Password-1',
            **captcha_response(),
        })

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('chat:admin_dashboard'))


class ClienteRegistrationTests(TestCase):
    def test_registration_saves_birth_date_and_phone(self):
        response = self.client.post(reverse('chat:registro'), {
            'nombre': 'Ana',
            'apellido': 'Pérez',
            'cedula': '12345678',
            'correo': 'ana@correo.com',
            'patologia': 'diabetes',
            'genero': 'mujer',
            'direccion': 'Calle 1',
            'n_telefono': '04121234567',
            'fecha_nacimiento': '2000-01-15',
            'password': 'StrongRegistrationPassword123!',
            'confirm_password': 'StrongRegistrationPassword123!',
            'accept_terms': 'on',
            **captcha_response(),
        })

        self.assertEqual(response.status_code, 302)
        cliente = Clientes.objects.get(cedula='12345678')
        self.assertEqual(cliente.fecha_nacimiento, date(2000, 1, 15))
        self.assertEqual(cliente.n_telefono, '04121234567')
        self.assertEqual(cliente.correo, 'ana@correo.com')
        self.assertTrue(check_password('StrongRegistrationPassword123!', cliente.password))

    def test_registration_rejects_non_numeric_phone(self):
        response = self.client.post(reverse('chat:registro'), {
            'nombre': 'Ana',
            'apellido': 'Pérez',
            'cedula': '12345678',
            'correo': 'ana@correo.com',
            'patologia': 'diabetes',
            'genero': 'mujer',
            'direccion': 'Calle 1',
            'n_telefono': '0412-1234567',
            'fecha_nacimiento': '2000-01-15',
            'password': 'StrongRegistrationPassword123!',
            'confirm_password': 'StrongRegistrationPassword123!',
            'accept_terms': 'on',
            **captcha_response(),
        })

        self.assertEqual(response.status_code, 400)
        self.assertFalse(Clientes.objects.filter(cedula='12345678').exists())


class SuperadminPasswordChangeTests(TestCase):
    def setUp(self):
        self.cliente = Clientes.objects.create(
            cedula='SuperAdminFarmaLuz',
            password=make_password('Old-SuperAdmin-Password-1'),
        )
        session = self.client.session
        session['user_type'] = 'admin'
        session['cliente_id'] = self.cliente.cliente_id
        session['cliente_cedula'] = self.cliente.cedula
        session['last_activity'] = timezone.now().timestamp()
        session.save()

    def test_password_change_checks_current_password_and_saves_hash(self):
        response = self.client.post(reverse('chat:superadmin_password_change'), {
            'current_password': 'Old-SuperAdmin-Password-1',
            'new_password': 'New-SuperAdmin-Password-2!',
            'confirm_password': 'New-SuperAdmin-Password-2!',
        })

        self.assertRedirects(response, reverse('chat:admin_dashboard'))
        self.cliente.refresh_from_db()
        self.assertTrue(check_password('New-SuperAdmin-Password-2!', self.cliente.password))

    def test_password_change_modal_has_toggle_controls_and_live_requirements(self):
        response = self.client.get(reverse('chat:admin_dashboard'))
        content = response.content.decode()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(content.count('data-password-toggle='), 3)
        for requirement_id in (
            'adminReqLength',
            'adminReqUppercase',
            'adminReqLowercase',
            'adminReqNumber',
            'adminReqSpecial',
        ):
            self.assertIn(requirement_id, content)
        self.assertIn('chat/js/admin_password_change.js', content)
        self.assertNotRegex(content, r'\sstyle\s*=')


class ChatHistoryPaginationTests(TestCase):
    def setUp(self):
        self.cliente = Clientes.objects.create(
            cedula='12345678',
            nombre='Ana',
            password=make_password('Client-Password-1!'),
        )
        self.conversation_key = self.cliente.cedula
        self.message_ids = []
        for index in range(55):
            message = ChatMessage.objects.create(
                conversation_key=self.conversation_key,
                cliente=self.cliente,
                sender=ChatMessage.Sender.CLIENT,
                message=f'Mensaje {index}',
            )
            self.message_ids.append(message.pk)

    def _set_client_session(self):
        session = self.client.session
        session['user_type'] = 'client'
        session['cliente_id'] = self.cliente.cliente_id
        session['cliente_cedula'] = self.cliente.cedula
        session['conversation_key'] = self.conversation_key
        session.save()

    def test_chat_initial_history_is_limited_and_older_messages_are_fetchable(self):
        self._set_client_session()
        response = self.client.get(reverse('chat:bot_chat'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['chat_history']), 50)
        self.assertTrue(response.context['history_has_more'])

        oldest_initial_id = response.context['chat_history'][0]['id']
        older_response = self.client.get(
            reverse('chat:chat_history'),
            {'before_id': oldest_initial_id},
        )

        self.assertEqual(older_response.status_code, 200)
        older_messages = older_response.json()['messages']
        self.assertEqual(len(older_messages), 5)
        self.assertEqual(
            [message['id'] for message in older_messages],
            self.message_ids[:5],
        )
        self.assertFalse(older_response.json()['has_more'])

    def test_chat_history_endpoint_requires_client_session(self):
        response = self.client.get(reverse('chat:chat_history'))
        self.assertEqual(response.status_code, 403)

    def test_admin_dashboard_loads_only_the_latest_history_page(self):
        admin = Clientes.objects.create(
            cedula='SuperAdminFarmaLuz',
            password=make_password('Admin-Password-1!'),
        )
        session = self.client.session
        session['user_type'] = 'admin'
        session['cliente_id'] = admin.cliente_id
        session['cliente_cedula'] = admin.cedula
        session.save()

        response = self.client.get(reverse('chat:admin_dashboard'))

        self.assertEqual(response.status_code, 200)
        conversation = response.context['conversations'][0]
        self.assertEqual(len(conversation['messages']), 50)
        self.assertTrue(conversation['has_more'])
        self.assertTrue(conversation['messages_loaded'])

        older_response = self.client.get(
            reverse('chat:admin_conversation_history'),
            {
                'conversation_key': self.conversation_key,
                'before_id': conversation['messages'][0]['id'],
            },
        )

        self.assertEqual(older_response.status_code, 200)
        older_messages = older_response.json()['messages']
        self.assertEqual(len(older_messages), 5)
        self.assertFalse(older_response.json()['has_more'])


class ProductStockQueryTests(TestCase):
    def test_stock_command_prefetches_inventory_for_all_limited_products(self):
        for index, quantity in enumerate((12, 4, 0)):
            product = Productos.objects.create(
                nombre_producto=f'Analgesico {index}',
                descripcion='',
                contenido='',
                marca='',
                tiene_iva=False,
            )
            Almacen.objects.create(id_producto=product, cantidad=quantity)

        from .views import ChatBotFarmaluz

        with self.assertNumQueries(2):
            response = ChatBotFarmaluz().procesar_mensaje('disponible analgesico')

        self.assertIn('Disponible (12 unidades)', response)
        self.assertIn('Cantidad baja (4 unidades)', response)
        self.assertIn('Agotado', response)


class PasswordResetConfirmationTests(TestCase):
    def test_password_reset_redirects_to_login_with_success_message(self):
        cliente = Clientes.objects.create(
            cedula='12345678',
            correo='ana@correo.com',
            password=make_password('Old-Registration-Password-1!'),
        )
        from django.utils.encoding import force_bytes
        from django.utils.http import urlsafe_base64_encode
        from .views import _build_reset_signature

        uidb64 = urlsafe_base64_encode(force_bytes(cliente.cliente_id))
        signed_token = _build_reset_signature(uidb64, 'reset-token')
        email_token = urlsafe_base64_encode(force_bytes(signed_token))
        confirm_url = reverse('chat:password_reset_confirm', kwargs={'signed_token': email_token})
        confirm_page = self.client.get(confirm_url)
        self.assertEqual(confirm_page.status_code, 200)
        self.assertEqual(
            confirm_page.content.decode().count('class="input-wrap password-input-wrap"'),
            2,
        )
        self.assertNotRegex(confirm_page.content.decode(), r'\sstyle\s*=')

        response = self.client.post(
            confirm_url,
            {
                'new_password1': 'Reset-Registration-Password-2!',
                'new_password2': 'Reset-Registration-Password-2!',
            },
        )

        self.assertRedirects(
            response,
            reverse('chat:login'),
            fetch_redirect_response=False,
        )
        login_response = self.client.get(response.url)
        self.assertContains(login_response, 'Tu contraseña se actualizó correctamente.')
        cliente.refresh_from_db()
        self.assertTrue(check_password('Reset-Registration-Password-2!', cliente.password))


class SessionTimeoutTests(TestCase):
    def test_user_can_explicitly_renew_session_during_warning_grace_period(self):
        session = self.client.session
        session['user_type'] = 'client'
        session['last_activity'] = timezone.now().timestamp() - 481
        session.save()

        response = self.client.post(reverse('chat:renew_session'))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['ok'])
        self.assertGreater(self.client.session['last_activity'], timezone.now().timestamp() - 5)

    def test_expired_session_is_flushed_and_redirects_with_message_marker(self):
        cliente = Clientes.objects.create(cedula='12345678')
        session = self.client.session
        session['user_type'] = 'client'
        session['cliente_id'] = cliente.cliente_id
        session['cliente_cedula'] = cliente.cedula
        session['last_activity'] = timezone.now().timestamp() - 520
        session.save()

        response = self.client.get(reverse('chat:bot_chat'))

        self.assertRedirects(response, f"{reverse('chat:login')}?expired=1")
        self.assertNotIn('user_type', self.client.session)


class AuthTemplateSecurityTests(TestCase):
    def test_auth_forms_render_captcha_under_csp(self):
        for url in (
            reverse('chat:login'),
            reverse('chat:registro'),
            reverse('chat:password_reset'),
        ):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'captcha')
                policy = response.headers['Content-Security-Policy']
                self.assertIn("script-src 'self'", policy)
                self.assertIn('https://fonts.googleapis.com', policy)
                self.assertIn('https://cdnjs.cloudflare.com', policy)
                self.assertNotRegex(response.content.decode(), r'\sstyle\s*=')
                self.assertNotRegex(response.content.decode(), r'<script(?![^>]*\bsrc=)[^>]*>')

    def test_registration_links_terms_in_a_new_tab(self):
        response = self.client.get(reverse('chat:registro'))
        content = response.content.decode()
        checkbox_position = content.index('name="accept_terms"')
        submit_position = content.index('Guardar registro')

        self.assertIn('target="_blank"', content[checkbox_position:submit_position])
        self.assertLess(checkbox_position, submit_position)
        self.assertEqual(self.client.get(reverse('chat:terminos')).status_code, 200)

    def test_registration_errors_are_rendered_without_raw_field_names(self):
        response = self.client.post(reverse('chat:registro'), {})
        content = response.content.decode()

        self.assertEqual(response.status_code, 400)
        summary = re.search(
            r'<div class="error-box form-error-summary" role="alert">(.*?)</div>',
            content,
            re.DOTALL,
        )
        self.assertIsNotNone(summary)
        self.assertNotIn('<ul', summary.group(1))
        self.assertNotIn('<li>', summary.group(1))
        self.assertNotIn('correo', summary.group(1))

    def test_password_reset_rejects_submission_without_captcha(self):
        response = self.client.post(reverse('chat:password_reset'), {
            'correo': 'ana@correo.com',
        })

        self.assertEqual(response.status_code, 400)
        self.assertContains(response, 'captcha', status_code=400)


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
