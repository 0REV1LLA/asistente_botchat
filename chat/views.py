import json
import secrets
import traceback
import binascii
from collections import OrderedDict
from datetime import timedelta

from django.conf import settings
from django.core import signing
from django.core.mail import EmailMultiAlternatives
from django.db.models import F, Prefetch, Window
from django.db.models.functions import RowNumber
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import force_bytes, force_str
from django.utils.timezone import localtime
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.views.decorators.csrf import csrf_exempt
from django.templatetags.static import static

import re
from django.contrib.auth.hashers import make_password, check_password
from django.contrib import messages
from django.views.decorators.http import require_GET, require_POST

from .constants import SUPERADMIN_CEDULA
from .forms import (
    LoginForm,
    PasswordResetRequestForm,
    RegistrationForm,
    SuperadminPasswordChangeForm,
)
from .models import Almacen, ChatMessage, Clientes, Productos, ChatsOcultos

#Configuraciones generales
BOT_NAME = 'Lucy'
BOT_EMOJI = '💁‍♀️'
PASSWORD_RESET_SESSION_KEY = 'password_reset_request'
PASSWORD_RESET_MAX_AGE = 60 * 60 * 24  # 24 horas

RAPID_COMMANDS = [
    ('productos', 'Ver la lista de productos'),
    ('precio NOMBRE', 'Consultar el precio de un producto'),
    ('disponible NOMBRE', 'Ver disponibilidad en inventario'),
    ('buscar NOMBRE', 'Buscar datos detallados de un producto'),
    ('ayuda', 'Ver todos los comandos disponibles'),
    ('lucy', 'Presentación de la asistente'),
    ('hola', 'Saludo inicial con guía rápida'),
    ('adios', 'Despedida del chat'),
]

#mensajes de error en consultas
def _catalog_unavailable_message(error_details=""):
    if error_details:
        return f'El catálogo de productos no está disponible (Error: {error_details}).'
    return 'El catálogo de productos no está disponible en esta base de datos todavía.'


def _safe_product_list(queryset, limit=None, with_stock=False):
    try:
        if with_stock:
            queryset = queryset.prefetch_related(Prefetch(
                'almacen',
                queryset=Almacen.objects.order_by('pk'),
                to_attr='_almacen_records',
            ))
        if limit is not None:
            return list(queryset[:limit])
        return list(queryset)
    except Exception as e:
        print(f"--- ERROR CRÍTICO EN CONSULTA DE PRODUCTOS ---")
        print(str(e))
        print(f"----------------------------------------------")
        return None


#configuracion de datos de admin
def _ensure_superadmin_exists():
    cliente, created = Clientes.objects.get_or_create(
        cedula=SUPERADMIN_CEDULA,
        defaults={
            'nombre': 'Super',
            'apellido': 'Admin',
        },
    )
    if created:
        cliente.save()
    return cliente


def _auth_brand_context(extra=None):
    context = {
        'assistant_name': BOT_NAME,
        'assistant_emoji': BOT_EMOJI,
    }
    if extra:
        context.update(extra)
    return context

#vistas de recuperacion de contraseña
def _password_reset_session_payload(uidb64, token, correo):
    return {
        'uidb64': uidb64,
        'token': token,
        'correo': correo,
        'expires_at': int((timezone.now() + timedelta(seconds=PASSWORD_RESET_MAX_AGE)).timestamp()),
    }


def _store_password_reset_state(request, uidb64, token, correo):
    request.session[PASSWORD_RESET_SESSION_KEY] = _password_reset_session_payload(uidb64, token, correo)
    request.session.set_expiry(PASSWORD_RESET_MAX_AGE)
    request.session.modified = True


def _clear_password_reset_state(request):
    request.session.pop(PASSWORD_RESET_SESSION_KEY, None)
    request.session.modified = True


def _get_password_reset_state(request):
    return request.session.get(PASSWORD_RESET_SESSION_KEY)


def _build_reset_signature(uidb64, token):
    """Construye una firma digital para el enlace de recuperación"""
    payload = {
        'uidb64': uidb64,
        'token': token,
    }
    return signing.dumps(payload, salt='password-reset')


def _decode_reset_signature(signed_token):
    """Decodifica y verifica la firma digital"""
    try:
        payload = signing.loads(signed_token, salt='password-reset', max_age=PASSWORD_RESET_MAX_AGE)
        
        if not isinstance(payload, dict):
            raise signing.BadSignature('Payload inválido')
        
        if 'uidb64' not in payload or 'token' not in payload:
            raise signing.BadSignature('Faltan campos requeridos')
        
        return payload
        
    except signing.BadSignature as e:
        print(f"❌ BadSignature: {e}")
        raise
    except signing.SignatureExpired as e:
        print(f"❌ SignatureExpired: {e}")
        raise
    except Exception as e:
        print(f"❌ Error en decode: {e}")
        raise signing.BadSignature(f'Error al decodificar: {e}')


