from django.urls import path
from .views import *


urlpatterns = [
    path('buscar-alumno/<int:numero_control>/', buscar_alumno, name='buscar_alumno'),
    path('talleres-disponibles/', talleres_disponibles, name='talleres_disponibles'),
    path('especialidades-disponibles/', especialidades_disponibles, name='especialidades_disponibles'),
    path('registrar-inscripcion/', registrar_inscripcion, name='registrar_inscripcion'),
    path('pdf/<int:numero_control>/', generar_solicitud_pdf, name='generar_pdf'),
    path('consultar-ficha/<int:numero_control>/', consultar_ficha, name='consultar_ficha'),
    path('consultar-fichas/', consultar_todas_fichas, name='consultar_todas_fichas'),
]