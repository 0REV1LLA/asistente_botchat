from django.urls import path
from . import views

app_name = 'chat'

urlpatterns = [
    path('registro/', views.registro_view, name='registro'),
    path('acceso/', views.login_view, name='login'),
    path('bot/', views.chat_view, name='bot_chat'),
    path('admin-dashboard/', views.admin_dashboard_view, name='admin_dashboard'),
    path('logout/', views.logout_view, name='logout'),
    path('enviar/', views.enviar_mensaje, name='enviar_mensaje'),
    path('bloquear/<int:cliente_id>/', views.toggle_bloqueo_cliente, name='toggle_bloqueo_cliente'),
]