import json
import secrets
import traceback
import binascii
import re
import unicodedata
from collections import OrderedDict
from datetime import timedelta
from difflib import SequenceMatcher

from django.conf import settings
from django.core import signing
from django.core.mail import EmailMultiAlternatives
from django.db.models import F, Prefetch, Q, Window
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
    latest_eligible_birth_date,
)
from .models import (
    Almacen,
    BitacoraSuperadmin,
    ChatMessage,
    Clientes,
    Productos,
    ChatsOcultos,
)

#Configuraciones generales
BOT_NAME = 'Lucy'
BOT_EMOJI = '💁‍♀️'
PASSWORD_RESET_SESSION_KEY = 'password_reset_request'
PASSWORD_RESET_MAX_AGE = 60 * 60 * 24  # 24 horas

RAPID_COMMANDS = [
    ('productos', 'Ver y filtrar productos por categoría, compuesto u otros atributos'),
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


def _record_superadmin_action(action_type, detail):
    BitacoraSuperadmin.objects.create(
        superadmin_cedula=SUPERADMIN_CEDULA,
        action_type=action_type,
        detail=detail,
    )


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
PRODUCT_LIST_LIMIT = 15
SUGGESTION_SCAN_LIMIT = 500
PRODUCT_QUERY_STOP_WORDS = {
    'a', 'al', 'algun', 'alguna', 'algunos', 'algunas', 'como', 'con', 'cual',
    'de', 'del', 'el', 'ella', 'en', 'es', 'esta', 'este', 'hay', 'la', 'las',
    'los', 'me', 'mi', 'necesito', 'para', 'por', 'que', 'quiero', 'un', 'una',
    'uno', 'unos', 'unas', 'favor', 'producto', 'productos', 'medicamento',
    'medicamentos', 'farmaco', 'farmacos', 'buscar', 'busca', 'precio',
    'cuesta', 'cuanto', 'vale', 'disponible', 'disponibilidad', 'stock',
    'informacion', 'info', 'detalle', 'detalles', 'sobre', 'tienen', 'tiene',
    'dime', 'dame', 'muestrame', 'mostrar', 'ver', 'lista', 'listar', 'catalogo',
    'quisiera', 'consultar', 'consulta', 'consultame', 'podrias', 'decirme',
    'decir', 'deseo', 'presenta', 'presentacion', 'receta', 'recetas', 'recipe',
    'recipes', 'prescripcion',
    'prescripciones', 'compuesto', 'compuestos', 'categoria', 'categorias',
    'marca', 'contenido', 'existencia', 'existencias', 'agotado', 'agotados',
    'saber', 'si', 'gustaria', 'hablar', 'hablame', 'informame', 'recomiendame',
    'recomendar', 'tienes', 'existe', 'existen', 'podria', 'puedo', 'indica',
    'indicame', 'venden', 'vendan', 'ensename', 'puedes',
}


def _normalize_text(value):
    normalized = unicodedata.normalize('NFKD', str(value or '').casefold())
    return ''.join(character for character in normalized if not unicodedata.combining(character))


def _product_tokens(value):
    return [
        token for token in re.findall(r'[a-z0-9]+', _normalize_text(value))
        if len(token) >= 2 and token not in PRODUCT_QUERY_STOP_WORDS
    ]


def _accent_insensitive_regex(value):
    accent_groups = {
        'a': '[aáàäâã]',
        'e': '[eéèëê]',
        'i': '[iíìïî]',
        'o': '[oóòöôõ]',
        'u': '[uúùüû]',
        'n': '[nñ]',
    }
    return ''.join(
        accent_groups.get(character, re.escape(character))
        for character in _normalize_text(value)
    )


def _text_contains(field_name, value):
    return (
        Q(**{f'{field_name}__icontains': value})
        | Q(**{f'{field_name}__iregex': _accent_insensitive_regex(value)})
    )


def _product_queryset(with_stock=False):
    queryset = Productos.objects.select_related(
        'categoria',
        'sub_categorias_nivel_1',
        'sub_categorias_nivel_2',
    )
    if with_stock:
        queryset = queryset.prefetch_related(Prefetch(
            'almacen',
            queryset=Almacen.objects.order_by('pk'),
            to_attr='_almacen_records',
        ))
    return queryset


def _product_text_filter(queryset, query):
    tokens = _product_tokens(query)
    if not tokens:
        return queryset.none()

    for token in tokens:
        token_filter = _text_contains('nombre_producto', token)
        token_filter |= _text_contains('compuesto', token)
        token_filter |= _text_contains('categoria__nombre_categoria', token)
        token_filter |= _text_contains('sub_categorias_nivel_1__nombre_sub_categoria', token)
        token_filter |= _text_contains('sub_categorias_nivel_2__nombre_sub_categoria_nivel_2', token)
        token_filter |= _text_contains('marca', token)
        token_filter |= _text_contains('contenido', token)
        token_filter |= _text_contains('descripcion', token)
        queryset = queryset.filter(token_filter)
    return queryset.distinct()


def _product_stock_quantity(product):
    stock_records = getattr(product, '_almacen_records', ())
    return (stock_records[0].cantidad or 0) if stock_records else 0


def _extract_product_query(message, intent):
    query = _normalize_text(message)
    command_patterns = {
        'price': r'^(?:(?:por favor|me puedes|puedes)\s+)*(?:cuanto cuesta|cuanto vale|cual es el precio de|precio(?:s)?(?: de)?|costo(?: de)?|vale)\s*',
        'availability': r'^(?:(?:por favor|me puedes|puedes)\s+)*(?:esta disponible(?: el| la)?|disponibilidad(?: de)?|disponible(?: el| la)?|hay(?: en existencia)?|tienen|tiene|stock(?: de)?|cuanto queda de)\s*',
        'detail': r'^(?:(?:por favor|me puedes|puedes|quiero)\s+)*(?:buscar|busca|informacion(?: de| sobre)?|info(?: de| sobre)?|detalle(?:s)?(?: de)?|saber(?: sobre| de)?|datos de)\s*',
        'list': r'^(?:(?:por favor|quiero|puedes|me puedes)\s+)*(?:muestrame|mostrar|ver|lista|listar|dame|catalogo(?: de)?|que productos hay|que medicamentos hay)\s*',
    }
    query = re.sub(command_patterns[intent], '', query).strip()
    query = re.sub(r'\b(?:productos?|medicamentos?|medicinas?|farmacos?)\b', ' ', query)
    filler_pattern = r'\b(?:' + '|'.join(
        re.escape(word) for word in sorted(PRODUCT_QUERY_STOP_WORDS, key=len, reverse=True)
    ) + r')\b'
    query = re.sub(filler_pattern, ' ', query)
    return re.sub(r'\s+', ' ', query).strip(' ?!.,;:')


def _parse_product_list_filters(message):
    query = _normalize_text(message)
    query = re.sub(
        r'^(?:(?:por favor|quiero|puedes|me puedes)\s+)*(?:muestrame|mostrar|ver|lista|listar|dame|catalogo(?: de)?)\s*',
        '',
        query,
    )
    query = re.sub(r'\b(?:productos?|medicamentos?|medicinas?|farmacos?)\b', ' ', query)
    filters = {}
    labels = re.compile(
        r'\b(categoria|tipo|compuesto|principio activo|presentacion|contenido|marca|nombre)\s+(?:de\s+)?'
    )
    matches = list(labels.finditer(query))
    for index, match in enumerate(matches):
        next_start = matches[index + 1].start() if index + 1 < len(matches) else len(query)
        value = query[match.end():next_start].strip(' ,;:')
        value = re.split(
            r'\b(?:con receta|con recipe|requiere receta|requiere recipe|requiere prescripcion|'
            r'sin receta|sin recipe|sin prescripcion|no requiere receta|no requiere recipe|'
            r'no requiere prescripcion|disponibles?|en existencia|agotados?|sin existencia|con stock)\b',
            value,
            maxsplit=1,
        )[0]
        value = re.sub(r'\b(?:y|del|de|el|la|los|las)\b$', '', value).strip()
        if not value:
            continue
        key = match.group(1)
        if key in {'categoria', 'tipo'}:
            filters['category'] = value
        elif key in {'compuesto', 'principio activo'}:
            filters['compound'] = value
        elif key in {'presentacion', 'contenido'}:
            filters['presentation'] = value
        else:
            filters[key] = value

    residual = _normalize_text(message)
    residual = re.sub(
        r'^(?:(?:por favor|quiero|puedes|me puedes)\s+)*(?:muestrame|mostrar|ver|lista|listar|dame|catalogo(?: de)?)\s*',
        '',
        residual,
    )
    residual = re.sub(r'\b(?:productos?|medicamentos?|medicinas?|farmacos?)\b', ' ', residual)
    residual = labels.sub(' ', residual)
    for value in filters.values():
        residual = residual.replace(value, ' ')
    residual = re.sub(
        r'\b(?:con receta|requiere receta|requiere recipe|requiere prescripcion|sin receta|sin recipe|sin prescripcion|no requiere receta|no requiere recipe|no requiere prescripcion|disponibles?|en existencia|agotados?|sin existencia|con stock)\b',
        ' ',
        residual,
    )
    residual = re.sub(r'\b(?:y|de|del|el|la|los|las|con|para)\b', ' ', residual)
    residual_tokens = _product_tokens(residual)
    if residual_tokens:
        filters['text'] = ' '.join(residual_tokens)

    if re.search(r'\b(?:sin receta|sin recipe|no requiere receta|no requiere recipe|sin prescripcion|no requiere prescripcion)\b', _normalize_text(message)):
        filters['prescription'] = False
    elif re.search(r'\b(?:con receta|con recipe|requiere receta|requiere recipe|requiere prescripcion)\b', _normalize_text(message)):
        filters['prescription'] = True
    if re.search(r'\b(?:agotado|agotados|sin existencia|sin stock)\b', _normalize_text(message)):
        filters['availability'] = False
    elif re.search(r'\b(?:disponible|disponibles|en existencia|con stock|stock)\b', _normalize_text(message)):
        filters['availability'] = True
    return filters


def _apply_product_list_filters(queryset, filters):
    if 'category' in filters:
        queryset = queryset.filter(_text_contains('categoria__nombre_categoria', filters['category']))
    if 'compound' in filters:
        queryset = queryset.filter(_text_contains('compuesto', filters['compound']))
    if 'presentation' in filters:
        queryset = queryset.filter(_text_contains('contenido', filters['presentation']))
    if 'brand' in filters:
        queryset = queryset.filter(_text_contains('marca', filters['brand']))
    if 'nombre' in filters:
        queryset = queryset.filter(_text_contains('nombre_producto', filters['nombre']))
    if 'text' in filters:
        queryset = _product_text_filter(queryset, filters['text'])
    if 'prescription' in filters:
        queryset = queryset.filter(requiere_recipe=filters['prescription'])
    if filters.get('availability') is True:
        queryset = queryset.filter(almacen__cantidad__gt=0)
    elif filters.get('availability') is False:
        queryset = queryset.exclude(almacen__cantidad__gt=0)
    return queryset.distinct()


def _suggest_available_products(query, limit=3):
    tokens = _product_tokens(query)
    if not tokens:
        return []

    queryset = _product_queryset(with_stock=True)
    candidates = _product_text_filter(queryset, query).order_by('nombre_producto', 'id_producto')[:100]
    products = list(candidates)
    available = [
        product for product in products
        if _product_stock_quantity(product) > 0
    ]
    if not available:
        scored_ids = []
        rows = Productos.objects.order_by('nombre_producto', 'id_producto').values(
            'id_producto',
            'nombre_producto',
            'compuesto',
            'categoria__nombre_categoria',
        )[:SUGGESTION_SCAN_LIMIT]
        normalized_query = ' '.join(tokens)
        for row in rows:
            searchable = ' '.join(filter(None, (
                row['nombre_producto'],
                row['compuesto'],
                row['categoria__nombre_categoria'],
            )))
            normalized_candidate = _normalize_text(searchable)
            score = max(
                SequenceMatcher(None, normalized_query, normalized_candidate).ratio(),
                *(SequenceMatcher(None, token, normalized_candidate).ratio() for token in tokens),
            )
            if score >= 0.32:
                scored_ids.append((score, row['id_producto']))
        selected_ids = [
            product_id for _, product_id in sorted(scored_ids, reverse=True)[:30]
        ]
        products = list(
            _product_queryset(with_stock=True)
            .filter(id_producto__in=selected_ids)
        )
        score_by_id = dict(scored_ids)
        products.sort(key=lambda product: score_by_id.get(product.pk, 0), reverse=True)
        available = [
            product for product in products
            if _product_stock_quantity(product) > 0
        ]
    return available[:limit]


def _not_found_response(query):
    suggestions = _suggest_available_products(query)
    if not suggestions:
        return (
            f"No encontré '{query}'. No hay alternativas similares disponibles en inventario; "
            "puedes filtrar el catálogo por categoría o compuesto."
        )
    lines = [f"No encontré '{query}'. Estas alternativas similares sí están disponibles:"]
    lines.extend(_format_suggestion_lines(suggestions))
    return '\n'.join(lines)


def _format_suggestion_lines(products):
    return [
        f"• {product.nombre_producto} — {product.compuesto or 'Compuesto no especificado'} "
        f"({_product_stock_quantity(product)} unidades)"
        for product in products
    ]


class ChatBotFarmaluz:
    def _list_products(self, message):
        filters = _parse_product_list_filters(message)
        queryset = _apply_product_list_filters(_product_queryset(), filters)
        try:
            total = queryset.count()
            products = _safe_product_list(
                queryset.order_by('nombre_producto', 'id_producto'),
                PRODUCT_LIST_LIMIT,
            )
        except Exception as error:
            print(f'Error consultando el catálogo: {error}')
            return _catalog_unavailable_message('Error al consultar la tabla de productos')
        if products is None:
            return _catalog_unavailable_message('Error al consultar la tabla de productos')
        if not products:
            filter_query = ' '.join(
                value for value in filters.values() if isinstance(value, str)
            )
            if filter_query:
                return _not_found_response(filter_query)
            if not filters:
                return 'No hay productos registrados en la base de datos.'
            return 'No hay productos que coincidan con los filtros seleccionados.'

        response = '📦 **LISTA DE PRODUCTOS:**\n\n'
        for product in products:
            price = f'${product.precio_venta}' if product.precio_venta else 'Consultar'
            category = product.categoria.nombre_categoria if product.categoria else 'Sin categoría'
            response += (
                f'• {product.nombre_producto or "Producto"} — {price}; '
                f'Categoría: {category}; Compuesto: {product.compuesto or "No especificado"}; '
                f'Requiere récipe: {"Sí" if product.requiere_recipe else "No"}\n'
            )
        if total > len(products):
            response += f'\nMostrando {len(products)} de {total} resultados. Refina con nombre, categoría, compuesto, marca, presentación, receta o disponibilidad.'
        if not filters and total > len(products):
            response += '\nEjemplos: `productos categoria analgesicos`, `productos compuesto ibuprofeno`, `productos disponibles`.'
        return response

    def _price(self, query):
        products = _safe_product_list(
            _product_text_filter(_product_queryset(), query).order_by('nombre_producto', 'id_producto'),
            5,
        )
        if products is None:
            return _catalog_unavailable_message('Error en filtro de precio')
        if not products:
            return _not_found_response(query)
        lines = [f"💰 **PRECIO DE '{query}':**", '']
        for product in products:
            price = f'${product.precio_venta}' if product.precio_venta else 'No disponible'
            lines.append(f'• {product.nombre_producto}: {price}')
        return '\n'.join(lines)

    def _availability(self, query):
        products = _safe_product_list(
            _product_text_filter(_product_queryset(), query)
            .order_by('nombre_producto', 'id_producto'),
            5,
            with_stock=True,
        )
        if products is None:
            return _catalog_unavailable_message('Error en filtro de disponibilidad')
        if not products:
            return _not_found_response(query)
        lines = [f"📊 **DISPONIBILIDAD DE '{query}':**", '']
        for product in products:
            quantity = _product_stock_quantity(product)
            if quantity > 10:
                status = f'✅ Disponible ({quantity} unidades)'
            elif quantity > 0:
                status = f'⚠️ Cantidad baja ({quantity} unidades)'
            else:
                status = '❌ Agotado'
            lines.append(f'• {product.nombre_producto}: {status}')
            if product.requiere_recipe:
                lines.append('  ⚠️ Requiere récipe/prescripción médica; tenlo a la mano.')
        if not any(_product_stock_quantity(product) > 0 for product in products):
            suggestions = _suggest_available_products(query)
            if suggestions:
                lines.extend(['', 'Alternativas similares disponibles:'])
                lines.extend(_format_suggestion_lines(suggestions))
        return '\n'.join(lines)

    def _details(self, query):
        products = _safe_product_list(
            _product_text_filter(_product_queryset(), query)
            .order_by('nombre_producto', 'id_producto'),
            10,
            with_stock=True,
        )
        if products is None:
            return _catalog_unavailable_message('Error en búsqueda detallada')
        if not products:
            return _not_found_response(query)

        lines = [f"🔍 **RESULTADOS DE '{query}':**", '']
        for product in products:
            price = f'${product.precio_venta}' if product.precio_venta else 'Consultar'
            category = product.categoria.nombre_categoria if product.categoria else 'No especificada'
            lines.extend([
                f'• {product.nombre_producto or "Producto"}',
                f'  💰 Precio: {price}',
                f'  📦 Presentación: {product.contenido or "No especificada"}',
                f'  📝 Descripción: {product.descripcion or "Sin descripción"}',
                f'  🧪 Compuesto: {product.compuesto or "No especificado"}',
                f'  🗂️ Categoría: {category}',
                f'  📊 Cantidad en almacén: {_product_stock_quantity(product)}',
                f'  🏷️ Marca: {product.marca or "Genérica"}',
                f'  🩺 Requiere récipe/prescripción: {"Sí" if product.requiere_recipe else "No"}',
                '',
            ])
        return '\n'.join(lines)

    def procesar_mensaje(self, mensaje):
        normalized = _normalize_text(mensaje).strip()
        if normalized == 'lucy':
            return f"""{BOT_EMOJI} **Hola, soy {BOT_NAME}**, tu asistente virtual de FarmaLuz.

Puedo ayudarte a revisar productos, precios y disponibilidad.

**Ejemplo de uso:**
• `buscar diclofenac`
• `precio diclofenac`
• `disponible diclofenac`
• `productos categoria analgesicos`

Escribe `ayuda` para ver todos los comandos rápidos."""

        if re.search(r'\b(?:ayuda|comandos|help)\b', normalized):
            return self.mostrar_ayuda()
        if re.search(r'\b(?:hola|buenas|hi|hello)\b', normalized):
            return f"¡Hola! {BOT_EMOJI}\n\n" + self.mostrar_ayuda()
        if re.search(r'\b(?:adios|chao|hasta luego|nos vemos|bye|gracias)\b', normalized):
            return f"¡Gracias por consultar Farmaluz! {BOT_EMOJI}\n\nEscribe `hola` si necesitas algo más."

        has_product_word = bool(re.search(r'\b(?:producto|productos|medicamento|medicamentos|medicina|medicinas|farmaco|farmacos)\b', normalized))
        list_cue = bool(re.search(r'\b(?:lista|listar|catalogo|mostrar|muestrame|ensename|ver|dame)\b', normalized))
        list_filter_cue = bool(re.search(
            r'\b(?:categoria|tipo|compuesto|principio activo|presentacion|contenido|marca|nombre|receta|recipe|prescripcion|disponible|disponibles|stock|existencia|agotados|agotado)\b',
            normalized,
        ))
        if has_product_word and (
            list_cue
            or list_filter_cue
            or normalized in {'producto', 'productos', 'medicamento', 'medicamentos', 'medicina', 'medicinas', 'farmaco', 'farmacos'}
            or re.search(r'\b(?:que|cuales)\s+(?:productos|medicamentos|medicinas)\s+(?:hay|tienen|tienes)\b', normalized)
        ):
            return self._list_products(mensaje)
        if normalized in {'lista', 'listar', 'catalogo', 'catalogar', 'hay productos', 'hay medicamentos', 'hay medicinas'}:
            return self._list_products(mensaje)

        if re.search(r'\b(?:precio|precios|cuesta|cuestan|costo|coste|vale|valen)\b', normalized):
            query = _extract_product_query(mensaje, 'price')
            return self._price(query) if query else 'Indica el nombre del producto. Ejemplo: `precio paracetamol`.'

        if re.search(r'\b(?:disponible|disponibilidad|stock|existencia|hay|tienen|tiene|tienes|existe|existen)\b', normalized):
            query = _extract_product_query(mensaje, 'availability')
            return self._availability(query) if query else 'Indica el producto que deseas consultar. Ejemplo: `disponible paracetamol`.'

        if re.search(r'\b(?:buscar|busca|informacion|info|detalle|detalles|saber|consultar|consulta|informame|recomiendame)\b', normalized):
            query = _extract_product_query(mensaje, 'detail')
            return self._details(query) if query else 'Indica el nombre del producto. Ejemplo: `buscar paracetamol`.'

        if has_product_word:
            query = _extract_product_query(mensaje, 'detail')
            return self._details(query) if query else 'Indica el nombre del producto. Ejemplo: `buscar paracetamol`.'

        return self.mostrar_error()

    def mostrar_ayuda(self):
        lines = [f"{BOT_EMOJI} **COMANDOS RÁPIDOS:**", ""]
        for command, description in RAPID_COMMANDS:
            lines.append(f"• `{command}` - {description}")

        lines.extend([
            "",
            "**FILTROS DEL CATÁLOGO:**",
            "• `productos categoria analgesicos`",
            "• `productos compuesto ibuprofeno`",
            "• `productos disponibles` o `productos con receta`",
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

    if cliente.cedula == SUPERADMIN_CEDULA:
        _record_superadmin_action(
            BitacoraSuperadmin.Action.LOGIN,
            'Inicio de sesión del superadministrador.',
        )

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
            'latest_eligible_birth_date': latest_eligible_birth_date(),
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
            'latest_eligible_birth_date': latest_eligible_birth_date(),
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
    _record_superadmin_action(
        BitacoraSuperadmin.Action.PASSWORD_CHANGE,
        'El superadministrador actualizó su contraseña.',
    )
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
    if _is_admin_session(request):
        _record_superadmin_action(
            BitacoraSuperadmin.Action.LOGOUT,
            'Cierre de sesión del superadministrador.',
        )
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
        action_type = (
            BitacoraSuperadmin.Action.BLOCK
            if cliente.bloqueado
            else BitacoraSuperadmin.Action.UNBLOCK
        )
        _record_superadmin_action(
            action_type,
            f'Usuario afectado: {cliente.cedula} ({_client_display_name(cliente)}).',
        )

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

            client_message = ChatMessage.objects.create(
                cliente=cliente,
                conversation_key=conversation_key,
                sender=ChatMessage.Sender.CLIENT,
                message=mensaje.strip(),
            )
            
            respuesta = bot.procesar_mensaje(mensaje)
            bot_message = ChatMessage.objects.create(
                cliente=cliente,
                conversation_key=conversation_key,
                sender=ChatMessage.Sender.BOT,
                message=respuesta,
            )
            
            return JsonResponse({
                'respuesta': respuesta,
                'client_time': _format_message_time(client_message.created_at),
                'response_time': _format_message_time(bot_message.created_at),
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
        print(f"Token recibido: {signed_token[:50]}...")

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
        
        print(f"UIDB64 decodificado: {uidb64}")
        print(f"Token decodificado: {token[:20]}...")
        
        # Obtener cliente
        cliente = _cliente_from_uidb64(uidb64)
        if not cliente:
            print(f"Cliente no encontrado para UIDB64: {uidb64}")
            return render(request, 'chat/password_reset_confirm.html', {
                'error_message': 'Cliente no encontrado. El enlace es inválido.'
            })
        
        print(f"Cliente encontrado: {cliente.cedula} - {cliente.correo}")
        
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
            
            # Hashear la contraseña antes de guardar
            from django.contrib.auth.hashers import make_password
            cliente.password = make_password(new_password)
            cliente.save()
            
            print(f"Contraseña actualizada para: {cliente.correo}")
            
            # Limpiar sesión si existe
            _clear_password_reset_state(request)
            messages.success(request, 'Tu contraseña se actualizó correctamente.')
            return redirect('chat:login')
        
        return render(request, 'chat/password_reset_confirm.html', {
            'cliente': cliente,
            'nombre_completo': _full_name(cliente) or 'Cliente'
        })
        
    except signing.BadSignature as e:
        print(f"BadSignature error: {e}")
        error_msg = str(e)
        if 'No ":" found in value' in error_msg:
            print("Token ya usado - Redirigiendo a página de éxito")
            return redirect('chat:password_reset_complete')
        return render(request, 'chat/password_reset_confirm.html', {
            'error_message': 'El enlace es inválido o ha sido manipulado. Solicita un nuevo enlace.'
        })
    except signing.SignatureExpired as e:
        print(f"SignatureExpired error: {e}")
        return render(request, 'chat/password_reset_confirm.html', {
            'error_message': 'El enlace ha expirado. Solicita un nuevo enlace de recuperación.'
        })
    except Exception as e:
        print(f"Error general en password_reset_confirm: {e}")
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
        _, created = ChatsOcultos.objects.get_or_create(
            superadmin_cedula=SUPERADMIN_CEDULA,
            conversation_key=conversation_key
        )
        if created:
            _record_superadmin_action(
                BitacoraSuperadmin.Action.HIDE_CHAT,
                f'Conversación ocultada del panel: {conversation_key}.',
            )
        
        return JsonResponse({'success': True, 'message': 'Chat oculto del panel'})
        
    except Exception as e:
        print(f"❌ Error al borrar conversación: {e}")
        return JsonResponse({'error': str(e)}, status=500)