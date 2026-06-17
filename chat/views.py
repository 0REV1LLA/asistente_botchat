import json
from collections import OrderedDict

from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.timezone import localtime
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.hashers import make_password
from django.templatetags.static import static

from .models import Almacen, ChatMessage, Clientes, Productos

SUPERADMIN_CEDULA = 'SuperAdminFarmaLuz'
BOT_NAME = 'Luzy'
BOT_EMOJI = '💁‍♀️'

RAPID_COMMANDS = [
    ('productos', 'Ver la lista de productos'),
    ('precio NOMBRE', 'Consultar el precio de un producto'),
    ('disponible NOMBRE', 'Ver disponibilidad en inventario'),
    ('buscar NOMBRE', 'Buscar datos detallados de un producto'),
    ('ayuda', 'Ver todos los comandos disponibles'),
    ('comandos', 'Alias de ayuda'),
    ('help', 'Alias de ayuda'),
    ('luzy', 'Presentación de la asistente'),
    ('hola', 'Saludo inicial con guía rápida'),
    ('adios', 'Despedida del chat'),
]


def _catalog_unavailable_message():
    return 'El catálogo de productos no está disponible en esta base de datos todavía.'


def _safe_product_list(queryset, limit=None):
    try:
        if limit is not None:
            return list(queryset[:limit])
        return list(queryset)
    except Exception:
        return None

class ChatBotFarmaluz:
    def procesar_mensaje(self, mensaje):
        mensaje = mensaje.lower().strip()

        if mensaje == 'luzy':
            return f"""{BOT_EMOJI} **Hola, soy {BOT_NAME}**, tu asistente virtual de FarmaLuz.

Puedo ayudarte a revisar productos, precios y stock de forma rápida.

**Ejemplo de uso:**
• `buscar diclofenac`
• `precio diclofenac`
• `disponible diclofenac`

Escribe `ayuda` para ver todos los comandos rápidos."""
        
        # Comando: LISTAR PRODUCTOS
        if mensaje == 'productos' or mensaje == 'lista' or mensaje == 'ver productos':
            productos = _safe_product_list(Productos.objects.all(), 15)
            if productos is None:
                return _catalog_unavailable_message()
            if productos:
                respuesta = "📦 **LISTA DE PRODUCTOS:**\n\n"
                for p in productos:
                    precio = f"${p.precio_venta}" if p.precio_venta else "Consultar"
                    respuesta += f"• {p.nombre_producto} - {precio}\n"
                return respuesta
            return "No hay productos registrados."
        
        # Comando: PRECIO [producto]
        if mensaje.startswith('precio '):
            producto_nombre = mensaje.replace('precio ', '').strip()
            if not producto_nombre:
                return "❌ Uso correcto: `precio NOMBRE`\nEjemplo: `precio paracetamol`"
            
            productos = _safe_product_list(Productos.objects.filter(nombre_producto__icontains=producto_nombre), 5)
            if productos is None:
                return _catalog_unavailable_message()
            if productos:
                respuesta = f"💰 **PRECIO DE '{producto_nombre}':**\n\n"
                for p in productos:
                    precio = f"${p.precio_venta}" if p.precio_venta else "No disponible"
                    respuesta += f"• {p.nombre_producto}: {precio}\n"
                return respuesta
            return f"❌ No encontré '{producto_nombre}'. Usa `productos` para ver la lista."
        
        # Comando: DISPONIBLE [producto]
        if mensaje.startswith('disponible '):
            producto_nombre = mensaje.replace('disponible ', '').strip()
            if not producto_nombre:
                return "❌ Uso correcto: `disponible NOMBRE`\nEjemplo: `disponible paracetamol`"
            
            productos = _safe_product_list(Productos.objects.filter(nombre_producto__icontains=producto_nombre), 5)
            if productos is None:
                return _catalog_unavailable_message()
            if productos:
                respuesta = f"📊 **STOCK DE '{producto_nombre}':**\n\n"
                for p in productos:
                    try:
                        stock = Almacen.objects.filter(id_producto=p).first()
                    except Exception:
                        return _catalog_unavailable_message()
                    cantidad = stock.cantidad if stock else 0
                    if cantidad > 10:
                        estado = f"✅ Disponible ({cantidad} unidades)"
                    elif cantidad > 0:
                        estado = f"⚠️ Cantidad baja ({cantidad} unidades)"
                    else:
                        estado = "❌ Agotado"
                    respuesta += f"• {p.nombre_producto}: {estado}\n"
                return respuesta
            return f"❌ No encontré '{producto_nombre}'. Usa `productos` para ver la lista."
        
        # Comando: BUSCAR [producto]
        if mensaje.startswith('buscar '):
            producto_nombre = mensaje.replace('buscar ', '').strip()
            if not producto_nombre:
                return "❌ Uso correcto: `buscar NOMBRE`\nEjemplo: `buscar paracetamol`"
            
            productos = _safe_product_list(Productos.objects.filter(nombre_producto__icontains=producto_nombre), 10)
            if productos is None:
                return _catalog_unavailable_message()
            if productos:
                respuesta = f"🔍 **RESULTADOS DE '{producto_nombre}':**\n\n"
                for p in productos:
                    try:
                        stock = Almacen.objects.filter(id_producto=p).first()
                    except Exception:
                        return _catalog_unavailable_message()
                    cantidad = stock.cantidad if stock else 0
                    precio = f"${p.precio_venta}" if p.precio_venta else "Consultar"
                    respuesta += f"• {p.nombre_producto}\n"
                    respuesta += f"  💰 Precio: {precio}\n"
                    respuesta += f"  📦 Contenido: {p.contenido}\n"
                    respuesta += f"  📝 Descripcion: {p.descripcion}\n"
                    respuesta += f"  📊 Cantidad: {cantidad}\n"
                    respuesta += f"  🏷️ Marca: {p.marca}\n\n"
                return respuesta
            return f"❌ No encontré '{producto_nombre}'. Usa `productos` para ver la lista."
        
        # Comando: AYUDA
        if mensaje == 'ayuda' or mensaje == 'comandos' or mensaje == 'help':
            return self.mostrar_ayuda()
        
        # Comando: SALUDO
        if mensaje in ['hola', 'buenas', 'hola buenas', 'buenos dias', 'buenas tardes', 'buenas noches', 'hi', 'hello']:
            return f"¡Hola! {BOT_EMOJI}\n\n" + self.mostrar_ayuda()
        
        # Comando: DESPEDIDA
        if mensaje in ['adios', 'chao', 'hasta luego', 'nos vemos', 'bye', 'gracias']:
            return f"¡Gracias por consultar Farmaluz! {BOT_EMOJI}\n\nEscribe `hola` si necesitas algo más."
        
        # RESPUESTA SI NO ENTIENDE EL COMANDO
        return self.mostrar_error()
    
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
            f"Escribe `luzy` para conocerme mejor o `hola` para empezar.",
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

