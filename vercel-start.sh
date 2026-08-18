#!/bin/bash
# Instala dependencias y prepara la app para despliegue en Vercel
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