def _cliente_from_uidb64(uidb64):
    try:
        cliente_id = force_str(urlsafe_base64_decode(uidb64))
    except (TypeError, ValueError, OverflowError):
        return None

    if not str(cliente_id).isdigit():
        return None

    return Clientes.objects.filter(cliente_id=int(cliente_id)).first()

#vistas para el correo de recuperacion
def _password_reset_form_context(**extra):
    context = _auth_brand_context()
    context.update(extra)
    return context


def _send_reset_email(cliente, reset_url):
    """Envía el correo de recuperación"""
    if not settings.DEFAULT_FROM_EMAIL or not settings.EMAIL_HOST_USER or not settings.EMAIL_HOST_PASSWORD:
        print(
            '❌ SMTP incompleto: '
            f'backend={settings.EMAIL_BACKEND}, '
            f'host={settings.EMAIL_HOST!r}, '
            f'usuario_configurado={bool(settings.EMAIL_HOST_USER)}, '
            f'password_configurada={bool(settings.EMAIL_HOST_PASSWORD)}, '
            f'remitente_configurado={bool(settings.DEFAULT_FROM_EMAIL)}'
        )
        raise RuntimeError(
            'Faltan EMAIL_HOST_USER, EMAIL_HOST_PASSWORD o DEFAULT_FROM_EMAIL en las variables de entorno.'
        )

    subject = 'Recuperación de Contraseña - FarmaLuz'
    
    lines = [
        f'Hola {cliente.nombre or "cliente"},',
        '',
        'Recibimos una solicitud para recuperar tu contraseña en FarmaLuz.',
        '',
        'Para restablecer tu contraseña, haz clic en el siguiente enlace:',
        reset_url,
        '',
        'Este enlace es válido por 24 horas.',
        '',
        'Si no realizaste esta solicitud, ignora este correo.',
        '',
        'Saludos,',
        'Equipo FarmaLuz'
    ]

    try:
        html_body = render_to_string('chat/password_reset_email.html', {
            'nombre': cliente.nombre or 'cliente',
            'reset_url': reset_url,
        })
        message = EmailMultiAlternatives(
            subject,
            '\n'.join(lines),
            settings.DEFAULT_FROM_EMAIL,
            [cliente.correo],
        )
        message.attach_alternative(html_body, 'text/html')
        message.send(fail_silently=False)
        print(f"✅ Correo enviado a: {cliente.correo}")
        print(f"🔗 Enlace: {reset_url}")
    except Exception as e:
        print(f"❌ Error al enviar correo: {e}")
        raise

