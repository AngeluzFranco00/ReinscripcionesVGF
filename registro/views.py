from django.db import transaction
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.core.exceptions import ValidationError
import json
from .models import *
from io import BytesIO

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Table, TableStyle, 
    Spacer, Image
)
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from django.views.decorators.http import require_http_methods
        

def buscar_alumno(request, numero_control):
    if request.method == 'GET':
        try:
            alumno = Alumno.objects.get(numero_control=numero_control)
            data = {
                'numero_control': alumno.numero_control,
                'nombres': alumno.nombres,
                'apellido_paterno': alumno.apellido_paterno,
                'apellido_materno': alumno.apellido_materno,
                'grupo_anterior': alumno.grupo_anterior,
                'semestre_anterior': alumno.semestre_anterior,
                'puede_elegir_especialidad': alumno.puede_elegir_especialidad,
                'tiene_ficha': FichaInscripcion.objects.filter(alumno=alumno).exists()
            }
            
            if data['tiene_ficha']:
                ficha = FichaInscripcion.objects.get(alumno=alumno)
                data['ficha_existente'] = {
                    'id_inscripcion': ficha.id_inscripcion,
                    'grupo_inscripcion': ficha.grupo_inscripcion,
                    'semestre_inscripcion': ficha.semestre_inscripcion,
                    'especialidad': ficha.especialidad.nombre if ficha.especialidad else None,
                    'taller': ficha.taller.nombre if ficha.taller else None,
                    'fecha_solicitud': ficha.fecha_solicitud
                }
            
            return JsonResponse(data, status=200)
        except Alumno.DoesNotExist:
            return JsonResponse({'error': 'Alumno no encontrado'}, status=404)
    else:
        return JsonResponse({'error': 'Método no permitido'}, status=405)


def talleres_disponibles(request):
    if request.method == 'GET':
        talleres = Taller.objects.filter(cantidad__lt=30).values('id_taller', 'nombre', 'cantidad')
        talleres_list = []
        for taller in talleres:
            taller_obj = Taller.objects.get(id_taller=taller['id_taller'])
            taller['fichas_disponibles'] = taller_obj.fichas_disponibles()
            talleres_list.append(taller)
        return JsonResponse(talleres_list, safe=False)


def especialidades_disponibles(request):
    if request.method == 'GET':
        especialidades = Especialidad.objects.filter(cantidad__lt=40).values(
            'id_especialidad', 'nombre', 'codigo', 'cantidad'
        )
        especialidades_list = []
        for esp in especialidades:
            esp_obj = Especialidad.objects.get(id_especialidad=esp['id_especialidad'])
            esp['fichas_disponibles'] = esp_obj.fichas_disponibles()
            especialidades_list.append(esp)
        return JsonResponse(especialidades_list, safe=False)

@csrf_exempt
@transaction.atomic
def registrar_inscripcion(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            
            numero_control = data.get('numero_control')
            if not numero_control:
                return JsonResponse({'success': False, 'error': 'Número de control es obligatorio'}, status=400)
                
            try:
                alumno = Alumno.objects.get(numero_control=numero_control)
            except Alumno.DoesNotExist:
                return JsonResponse({'success': False, 'error': 'Alumno no encontrado'}, status=404)

            semestre_nuevo = alumno.semestre_anterior + 1
            if FichaInscripcion.objects.filter(alumno=alumno, semestre_inscripcion=semestre_nuevo).exists():
                return JsonResponse({
                    'success': False, 
                    'error': f'El alumno ya tiene una ficha registrada para el semestre {semestre_nuevo}'
                }, status=409)

            especialidad = None
            if alumno.puede_elegir_especialidad:
                especialidad_id = data.get('especialidad_id')
                if not especialidad_id:
                    return JsonResponse({
                        'success': False, 
                        'error': 'Los alumnos de 2do semestre deben elegir una especialidad'
                    }, status=400)
                
                try:
                    especialidad = Especialidad.objects.get(pk=especialidad_id)
                    if especialidad.fichas_disponibles() <= 0:
                        return JsonResponse({
                            'success': False, 
                            'error': f'No hay cupo disponible en la especialidad {especialidad.nombre}'
                        }, status=400)
                except Especialidad.DoesNotExist:
                    return JsonResponse({'success': False, 'error': 'Especialidad no válida'}, status=400)
            else:
                pass

            taller = None
            taller_id = data.get('taller_id')
            if taller_id:
                try:
                    taller = Taller.objects.get(pk=taller_id)
                    if taller.fichas_disponibles() <= 0:
                        return JsonResponse({
                            'success': False, 
                            'error': f'No hay cupo disponible en el taller {taller.nombre}'
                        }, status=400)
                except Taller.DoesNotExist:
                    return JsonResponse({'success': False, 'error': 'Taller no válido'}, status=400)

            ficha = FichaInscripcion(
                alumno=alumno,
                especialidad=especialidad,
                taller=taller
            )
            
            ficha.save()

            return JsonResponse({
                'success': True,
                'message': 'Inscripción registrada exitosamente',
                'data': {
                    'id_inscripcion': ficha.id_inscripcion,
                    'numero_control': ficha.alumno.numero_control,
                    'nombre_completo': f"{ficha.alumno.nombres} {ficha.alumno.apellido_paterno} {ficha.alumno.apellido_materno}",
                    'grupo_asignado': ficha.grupo_inscripcion,
                    'semestre_asignado': ficha.semestre_inscripcion,
                    'especialidad_asignada': ficha.especialidad.nombre if ficha.especialidad else None,
                    'codigo_especialidad': ficha.especialidad.codigo if ficha.especialidad else None,
                    'taller_asignado': ficha.taller.nombre if ficha.taller else None,
                    'fecha_solicitud': ficha.fecha_solicitud.isoformat()
                }
            }, status=201)

        except ValidationError as e:
            return JsonResponse({
                'success': False,
                'error': str(e.message) if hasattr(e, 'message') else str(e)
            }, status=400)
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': f'Error interno del servidor: {str(e)}'
            }, status=500)
    else:
        return JsonResponse({'error': 'Método no permitido'}, status=405)


