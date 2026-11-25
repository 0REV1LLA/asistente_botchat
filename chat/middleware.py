from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone

from .constants import SUPERADMIN_CEDULA
from .models import BitacoraSuperadmin


INACTIVITY_WARNING_SECONDS = 8 * 60
INACTIVITY_GRACE_SECONDS = 30
LAST_ACTIVITY_SESSION_KEY = 'last_activity'
SESSION_RENEWAL_PATH = '/chat/sesion/renovar/'


class CustomSessionTimeoutMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        session = request.session
        user_type = session.get('user_type')
        if user_type in {'client', 'admin'}:
            now = timezone.now().timestamp()
            last_activity = session.get(LAST_ACTIVITY_SESSION_KEY, now)
            elapsed = max(0, now - last_activity)

            if elapsed >= INACTIVITY_WARNING_SECONDS + INACTIVITY_GRACE_SECONDS:
                if user_type == 'admin' and session.get('cliente_cedula') == SUPERADMIN_CEDULA:
                    BitacoraSuperadmin.objects.create(
                        superadmin_cedula=SUPERADMIN_CEDULA,
                        action_type=BitacoraSuperadmin.Action.LOGOUT,
                        detail='Cierre de sesión del superadministrador por inactividad.',
                    )
                session.flush()
                return redirect(f"{reverse('chat:login')}?expired=1")

            if elapsed < INACTIVITY_WARNING_SECONDS or request.path == SESSION_RENEWAL_PATH:
                session[LAST_ACTIVITY_SESSION_KEY] = now

        return self.get_response(request)