#viista para el chat con el bot
class ChatBotFarmaluz:
    def procesar_mensaje(self, mensaje):
        mensaje = mensaje.lower().strip()

        if mensaje == 'lucy':
            return f"""{BOT_EMOJI} **Hola, soy {BOT_NAME}**, tu asistente virtual de FarmaLuz.

Puedo ayudarte a revisar productos, precios y stock de forma rápida.

**Ejemplo de uso:**
• `buscar diclofenac`
• `precio diclofenac`
• `disponible diclofenac`

Escribe `ayuda` para ver todos los comandos rápidos."""
        
        if mensaje in ['productos', 'lista', 'ver productos']:
            productos = _safe_product_list(Productos.objects.all(), 15)
            if productos is None:
                return _catalog_unavailable_message("Error al consultar la tabla de productos")
            if productos:
                respuesta = "📦 **LISTA DE PRODUCTOS:**\n\n"
                for p in productos:
                    precio = f"${p.precio_venta}" if getattr(p, 'precio_venta', None) else "Consultar"
                    respuesta += f"• {p.nombre_producto} - {precio}\n"
                return respuesta
            return "No hay productos registrados en la base de datos."
        
        if mensaje.startswith('precio '):
            producto_nombre = mensaje.replace('precio ', '').strip()
            if not producto_nombre:
                return "❌ Uso correcto: `precio NOMBRE`\nEjemplo: `precio paracetamol`"
            
            productos = _safe_product_list(
                Productos.objects.filter(nombre_producto__icontains=producto_nombre),
                5,
            )
            if productos is None:
                return _catalog_unavailable_message("Error en filtro de precio")
            if productos:
                respuesta = f"💰 **PRECIO DE '{producto_nombre}':**\n\n"
                for p in productos:
                    precio = f"${p.precio_venta}" if getattr(p, 'precio_venta', None) else "No disponible"
                    respuesta += f"• {p.nombre_producto}: {precio}\n"
                return respuesta
            return f"❌ No encontré '{producto_nombre}'. Usa `productos` para ver la lista."
        
        if mensaje.startswith('disponible '):
            producto_nombre = mensaje.replace('disponible ', '').strip()
            if not producto_nombre:
                return "❌ Uso correcto: `disponible NOMBRE`\nEjemplo: `disponible paracetamol`"
            
            productos = _safe_product_list(
                Productos.objects.filter(nombre_producto__icontains=producto_nombre),
                5,
                with_stock=True,
            )
            if productos is None:
                return _catalog_unavailable_message("Error en filtro de disponibilidad")
            if productos:
                respuesta = f"📊 **DISPONIBILIDAD DE '{producto_nombre}':**\n\n"
                for p in productos:
                    try:
                        stock_records = getattr(p, '_almacen_records', None)
                        stock = stock_records[0] if stock_records else None
                        cantidad = stock.cantidad if stock else 0
                    except Exception as e:
                        print(f"Error consultando Almacen: {e}")
                        cantidad = 0
                        
                    if cantidad > 10:
                        estado = f"✅ Disponible ({cantidad} unidades)"
                    elif cantidad > 0:
                        estado = f"⚠️ Cantidad baja ({cantidad} unidades)"
                    else:
                        estado = "❌ Agotado"
                    respuesta += f"• {p.nombre_producto}: {estado}\n"
                return respuesta
            return f"❌ No encontré '{producto_nombre}'. Usa `productos` para ver la lista."
        
        if mensaje.startswith('buscar '):
            producto_nombre = mensaje.replace('buscar ', '').strip()
            if not producto_nombre:
                return "❌ Uso correcto: `buscar NOMBRE`\nEjemplo: `buscar paracetamol`"
            
            productos = _safe_product_list(
                Productos.objects.filter(nombre_producto__icontains=producto_nombre),
                10,
                with_stock=True,
            )
            if productos is None:
                return _catalog_unavailable_message("Error en búsqueda detallada")
            if productos:
                respuesta = f"🔍 **RESULTADOS DE '{producto_nombre}':**\n\n"
                for p in productos:
                    try:
                        stock_records = getattr(p, '_almacen_records', None)
                        stock = stock_records[0] if stock_records else None
                        cantidad = stock.cantidad if stock else 0
                    except Exception:
                        cantidad = 0
                        
                    precio = f"${p.precio_venta}" if getattr(p, 'precio_venta', None) else "Consultar"
                    contenido = getattr(p, 'contenido', 'No especificado')
                    descripcion = getattr(p, 'descripcion', 'Sin descripción')
                    marca = getattr(p, 'marca', 'Genérico')
                    
                    respuesta += f"• {p.nombre_producto}\n"
                    respuesta += f"  💰 Precio: {precio}\n"
                    respuesta += f"  📦 Contenido: {contenido}\n"
                    respuesta += f"  📝 Descripción: {descripcion}\n"
                    respuesta += f"  📊 Cantidad en Almacén: {cantidad}\n"
                    respuesta += f"  🏷️ Marca: {marca}\n\n"
                return respuesta
            return f"❌ No encontré '{producto_nombre}'. Usa `productos` para ver la lista."
        
        if mensaje in ['ayuda', 'comandos', 'help']:
            return self.mostrar_ayuda()
        
        if mensaje in ['hola', 'buenas', 'hola buenas', 'buenos dias', 'buenas tardes', 'buenas noches', 'hi', 'hello']:
            return f"¡Hola! {BOT_EMOJI}\n\n" + self.mostrar_ayuda()
        
        if mensaje in ['adios', 'chao', 'hasta luego', 'nos vemos', 'bye', 'gracias']:
            return f"¡Gracias por consultar Farmaluz! {BOT_EMOJI}\n\nEscribe `hola` si necesitas algo más."
        
        return self.mostrar_error()
    
    #funcion de ayuda
    def mostrar_ayuda(self):
        lines = [f"{BOT_EMOJI} **COMANDOS RÁPIDOS:**", ""]
        for command, description in RAPID_COMMANDS:
            lines.append(f"• `{command}` - {description}")

        lines.extend([
            "",
            "**EJEMPLOS DE USO:**",
            "• `productos`",
            "• `precio diclofenac`",
            "• `disponible diclofenac`",
            "• `buscar diclofenac`",
            "",
            f"Escribe `lucy` para conocerme mejor o `hola` para empezar.",
        ])
        return "\n".join(lines)

    def mostrar_error(self):
        return """❌ **NO ENTENDÍ EL COMANDO**

Escribe `ayuda` para ver los comandos disponibles.

**EJEMPLOS VÁLIDOS:**
• `productos`
• `precio diclofenac`
• `disponible diclofenac`
• `buscar diclofenac`"""


bot = ChatBotFarmaluz()


def _full_name(cliente):
    if not cliente:
        return ''
    parts = [part for part in [cliente.nombre, cliente.apellido] if part]
    return ' '.join(parts).strip()

def _client_initials(cliente):
    nombre_completo = _full_name(cliente)
    if nombre_completo:
        letras = ''.join(parte.strip()[0] for parte in nombre_completo.split() if parte.strip())
        if letras:
            return letras[:2].upper()
    return (cliente.cedula[:2] or 'CL').upper()


def _client_display_name(cliente):
    nombre_completo = _full_name(cliente)
    return nombre_completo or (cliente.cedula if cliente else 'Cliente')


