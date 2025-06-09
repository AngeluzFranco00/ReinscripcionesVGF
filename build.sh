#!/bin/bash
set -o errexit

# Instalar dependencias del sistema (sin sudo)
apt-get update && apt-get install -y \
    python3-dev \
    default-libmysqlclient-dev \
    build-essential

# Instalar dependencias de Python
pip install --upgrade pip
pip install -r requirements.txt

# Configuración Django
python manage.py collectstatic --noinput
python manage.py migrate