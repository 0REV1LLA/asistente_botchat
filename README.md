# Asistente Virtual FarmaLuz

Sistema Django para registro de pacientes, acceso, chat con Lucy y panel de superadministración.

## Requisitos

- Python 3.11
- Un entorno virtual
- Para el modo por defecto, SQLite
- Para usar la base original, MySQL y `mysqlclient`

## Instalación rápida

1. Crear y activar el entorno virtual.
2. Instalar dependencias:

```bash
pip install -r requirements.txt
```

3. Copiar el archivo de entorno:

```bash
copy .env.example .env
```

4. Ejecutar migraciones:

```bash
python manage.py migrate
```

5. Levantar el servidor:

```bash
python manage.py runserver
```

Abrir `http://127.0.0.1:8000/`.
La ruta raíz redirige al acceso.

## Cuentas de prueba

La migración inicial crea cuentas de demostración:

- Superadmin: `SuperAdminFarmaLuz`
- Cliente demo: `12345678`

## Base de datos

Por defecto el proyecto usa SQLite para que puedas probarlo en otra PC sin depender de MySQL.

Si quieres usar MySQL, configura estas variables en `.env`:

```env
DB_ENGINE=django.db.backends.mysql
DB_NAME=inventario_farmaluz
DB_USER=root
DB_PASSWORD=
DB_HOST=localhost
DB_PORT=3306
```

## Notas

- El panel de superadmin muestra los chats por conversación.
- Si no existen tablas de catálogo de productos en la base activa, el bot responde sin romper la aplicación.
- `db.sqlite3` y `.env` quedan fuera del repositorio.
- Usa tu propio entorno de Python; el proyecto no depende de una carpeta `.venv` versionada aquí.

## Recuperación de contraseña en Vercel

En Vercel, agrega estas variables en **Settings > Environment Variables** y vuelve a desplegar:

```env
SECRET_KEY=una-clave-larga-y-aleatoria
DEBUG=False
PUBLIC_URL=https://asistente-botchat.vercel.app
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_USE_SSL=False
EMAIL_HOST_USER=tu-cuenta@gmail.com
EMAIL_HOST_PASSWORD=tu-contraseña-de-aplicación-de-16-caracteres
DEFAULT_FROM_EMAIL=tu-cuenta@gmail.com
```

Para Gmail, `EMAIL_HOST_PASSWORD` debe ser una contraseña de aplicación, no la contraseña normal de la cuenta. No guardes estas variables en Git. Si la contraseña SMTP que estaba escrita en el código fue real, revócala y genera una nueva antes de configurar Vercel.