def _client_summary(cliente):
    if not cliente:
        return 'Cliente sin datos'
    nombre_completo = _client_display_name(cliente)
    return f"Cliente {nombre_completo} Cédula {cliente.cedula}" if nombre_completo else f"Cliente Cédula {cliente.cedula}"


def _client_avatar(cliente):
    genero = (getattr(cliente, 'genero', '') or '').strip().lower()
    if genero == 'mujer':
        return '💄'
    if genero == 'hombre':
        return '🧑‍⚕️'
    return '👤'


def _format_message_time(created_at):
    return localtime(created_at).strftime('%I:%M %p')


def _conversation_label(cliente):
    return _client_display_name(cliente)


def _message_sender_label(message):
    if message.sender == ChatMessage.Sender.CLIENT:
        return _client_summary(message.cliente)
    return f"{BOT_EMOJI} {BOT_NAME} · SuperAdmin"


def _message_bubble_class(message):
    return 'superadmin' if message.sender == ChatMessage.Sender.BOT else 'client'


def _is_admin_session(request):
    return request.session.get('user_type') == 'admin' and request.session.get('cliente_cedula') == SUPERADMIN_CEDULA


def _serialize_message(message):
    return {
        'id': message.pk,
        'sender': message.sender,
        'bubble_class': _message_bubble_class(message),
        'sender_label': _message_sender_label(message),
        'text': message.message,
        'time': _format_message_time(message.created_at),
    }


CHAT_HISTORY_PAGE_SIZE = 50


def _get_message_page(conversation_key, before_id=None):
    queryset = ChatMessage.objects.filter(
        conversation_key=conversation_key,
    ).select_related('cliente').order_by('-created_at', '-pk')
    if before_id is not None:
        queryset = queryset.filter(pk__lt=before_id)

    page = list(queryset[:CHAT_HISTORY_PAGE_SIZE + 1])
    has_more = len(page) > CHAT_HISTORY_PAGE_SIZE
    messages = [_serialize_message(message) for message in reversed(page[:CHAT_HISTORY_PAGE_SIZE])]
    return messages, has_more


def _get_chat_history(conversation_key):
    history, has_more = _get_message_page(conversation_key)

    if not history:
        history.append({
            'id': None,
            'sender': ChatMessage.Sender.BOT,
            'bubble_class': 'bot',
            'sender_label': f'{BOT_EMOJI} {BOT_NAME}',
            'text': '¡Hola! Soy Lucy, asistente de Farmaluz. Usa los comandos para aprovechar mejor tu consulta.',
            'time': '',
        })

    return history, has_more


# ============================================
# FUNCIÓN MODIFICADA - CON FILTRO DE CHATS OCULTOS EN BD Y PATOLOGÍA
# ============================================
def _build_conversations(request=None):
    conversations = OrderedDict()

    # Obtener lista de conversaciones ocultas desde la base de datos
    hidden = None
    if request and _is_admin_session(request):
        hidden = ChatsOcultos.objects.filter(
            superadmin_cedula=SUPERADMIN_CEDULA
        ).values_list('conversation_key', flat=True)

    messages = ChatMessage.objects.annotate(
        conversation_rank=Window(
            expression=RowNumber(),
            partition_by=[F('conversation_key')],
            order_by=[F('created_at').desc(), F('pk').desc()],
        ),
    ).filter(conversation_rank=1).select_related('cliente').order_by('conversation_key')
    if hidden is not None:
        messages = messages.exclude(conversation_key__in=hidden)

    for message in messages:
        conversation_key = message.conversation_key
        cliente = message.cliente

        conversations[conversation_key] = {
            'conversation_key': conversation_key,
            'cliente_id': cliente.cliente_id if cliente else None,
            'client_name': _conversation_label(cliente) if cliente else conversation_key,
            'client_summary': _client_summary(cliente) if cliente else conversation_key,
            'cedula': cliente.cedula if cliente else conversation_key,
            'patologia': cliente.patologia if cliente else None,
            'initials': _client_initials(cliente) if cliente else conversation_key[:2].upper(),
            'avatar': _client_avatar(cliente) if cliente else '👤',
            'last_time': _format_message_time(message.created_at),
            'last_message': message.message,
            'bloqueado': bool(cliente and cliente.bloqueado),
            'messages': [],
            'messages_loaded': False,
            'has_more': False,
        }

    return list(conversations.values())