# Instancia del chatbot
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
        'sender': message.sender,
        'bubble_class': _message_bubble_class(message),
        'sender_label': _message_sender_label(message),
        'text': message.message,
        'time': _format_message_time(message.created_at),
    }


def _get_chat_history(conversation_key):
    history = [
        _serialize_message(message)
        for message in ChatMessage.objects.filter(conversation_key=conversation_key).order_by('created_at')
    ]

    if not history:
        history.append({
            'sender': ChatMessage.Sender.BOT,
            'bubble_class': 'bot',
            'sender_label': f'{BOT_EMOJI} {BOT_NAME}',
            'text': '¡Hola! Soy Luzy, asistente de Farmaluz. Usa los comandos para aprovechar mejor tu consulta.',
            'time': '',
        })

    return history


def _build_conversations():
    conversations = OrderedDict()
    messages = ChatMessage.objects.select_related('cliente').order_by('conversation_key', 'created_at')

    for message in messages:
        conversation_key = message.conversation_key
        cliente = message.cliente

        cedula = cliente.cedula if cliente else conversation_key
        if cedula == SUPERADMIN_CEDULA or conversation_key == SUPERADMIN_CEDULA:
            continue

        if conversation_key not in conversations:
            conversations[conversation_key] = {
                'conversation_key': conversation_key,
                'client_name': _conversation_label(cliente) if cliente else conversation_key,
                'client_summary': _client_summary(cliente) if cliente else conversation_key,
                'cedula': cedula,
                'initials': _client_initials(cliente) if cliente else conversation_key[:2].upper(),
                'avatar': _client_avatar(cliente) if cliente else '👤',
                'last_time': _format_message_time(message.created_at),
                'last_message': message.message,
                'messages': [],
                'last_sort': message.created_at,
            }

        conversations[conversation_key]['messages'].append({
            'sender': message.sender,
            'bubble_class': _message_bubble_class(message),
            'sender_label': _message_sender_label(message),
            'text': message.message,
            'time': _format_message_time(message.created_at),
        })
        conversations[conversation_key]['last_time'] = _format_message_time(message.created_at)
        conversations[conversation_key]['last_message'] = message.message
        conversations[conversation_key]['last_sort'] = message.created_at

    ordered = sorted(conversations.values(), key=lambda item: item['last_sort'], reverse=True)
    for conversation in ordered:
        conversation.pop('last_sort', None)
    return ordered