def consultar_ficha(request, numero_control):
    if request.method == 'GET':
        try:
            alumno = Alumno.objects.get(numero_control=numero_control)
            ficha = FichaInscripcion.objects.get(alumno=alumno)
            
            data = {
                'id_inscripcion': ficha.id_inscripcion,
                'alumno': {
                    'numero_control': ficha.alumno.numero_control,
                    'nombre_completo': f"{ficha.alumno.nombres} {ficha.alumno.apellido_paterno} {ficha.alumno.apellido_materno}",
                    'grupo_anterior': ficha.alumno.grupo_anterior,
                    'semestre_anterior': ficha.alumno.semestre_anterior
                },
                'inscripcion': {
                    'grupo_inscripcion': ficha.grupo_inscripcion,
                    'semestre_inscripcion': ficha.semestre_inscripcion,
                    'especialidad': {
                        'nombre': ficha.especialidad.nombre if ficha.especialidad else None,
                        'codigo': ficha.especialidad.codigo if ficha.especialidad else None
                    },
                    'taller': ficha.taller.nombre if ficha.taller else None,
                    'fecha_solicitud': ficha.fecha_solicitud
                }
            }
            
            return JsonResponse(data, status=200)
            
        except Alumno.DoesNotExist:
            return JsonResponse({'error': 'Alumno no encontrado'}, status=404)
        except FichaInscripcion.DoesNotExist:
            return JsonResponse({'error': 'El alumno no tiene ficha de inscripción'}, status=404)
    else:
        return JsonResponse({'error': 'Método no permitido'}, status=405)