def login_view(request):
    if request.method == 'GET':
        if _is_admin_session(request):
            return redirect('chat:admin_dashboard')
        if request.session.get('user_type') == 'client':
            return redirect('chat:bot_chat')
        return render(request, 'login.html', {
            'login_form': LoginForm(),
            'prefill_cedula': request.session.pop('login_prefill_cedula', ''),
            'registration_success': request.GET.get('registered') == '1',
            'session_expired': request.GET.get('expired') == '1',
            'assistant_name': BOT_NAME,
            'assistant_emoji': BOT_EMOJI,
        })

    form = LoginForm(request.POST)
    if not form.is_valid():
        return render(request, 'login.html', {
            'login_form': form,
            'prefill_cedula': request.POST.get('cedula', '').strip(),
            'assistant_name': BOT_NAME,
            'assistant_emoji': BOT_EMOJI,
        }, status=400)

    cedula = form.cleaned_data['cedula']
    password = form.cleaned_data['password']

    if cedula == SUPERADMIN_CEDULA:
        cliente = _ensure_superadmin_exists()
    else:
        cliente = Clientes.objects.filter(cedula=cedula).first()

    if not cliente:
        return render(request, 'login.html', {
            'error_message': 'Cédula incorrecta o no registrada.',
            'login_form': LoginForm(),
            'prefill_cedula': cedula,
            'assistant_name': BOT_NAME,
            'assistant_emoji': BOT_EMOJI,
        }, status=400)

    # Verificar si el cliente tiene contraseña (migración)
    if not cliente.password:
        return render(request, 'login.html', {
            'error_message': 'Debes restablecer tu contraseña usando "¿Olvidaste tu contraseña?".',
            'login_form': LoginForm(),
            'prefill_cedula': cedula,
            'assistant_name': BOT_NAME,
            'assistant_emoji': BOT_EMOJI,
        }, status=400)

    # Verificar bloqueo
    if cliente.bloqueado:
        return render(request, 'login.html', {
            'error_message': 'Usuario bloqueado por incumplir las normas de esta página web.',
            'login_form': LoginForm(),
            'prefill_cedula': cedula,
            'assistant_name': BOT_NAME,
            'assistant_emoji': BOT_EMOJI,
        }, status=403)

    # Verificar contraseña
    if not check_password(password, cliente.password):
        return render(request, 'login.html', {
            'error_message': 'Contraseña incorrecta.',
            'login_form': LoginForm(),
            'prefill_cedula': cedula,
            'assistant_name': BOT_NAME,
            'assistant_emoji': BOT_EMOJI,
        }, status=400)

    # 👇 GUARDAR EL CONVERSATION_KEY ANTES DE HACER FLUSH
    old_conversation_key = request.session.get('conversation_key')

    request.session.flush()
    request.session['user_type'] = 'admin' if cliente.cedula == SUPERADMIN_CEDULA else 'client'
    request.session['last_activity'] = timezone.now().timestamp()
    request.session['cliente_id'] = cliente.cliente_id
    request.session['cliente_cedula'] = cliente.cedula
    request.session['cliente_nombre'] = _client_display_name(cliente)
    request.session['cliente_summary'] = _client_summary(cliente)

    if old_conversation_key:
        request.session['conversation_key'] = old_conversation_key
    else:
        request.session['conversation_key'] = cliente.cedula

    redirect_url = reverse('chat:admin_dashboard') if cliente.cedula == SUPERADMIN_CEDULA else reverse('chat:bot_chat')
    return redirect(redirect_url)


def registro_view(request):
    if request.method == 'GET':
        if _is_admin_session(request):
            return redirect('chat:admin_dashboard')
        if request.session.get('user_type') == 'client':
            return redirect('chat:bot_chat')
        return render(request, 'registro.html', {
            'registration_form': RegistrationForm(),
            'assistant_name': BOT_NAME,
            'assistant_emoji': BOT_EMOJI,
        })

    form = RegistrationForm(request.POST)
    if not form.is_valid():
        form_values = request.POST.dict()
        form_values.pop('password', None)
        form_values.pop('confirm_password', None)
        return render(request, 'registro.html', {
            'registration_form': form,
            'form_values': form_values,
            'assistant_name': BOT_NAME,
            'assistant_emoji': BOT_EMOJI,
        }, status=400)

    data = form.cleaned_data
    cliente = Clientes.objects.create(
        cedula=data['cedula'],
        correo=data['correo'],
        nombre=data['nombre'],
        apellido=data['apellido'],
        patologia=data['patologia'],
        genero=data['genero'],
        direccion=data['direccion'],
        n_telefono=data['n_telefono'],
        fecha_nacimiento=data['fecha_nacimiento'],
        password=make_password(data['password']),
    )

    request.session['login_prefill_cedula'] = cliente.cedula
    request.session['registration_name'] = _client_display_name(cliente)
    return redirect(f"{reverse('chat:login')}?registered=1")


def chat_view(request):
    if _is_admin_session(request):
        return redirect('chat:admin_dashboard')

    if request.session.get('user_type') != 'client':
        return redirect('chat:login')

    cliente = Clientes.objects.filter(cliente_id=request.session.get('cliente_id')).first()
    conversation_key = request.session.get('conversation_key') or request.session.get('cliente_cedula') or ''

    cliente_nombre = request.session.get('cliente_nombre', 'Cliente')
    chat_history, history_has_more = _get_chat_history(conversation_key)
    return render(request, 'chat/index.html', {
        'cliente_nombre': cliente_nombre,
        'cliente_cedula': request.session.get('cliente_cedula', ''),
        'cliente_display_name': _conversation_label(cliente) if cliente else cliente_nombre,
        'assistant_name': BOT_NAME,
        'assistant_emoji': BOT_EMOJI,
        'last_activity': request.session.get('last_activity', timezone.now().timestamp()),
        'quick_commands': RAPID_COMMANDS,
        'chat_history': chat_history,
        'history_has_more': history_has_more,
        'cliente_bloqueado': bool(cliente and cliente.bloqueado),
    })


