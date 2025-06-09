set -o errexit
gunicorn Inscripciones.wsgi:application --bind 0.0.0.0:$PORT