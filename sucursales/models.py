from django.db import models

# Create your models here.

class Sucursal(models.Model):
    nombre = models.CharField(max_length=255, unique=True)
    direccion = models.CharField(max_length=500, blank=True, null=True)
    telefono = models.CharField(max_length=50, blank=True, null=True)
    low_stock_threshold = models.PositiveIntegerField(default=0, help_text="0 usa el umbral global")
    
    def __str__(self):
        return self.nombre
