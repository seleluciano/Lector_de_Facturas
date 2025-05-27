from django.db import models
from django.utils import timezone

class Factura(models.Model):
    numero = models.CharField(max_length=20, unique=True)
    fecha_emision = models.DateField(default=timezone.now)
    cliente = models.CharField(max_length=200)
    monto_total = models.DecimalField(max_digits=10, decimal_places=2)
    estado = models.CharField(
        max_length=20,
        choices=[
            ('PENDIENTE', 'Pendiente'),
            ('PAGADA', 'Pagada'),
            ('ANULADA', 'Anulada'),
        ],
        default='PENDIENTE'
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Factura {self.numero} - {self.cliente}"

    class Meta:
        verbose_name = "Factura"
        verbose_name_plural = "Facturas"
        ordering = ['-fecha_emision']