@require_http_methods(["GET"])
def generar_solicitud_pdf(request, numero_control):
    try:
        try:
            alumno = Alumno.objects.get(numero_control=numero_control)
            ficha = FichaInscripcion.objects.get(alumno=alumno)
        except Alumno.DoesNotExist:
            return HttpResponse('Alumno no encontrado', status=404)
        except FichaInscripcion.DoesNotExist:
            return HttpResponse('El alumno no tiene ficha de inscripción registrada', status=404)

        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter,
                                rightMargin=40, leftMargin=40,
                                topMargin=30, bottomMargin=40)

        elements = []
        styles = getSampleStyleSheet()

        header_style = ParagraphStyle(
            'header',
            parent=styles['Normal'],
            fontSize=10,
            alignment=TA_CENTER,
            textColor=colors.HexColor('#003366'),
            spaceAfter=3
        )

        title_style = ParagraphStyle(
            'title',
            parent=styles['Heading1'],
            fontSize=14,
            alignment=TA_CENTER,
            textColor=colors.HexColor('#003366'),
            spaceAfter=10,
            fontName='Helvetica-Bold'
        )

        field_style = ParagraphStyle(
            'field',
            parent=styles['Normal'],
            fontSize=10,
            spaceAfter=5
        )

        section_style = ParagraphStyle(
            'section',
            parent=styles['Normal'],
            fontSize=11,
            fontName='Helvetica-Bold',
            spaceAfter=8
        )

        try:
            logo = Image("registro/static/logo.png", width=90, height=90)
        except:
            logo = Paragraph("<b>[LOGO]</b>", field_style)
        
        encabezado_data = [
            [logo, Paragraph(
                "<b>SECRETARÍA DE EDUCACIÓN PÚBLICA<br/>"
                "SUBSECRETARÍA DE EDUCACIÓN MEDIA SUPERIOR<br/>"
                "DIRECCIÓN GENERAL DE BACHILLERATO<br/>"
                "<br/>"
                "PREPARATORIA FEDERAL POR COOPERACIÓN<br/>"
                "\"VALENTÍN GÓMEZ FARÍAS\"<br/>"
                "C.C.T. 17EBH0027O</b>"
                , header_style)]
        ]
        encabezado_table = Table(encabezado_data, colWidths=[100, 450])
        encabezado_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('ALIGN', (1, 0), (1, 0), 'CENTER'),
            ('LEFTPADDING', (0, 0), (-1, -1), 5),
            ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ]))
        elements.append(encabezado_table)
        elements.append(Spacer(1, 15))

        nombre_completo = f"{alumno.nombres} {alumno.apellido_paterno} {alumno.apellido_materno}"
        
        datos_basicos = [
            [f"Número De Control: {alumno.numero_control}", f"Nombre Completo: {nombre_completo}"]
        ]
        tabla_basicos = Table(datos_basicos, colWidths=[200, 350])
        tabla_basicos.setStyle(TableStyle([
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ]))
        elements.append(tabla_basicos)
        elements.append(Spacer(1, 15))

        datos_reinscripcion = [
            ["DATOS DE REINSCRIPCIÓN"],
            ["SEMESTRE", "ESPECIALIDAD", "TALLER"],
            [str(ficha.semestre_inscripcion), ficha.especialidad.nombre, ficha.taller.nombre]
        ]
        tabla_reinscripcion = Table(datos_reinscripcion, colWidths=[183, 183, 184])
        tabla_reinscripcion.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('FONTNAME', (0, 0), (0, 0), 'Helvetica-Bold'),
            ('FONTNAME', (0, 1), (-1, 1), 'Helvetica-Bold'),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('SPAN', (0, 0), (-1, 0)),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#E8E8E8")),
            ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor("#F0F0F0")),
        ]))
        elements.append(tabla_reinscripcion)
        elements.append(Spacer(1, 15))

        datos_ultimo_semestre = [
            ["DATOS ULTIMO SEMESTRE CURSADO"],
            ["GRUPO ANTERIOR", "SEMESTRE ANTERIOR"],
            [str(alumno.grupo_anterior), str(alumno.semestre_anterior)]
        ]
        tabla_ultimo = Table(datos_ultimo_semestre, colWidths=[275, 275])
        tabla_ultimo.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('FONTNAME', (0, 0), (0, 0), 'Helvetica-Bold'),
            ('FONTNAME', (0, 1), (-1, 1), 'Helvetica-Bold'),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('SPAN', (0, 0), (-1, 0)),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#E8E8E8")),
            ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor("#F0F0F0")),
        ]))
        elements.append(tabla_ultimo)
        elements.append(Spacer(1, 15))

        materias_header = [
            ["MATERIAS QUE ADEUDAN EN LOS SEMESTRES ANTERIORES"],
            ["MATERIA", "PERIODO", "SEMESTRE"]
        ]
        materias_rows = [["", "", ""] for _ in range(6)]
        
        materias_data = materias_header + materias_rows
        tabla_materias = Table(materias_data, colWidths=[250, 150, 150])
        tabla_materias.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('FONTNAME', (0, 0), (0, 0), 'Helvetica-Bold'),
            ('FONTNAME', (0, 1), (-1, 1), 'Helvetica-Bold'),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('SPAN', (0, 0), (-1, 0)),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#E8E8E8")),
            ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor("#F0F0F0")),
        ]))
        elements.append(tabla_materias)
        elements.append(Spacer(1, 15))

        observaciones_data = [
            ["OBSERVACIONES"],
            [""]
        ]
        tabla_observaciones = Table(observaciones_data, colWidths=[550], rowHeights=[25, 60])
        tabla_observaciones.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('FONTNAME', (0, 0), (0, 0), 'Helvetica-Bold'),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BACKGROUND', (0, 0), (0, 0), colors.HexColor("#E8E8E8")),
            ('VALIGN', (0, 1), (0, 1), 'TOP'),
        ]))
        elements.append(tabla_observaciones)
        elements.append(Spacer(1, 20))

        fecha_actual = ficha.fecha_solicitud.strftime('%d/%m/%Y')
        firma_data = [
            ["FIRMA DE CONTROL ESCOLAR"],
            [""],
            [f"FECHA DE SOLICITUD: {fecha_actual}"]
        ]
        tabla_firma = Table(firma_data, colWidths=[275], rowHeights=[25, 50, 25])
        tabla_firma.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('FONTNAME', (0, 0), (0, 0), 'Helvetica-Bold'),
            ('FONTNAME', (0, 2), (0, 2), 'Helvetica-Bold'),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BACKGROUND', (0, 0), (0, 0), colors.HexColor("#E8E8E8")),
        ]))
        elements.append(tabla_firma)

        doc.build(elements)
        buffer.seek(0)
        
        response = HttpResponse(buffer, content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="solicitud_reinscripcion_{numero_control}.pdf"'
        
        response['Access-Control-Allow-Origin'] = '*'
        response['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
        response['Access-Control-Allow-Headers'] = 'Content-Type'
        
        return response

    except Exception as e:
        error_response = HttpResponse(f"Error al generar PDF: {str(e)}", status=500)
        error_response['Access-Control-Allow-Origin'] = '*'
        return error_response


def handle_preflight(request):
    response = HttpResponse()
    response['Access-Control-Allow-Origin'] = '*'
    response['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
    response['Access-Control-Allow-Headers'] = 'Content-Type'
    response['Access-Control-Max-Age'] = '86400'
    return response