def login_view(request):
    if request.method == 'GET':
        if _is_admin_session(request):
            return redirect('chat:admin_dashboard')
        if request.session.get('user_type') == 'client':
            return redirect('chat:bot_chat')
        return render(request, 'login.html', {
            'prefill_cedula': request.session.pop('login_prefill_cedula', ''),
            'registration_success': request.GET.get('registered') == '1',
            'assistant_name': BOT_NAME,
            'assistant_emoji': BOT_EMOJI,
        })

    cedula = request.POST.get('cedula', '').strip()

    if not cedula:
        return render(request, 'login.html', {
            'error_message': 'Debes ingresar tu cédula.',
            'prefill_cedula': '',
            'assistant_name': BOT_NAME,
            'assistant_emoji': BOT_EMOJI,
        }, status=400)

    cliente = Clientes.objects.filter(cedula=cedula).first()

    if not cliente:
        return render(request, 'login.html', {
            'error_message': 'Primero debes registrarte para acceder al sistema.',
            'prefill_cedula': cedula,
            'assistant_name': BOT_NAME,
            'assistant_emoji': BOT_EMOJI,
        }, status=400)

    request.session.flush()
    request.session['user_type'] = 'admin' if cliente.cedula == SUPERADMIN_CEDULA else 'client'
    request.session['cliente_id'] = cliente.cliente_id
    request.session['cliente_cedula'] = cliente.cedula
    request.session['cliente_nombre'] = _client_display_name(cliente)
    request.session['cliente_summary'] = _client_summary(cliente)
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
            'assistant_name': BOT_NAME,
            'assistant_emoji': BOT_EMOJI,
        })

    nombre = request.POST.get('nombre', '').strip()
    apellido = request.POST.get('apellido', '').strip()
    cedula = request.POST.get('cedula', '').strip()
    patologia = request.POST.get('patologia', '').strip()
    genero = request.POST.get('genero', '').strip().lower()
    direccion = request.POST.get('direccion', '').strip()

    required_fields = {
        'nombre': nombre,
        'apellido': apellido,
        'cedula': cedula,
        'patologia': patologia,
        'genero': genero,
        'direccion': direccion,
    }

    if any(not value for value in required_fields.values()):
        return render(request, 'registro.html', {
            'error_message': 'Completa todos los datos para continuar con el registro.',
            'form_values': required_fields,
            'assistant_name': BOT_NAME,
            'assistant_emoji': BOT_EMOJI,
        }, status=400)

    if genero not in {'hombre', 'mujer'}:
        return render(request, 'registro.html', {
            'error_message': 'Selecciona un género válido.',
            'form_values': required_fields,
            'assistant_name': BOT_NAME,
            'assistant_emoji': BOT_EMOJI,
        }, status=400)

    if cedula == SUPERADMIN_CEDULA:
        return render(request, 'registro.html', {
            'error_message': 'Esa cédula está reservada para el superadministrador.',
            'form_values': required_fields,
            'assistant_name': BOT_NAME,
            'assistant_emoji': BOT_EMOJI,
        }, status=400)

    cliente, _ = Clientes.objects.update_or_create(
        cedula=cedula,
        defaults={
            'password': make_password(cedula),
            'nombre': nombre,
            'apellido': apellido,
            'patologia': patologia,
            'genero': genero,
            'direccion': direccion,
            'n_telefono': None,
        },
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
    return render(request, 'chat/index.html', {
        'cliente_nombre': cliente_nombre,
        'cliente_cedula': request.session.get('cliente_cedula', ''),
        'cliente_display_name': _conversation_label(cliente) if cliente else cliente_nombre,
        'assistant_name': BOT_NAME,
        'assistant_emoji': BOT_EMOJI,
        'quick_commands': RAPID_COMMANDS,
        'chat_history': _get_chat_history(conversation_key),
    })


def admin_dashboard_view(request):
    if not _is_admin_session(request):
        return redirect('chat:login')

    conversations = _build_conversations()
    active_conversation = conversations[0] if conversations else None

    return render(request, 'admin_dashboard.html', {
        'conversations': conversations,
        'active_conversation': active_conversation,
        'total_messages': ChatMessage.objects.count(),
        'total_conversations': len(conversations),
        'brand_logo_url': static('chat/img/farmaluz-logo.png'),
        'assistant_name': BOT_NAME,
        'assistant_emoji': BOT_EMOJI,
    })


def logout_view(request):
    request.session.flush()
    return redirect('chat:registro')

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

            if not mensaje.strip():
                return JsonResponse({
                    'error': 'El mensaje no puede estar vacío.',
                    'success': False,
                }, status=400)

            conversation_key = request.session.get('conversation_key') or cliente.cedula
            request.session['conversation_key'] = conversation_key

            ChatMessage.objects.create(
                cliente=cliente,
                conversation_key=conversation_key,
                sender=ChatMessage.Sender.CLIENT,
                message=mensaje.strip(),
            )
            
            # Procesar con el chatbot
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