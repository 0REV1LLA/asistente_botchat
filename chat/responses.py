from simple_chatbot.responses import GenericRandomResponse

class SaludoResponse(GenericRandomResponse):
    choices = (
        "¡Hola! Soy el asistente de Farmaluz. ¿En qué puedo ayudarte?",
        "¡Bienvenido a Farmaluz! ¿Qué producto necesitas consultar?",
        "Hola, ¿cómo puedo ayudarte con tus medicamentos hoy?"
    )

class ProductoResponse(GenericRandomResponse):
    choices = (
        "Claro, déjame buscar información sobre ese producto...",
        "Un momento mientras consulto nuestro catálogo...",
        "¡Claro! Tengo información sobre esos productos."
    )

class StockResponse(GenericRandomResponse):
    choices = (
        "Revisando disponibilidad en nuestro almacén...",
        "Veamos si tenemos stock disponible...",
        "Consultando inventario actual..."
    )

class PrecioResponse(GenericRandomResponse):
    choices = (
        "Déjame verificar el precio actual...",
        "Claro, te confirmo el precio...",
        "El precio de ese producto es:"
    )

class DespedidaResponse(GenericRandomResponse):
    choices = (
        "¡Gracias por visitar Farmaluz! Vuelve pronto.",
        "Que tengas un excelente día. ¡Saludos!",
        "Hasta luego, estamos para servirte."
    )

class NoEntiendoResponse(GenericRandomResponse):
    choices = (
        "Lo siento, no entendí bien. ¿Podrías repetirlo?",
        "No estoy seguro de entender. ¿Puedes ser más específico?",
        "Disculpa, no reconozco esa consulta. ¿Preguntas por algún producto en especial?"
    )