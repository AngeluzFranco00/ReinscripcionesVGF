#!/bin/bash
set -o errexit

# Para sistemas basados en Debian (Render usa Ubuntu)
sudo apt-get update
sudo apt-get install -y python3-dev default-libmysqlclient-dev build-essential

pip install -r requirements.txt
python manage.py collectstatic --noinput
python manage.py migrate