@require_GET
def chat_history_view(request):
    if request.session.get('user_type') != 'client':
        return JsonResponse({'error': 'Debes iniciar sesión como cliente.'}, status=403)

    before_id = request.GET.get('before_id')
    if before_id is not None:
        try:
            before_id = int(before_id)
        except ValueError:
            return JsonResponse({'error': 'El cursor del historial no es válido.'}, status=400)
        if before_id <= 0:
            return JsonResponse({'error': 'El cursor del historial no es válido.'}, status=400)

    conversation_key = (
        request.session.get('conversation_key')
        or request.session.get('cliente_cedula')
        or ''
    )
    history, has_more = _get_message_page(conversation_key, before_id)
    return JsonResponse({'messages': history, 'has_more': has_more})


@require_GET
def admin_conversation_history_view(request):
    if not _is_admin_session(request):
        return JsonResponse({'error': 'Debes iniciar sesión como administrador.'}, status=403)

    conversation_key = request.GET.get('conversation_key', '')
    if not conversation_key:
        return JsonResponse({'error': 'La conversación solicitada no es válida.'}, status=400)
    if ChatsOcultos.objects.filter(
        superadmin_cedula=SUPERADMIN_CEDULA,
        conversation_key=conversation_key,
    ).exists():
        return JsonResponse({'error': 'La conversación no está disponible.'}, status=404)

    before_id = request.GET.get('before_id')
    if before_id is not None:
        try:
            before_id = int(before_id)
        except ValueError:
            return JsonResponse({'error': 'El cursor del historial no es válido.'}, status=400)
        if before_id <= 0:
            return JsonResponse({'error': 'El cursor del historial no es válido.'}, status=400)

    history, has_more = _get_message_page(conversation_key, before_id)
    return JsonResponse({'messages': history, 'has_more': has_more})


# ============================================
# FUNCIÓN MODIFICADA - PASANDO 'request' A _build_conversations
# ============================================
def admin_dashboard_view(request):
    if not _is_admin_session(request):
        return redirect('chat:login')

    return _render_admin_dashboard(request)


def _render_admin_dashboard(request, password_form=None, status=200):
    cliente = Clientes.objects.filter(cliente_id=request.session.get('cliente_id')).first()
    if cliente is None:
        request.session.flush()
        return redirect('chat:login')
    conversations = _build_conversations(request)
    active_conversation = conversations[0] if conversations else None
    if active_conversation:
        active_conversation['messages'], active_conversation['has_more'] = _get_message_page(
            active_conversation['conversation_key'],
        )
        active_conversation['messages_loaded'] = True

    if password_form is None:
        password_form = SuperadminPasswordChangeForm(cliente=cliente)
    return render(request, 'admin_dashboard.html', {
        'conversations': conversations,
        'active_conversation': active_conversation,
        'total_messages': ChatMessage.objects.count(),
        'total_conversations': len(conversations),
        'brand_logo_url': static('chat/img/farmaluz-logo.png'),
        'assistant_name': BOT_NAME,
        'assistant_emoji': BOT_EMOJI,
        'last_activity': request.session.get('last_activity', timezone.now().timestamp()),
        'password_form': password_form,
    }, status=status)


def superadmin_password_change_view(request):
    if not _is_admin_session(request):
        return redirect('chat:login')
    if request.method != 'POST':
        return redirect('chat:admin_dashboard')

    cliente = Clientes.objects.filter(cliente_id=request.session.get('cliente_id')).first()
    if cliente is None:
        request.session.flush()
        return redirect('chat:login')

    form = SuperadminPasswordChangeForm(request.POST, cliente=cliente)
    if not form.is_valid():
        return _render_admin_dashboard(request, password_form=form, status=400)

    cliente.password = make_password(form.cleaned_data['new_password'])
    cliente.save(update_fields=['password'])
    messages.success(request, 'La contraseña del superadministrador se actualizó correctamente.')
    return redirect('chat:admin_dashboard')


@require_POST
def renew_session_view(request):
    if request.session.get('user_type') not in {'client', 'admin'}:
        return JsonResponse({'error': 'La sesión ya no está activa.'}, status=401)

    request.session['last_activity'] = timezone.now().timestamp()
    return JsonResponse({'ok': True})


def terminos_view(request):
    return render(request, 'terminos.html', _auth_brand_context())


def logout_view(request):
    request.session.flush()
    login_url = reverse('chat:login')
    if request.GET.get('expired') == '1':
        return redirect(f'{login_url}?expired=1')
    return redirect(login_url)


