from django.urls import path
from . import views

app_name = 'chat'

urlpatterns = [
    # URLs de acceso
    path('registro/', views.registro_view, name='registro'),
    path('acceso/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('terminos/', views.terminos_view, name='terminos'),
    path('manual/sistema/', views.manual_sistema_view, name='manual_sistema'),
    path('manual/usuario/', views.manual_usuario_view, name='manual_usuario'),
    path('sesion/renovar/', views.renew_session_view, name='renew_session'),

     # URLs de recuperación de contraseña
    path('password-reset/', views.password_reset_request, name='password_reset'),
    path('password-reset/done/', views.password_reset_done, name='password_reset_done'),
    path('reset/<signed_token>/', views.password_reset_confirm, name='password_reset_confirm'),
    path('reset/done/', views.password_reset_complete, name='password_reset_complete'),

    # URLs del chatbot
    path('bot/', views.chat_view, name='bot_chat'),
    path('bot/historial/', views.chat_history_view, name='chat_history'),
    path('enviar/', views.enviar_mensaje, name='enviar_mensaje'),

    # URLs del admin
    path('admin-dashboard/', views.admin_dashboard_view, name='admin_dashboard'),
    path('admin-dashboard/historial/', views.admin_conversation_history_view, name='admin_conversation_history'),
    path('admin-dashboard/cambiar-contrasena/', views.superadmin_password_change_view, name='superadmin_password_change'),
    path('bloquear/<int:cliente_id>/', views.toggle_bloqueo_cliente, name='toggle_bloqueo_cliente'),
    path('borrar-conversacion/', views.borrar_conversacion, name='borrar_conversacion'),
]