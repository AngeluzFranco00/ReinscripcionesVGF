set -o errexit
gunicorn Inscripciones.wsgi --bind 0.0.0.0:$PORT