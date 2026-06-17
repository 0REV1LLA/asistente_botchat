# Asistente Virtual FarmaLuz

Sistema Django para registro de pacientes, acceso, chat con Luzy y panel de superadministración.

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
- `db.sqlite3`, `.env` y `.venv/` quedan fuera del repositorio.
