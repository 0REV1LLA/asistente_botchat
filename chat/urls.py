from django.urls import path
from . import views

app_name = 'chat'

urlpatterns = [
    path('registro/', views.registro_view, name='registro'),
    path('acceso/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

     # URLs de recuperación de contraseña
    path('password-reset/', views.password_reset_request, name='password_reset'),
    path('password-reset/done/', views.password_reset_done, name='password_reset_done'),
    path('reset/<signed_token>/', views.password_reset_confirm, name='password_reset_confirm'),
    path('reset/done/', views.password_reset_complete, name='password_reset_complete'),

    path('bot/', views.chat_view, name='bot_chat'),
    path('admin-dashboard/', views.admin_dashboard_view, name='admin_dashboard'),
    path('enviar/', views.enviar_mensaje, name='enviar_mensaje'),
    path('bloquear/<int:cliente_id>/', views.toggle_bloqueo_cliente, name='toggle_bloqueo_cliente'),
    path('borrar-conversacion/', views.borrar_conversacion, name='borrar_conversacion'),
]