def toggle_bloqueo_cliente(request, cliente_id):
    if not _is_admin_session(request):
        return redirect('chat:login')

    cliente = Clientes.objects.filter(cliente_id=cliente_id).first()
    if cliente:
        cliente.bloqueado = not cliente.bloqueado
        cliente.save(update_fields=['bloqueado'])

    return redirect('chat:admin_dashboard')


# ============================================
# FUNCIÓN MODIFICADA - Cuando el usuario escribe, el chat reaparece
# ============================================
@csrf_exempt
def enviar_mensaje(request):
    if request.method == 'POST':
        try:
            if request.session.get('user_type') != 'client':
                return JsonResponse({
                    'error': 'Debes iniciar sesión como cliente para enviar mensajes.',
                    'success': False,
                }, status=403)

            data = json.loads(request.body)
            mensaje = data.get('mensaje', '')
            cliente_id = request.session.get('cliente_id')
            cliente = Clientes.objects.filter(cliente_id=cliente_id).first()

            if not cliente:
                return JsonResponse({
                    'error': 'La sesión del cliente no es válida.',
                    'success': False,
                }, status=401)

            if cliente.bloqueado:
                return JsonResponse({
                    'error': 'Usuario bloqueado',
                    'success': False,
                    'blocked': True,
                }, status=403)

            if not mensaje.strip():
                return JsonResponse({
                    'error': 'El mensaje no puede estar vacío.',
                    'success': False,
                }, status=400)

            conversation_key = request.session.get('conversation_key') or cliente.cedula
            request.session['conversation_key'] = conversation_key

            # ELIMINAR EL CHAT DE LA LISTA DE OCULTOS (SI EXISTE) - PARA QUE REAPAREZCA
            ChatsOcultos.objects.filter(
                superadmin_cedula=SUPERADMIN_CEDULA,
                conversation_key=conversation_key
            ).delete()

            ChatMessage.objects.create(
                cliente=cliente,
                conversation_key=conversation_key,
                sender=ChatMessage.Sender.CLIENT,
                message=mensaje.strip(),
            )
            
            respuesta = bot.procesar_mensaje(mensaje)
            ChatMessage.objects.create(
                cliente=cliente,
                conversation_key=conversation_key,
                sender=ChatMessage.Sender.BOT,
                message=respuesta,
            )
            
            return JsonResponse({
                'respuesta': respuesta,
                'success': True
            })
        except Exception as e:
            print(f"ERROR: {e}")
            return JsonResponse({
                'error': str(e),
                'respuesta': f"Error: {str(e)}",
                'success': False
            }, status=500)
    
    return JsonResponse({'error': 'Método no permitido'}, status=405)


# ============================================
# RECUPERACIÓN DE CONTRASEÑA
# ============================================
def password_reset_request(request):
    """Send a password reset email after validating the email and CAPTCHA."""
    form = PasswordResetRequestForm(request.POST or None)
    if request.method == 'POST':
        if not form.is_valid():
            return render(request, 'chat/password_reset_form.html', {
                **_password_reset_form_context(),
                'form': form,
            }, status=400)

        try:
            cliente = Clientes.objects.get(correo__iexact=form.cleaned_data['correo'])
            token = secrets.token_urlsafe(32)
            uidb64 = urlsafe_base64_encode(force_bytes(cliente.cliente_id))
            signed_token = _build_reset_signature(uidb64, token)
            email_token = urlsafe_base64_encode(force_bytes(signed_token))
            reset_path = reverse('chat:password_reset_confirm', kwargs={
                'signed_token': email_token,
            })
            public_url = settings.PUBLIC_URL
            if public_url and any(character in public_url for character in '[]()'):
                print('PUBLIC_URL contiene formato inválido; se usará el dominio de la solicitud.')
                public_url = ''
            reset_url = f'{public_url}{reset_path}' if public_url else request.build_absolute_uri(reset_path)
            _send_reset_email(cliente, reset_url)
            return redirect('chat:password_reset_done')
        except Clientes.DoesNotExist:
            return render(request, 'chat/password_reset_form.html', {
                **_password_reset_form_context(),
                'form': PasswordResetRequestForm(),
                'error_message': 'No existe un cliente con este correo electrónico.',
            }, status=400)
        except Exception as error:
            print(f'Error en password_reset_request: {error}')
            traceback.print_exc()
            return render(request, 'chat/password_reset_form.html', {
                **_password_reset_form_context(),
                'form': PasswordResetRequestForm(),
                'error_message': 'No fue posible enviar el correo. Intenta nuevamente más tarde.',
            }, status=500)

    return render(request, 'chat/password_reset_form.html', {
        **_password_reset_form_context(),
        'form': form,
    })


def password_reset_done(request):
    """Confirmación de envío de correo"""
    return render(request, 'chat/password_reset_done.html', _auth_brand_context())


