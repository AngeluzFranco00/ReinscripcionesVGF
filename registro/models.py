from django.db import models
from django.core.exceptions import ValidationError

class Alumno(models.Model):
    numero_control = models.IntegerField(primary_key=True)
    nombres = models.CharField(max_length=50, db_collation='utf8mb4_unicode_ci')
    apellido_paterno = models.CharField(max_length=50)
    apellido_materno = models.CharField(max_length=50)
    grupo_anterior = models.CharField(max_length=10)
    semestre_anterior = models.IntegerField()

    def __str__(self):
        return f"{self.nombres} {self.apellido_paterno} ({self.numero_control})"

    @property
    def puede_elegir_especialidad(self):
        return self.semestre_anterior == 2

class Especialidad(models.Model):
    id_especialidad = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=50)
    codigo = models.CharField(max_length=2)
    cantidad = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.nombre} ({self.codigo})"

    def fichas_disponibles(self):
        return 40 - self.cantidad

    class Meta:
        verbose_name_plural = "Especialidades"

class Taller(models.Model):
    id_taller = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=50)
    cantidad = models.IntegerField(default=0)

    def __str__(self):
        return self.nombre

    def fichas_disponibles(self):
        return 30 - self.cantidad

    class Meta:
        verbose_name_plural = "Talleres"

class FichaInscripcion(models.Model):
    id_inscripcion = models.AutoField(primary_key=True)
    alumno = models.ForeignKey(Alumno, on_delete=models.CASCADE)
    especialidad = models.ForeignKey(Especialidad, on_delete=models.SET_NULL, null=True, blank=True)
    taller = models.ForeignKey(Taller, on_delete=models.SET_NULL, null=True, blank=True)
    grupo_inscripcion = models.CharField(max_length=10, blank=True)
    semestre_inscripcion = models.IntegerField(blank=True, null=True)
    fecha_solicitud = models.DateTimeField(auto_now_add=True)

    def clean(self):
        super().clean()
        
        if self.alumno and self.alumno.semestre_anterior == 2 and not self.especialidad:
            raise ValidationError("Los alumnos de 2do semestre deben elegir una especialidad.")
        
        if self.especialidad and self.especialidad.fichas_disponibles() <= 0:
            raise ValidationError(f"No hay cupo disponible en la especialidad {self.especialidad.nombre}")
        
        if self.taller and self.taller.fichas_disponibles() <= 0:
            raise ValidationError(f"No hay cupo disponible en el taller {self.taller.nombre}")

    def save(self, *args, **kwargs):
        self.full_clean()
        
        if self.alumno:
            self.semestre_inscripcion = self.alumno.semestre_anterior + 1
        
        if not self.especialidad and self.alumno.semestre_anterior > 2:
            self.asignar_especialidad_existente()
        
        if not self.grupo_inscripcion:
            self.grupo_inscripcion = self.calcular_grupo_nuevo()
        
        is_new = self.pk is None
        
        super().save(*args, **kwargs)
        
        if is_new:
            if self.especialidad:
                self.especialidad.cantidad += 1
                self.especialidad.save()
            if self.taller:
                self.taller.cantidad += 1
                self.taller.save()

    def asignar_especialidad_existente(self):
        
        if not self.alumno or self.alumno.semestre_anterior <= 2:
            return
            
        grupo_anterior_str = str(self.alumno.grupo_anterior)
        if len(grupo_anterior_str) >= 3:
            codigo_especialidad = grupo_anterior_str[-2:]
            try:
                especialidad = Especialidad.objects.get(codigo=codigo_especialidad)
                self.especialidad = especialidad
            except Especialidad.DoesNotExist:
                pass

    def calcular_grupo_nuevo(self):
        if not self.alumno:
            return ""
            
        if self.alumno.semestre_anterior == 2:
            if self.especialidad:
                return f"{self.semestre_inscripcion}{self.especialidad.codigo}"
            else:
                return f"{self.semestre_inscripcion}00"
        else:
            grupo_anterior_str = str(self.alumno.grupo_anterior)
            if len(grupo_anterior_str) >= 3:
                codigo_especialidad = grupo_anterior_str[-2:]
                return f"{self.semestre_inscripcion}{codigo_especialidad}"
            else:
                return f"{self.semestre_inscripcion}00"

    def __str__(self):
        return f"Ficha #{self.id_inscripcion} - {self.alumno.numero_control}"

    class Meta:
        verbose_name = "Ficha de Inscripción"
        verbose_name_plural = "Fichas de Inscripción"
        unique_together = ['alumno', 'semestre_inscripcion']