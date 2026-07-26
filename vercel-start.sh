#!/bin/bash
pip install -r requirements-vercel.txt
python manage.py migrate
python manage.py collectstatic --noinput