def password_reset_confirm(request, signed_token):
    """Confirmar nueva Contraseña - Verificación por firma digital"""
    try:
        print(f"🔐 Token recibido: {signed_token[:50]}...")

        # Los enlaces nuevos usan Base64 URL-safe para evitar que los clientes
        # de correo separen el token por sus caracteres especiales.
        try:
            decoded_token = force_str(urlsafe_base64_decode(signed_token))
            if ':' in decoded_token:
                signed_token = decoded_token
        except (TypeError, ValueError, OverflowError, binascii.Error):
            pass
        
        # Decodificar el token firmado
        payload = _decode_reset_signature(signed_token)
        uidb64 = payload['uidb64']
        token = payload['token']
        
        print(f"🔑 UIDB64 decodificado: {uidb64}")
        print(f"🔑 Token decodificado: {token[:20]}...")
        
        # Obtener cliente
        cliente = _cliente_from_uidb64(uidb64)
        if not cliente:
            print(f"❌ Cliente no encontrado para UIDB64: {uidb64}")
            return render(request, 'chat/password_reset_confirm.html', {
                'error_message': 'Cliente no encontrado. El enlace es inválido.'
            })
        
        print(f"✅ Cliente encontrado: {cliente.cedula} - {cliente.correo}")
        
        if request.method == 'POST':
            new_password = request.POST.get('new_password1', '').strip()
            confirm_password = request.POST.get('new_password2', '').strip()
            
            # Validaciones
            if not new_password or not confirm_password:
                return render(request, 'chat/password_reset_confirm.html', {
                    'cliente': cliente,
                    'nombre_completo': _full_name(cliente) or 'Cliente',
                    'error_message': 'Debes ingresar y confirmar la nueva contraseña.'
                })
            
            if len(new_password) < 16:
                return render(request, 'chat/password_reset_confirm.html', {
                    'cliente': cliente,
                    'nombre_completo': _full_name(cliente) or 'Cliente',
                    'error_message': '⚠️ La contraseña debe tener al menos 16 caracteres.'
                })
            
            if new_password != confirm_password:
                return render(request, 'chat/password_reset_confirm.html', {
                    'cliente': cliente,
                    'nombre_completo': _full_name(cliente) or 'Cliente',
                    'error_message': 'Las contraseñas no coinciden.'
                })
            
            # ✅ CORRECTO: Hashear la contraseña antes de guardar
            from django.contrib.auth.hashers import make_password
            cliente.password = make_password(new_password)
            cliente.save()
            
            print(f"✅ Contraseña actualizada para: {cliente.correo}")
            
            # Limpiar sesión si existe
            _clear_password_reset_state(request)
            messages.success(request, 'Tu contraseña se actualizó correctamente.')
            return redirect('chat:login')
        
        return render(request, 'chat/password_reset_confirm.html', {
            'cliente': cliente,
            'nombre_completo': _full_name(cliente) or 'Cliente'
        })
        
    except signing.BadSignature as e:
        print(f"❌ BadSignature error: {e}")
        error_msg = str(e)
        if 'No ":" found in value' in error_msg:
            print("🔄 Token ya usado - Redirigiendo a página de éxito")
            return redirect('chat:password_reset_complete')
        return render(request, 'chat/password_reset_confirm.html', {
            'error_message': 'El enlace es inválido o ha sido manipulado. Solicita un nuevo enlace.'
        })
    except signing.SignatureExpired as e:
        print(f"❌ SignatureExpired error: {e}")
        return render(request, 'chat/password_reset_confirm.html', {
            'error_message': 'El enlace ha expirado. Solicita un nuevo enlace de recuperación.'
        })
    except Exception as e:
        print(f"❌ Error general en password_reset_confirm: {e}")
        traceback.print_exc()
        return render(request, 'chat/password_reset_confirm.html', {
            'error_message': f'Error: {str(e)}'
        })


def password_reset_complete(request):
    """Contraseña actualizada exitosamente"""
    return render(request, 'chat/password_reset_complete.html', _auth_brand_context())


# ============================================
# BORRAR CONVERSACIÓN (SUPERADMIN) - GUARDADO EN BD
# ============================================

@csrf_exempt
def borrar_conversacion(request):
    """Elimina una conversación del panel del SuperAdmin (guardado en BD)"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)
    
    # Verificar que sea SuperAdmin
    if not _is_admin_session(request):
        return JsonResponse({'error': 'No autorizado'}, status=403)
    
    try:
        data = json.loads(request.body)
        conversation_key = data.get('conversation_key')
        
        if not conversation_key:
            return JsonResponse({'error': 'Falta conversation_key'}, status=400)
        
        # 👇 GUARDAR EN BASE DE DATOS
        ChatsOcultos.objects.get_or_create(
            superadmin_cedula=SUPERADMIN_CEDULA,
            conversation_key=conversation_key
        )
        
        return JsonResponse({'success': True, 'message': 'Chat oculto del panel'})
        
    except Exception as e:
        print(f"❌ Error al borrar conversación: {e}")
        return JsonResponse({'error': str(e)}, status=500)