from django.db import models
from django.utils import timezone

class Factura(models.Model):
    TIPOS_FACTURA = [
        ('A', 'Tipo A'),
        ('B', 'Tipo B'),
        ('C', 'Tipo C'),
    ]

    ESTADOS_FACTURA = [
        ('PENDIENTE', 'Pendiente'),
        ('PAGADA', 'Pagada'),
        ('ANULADA', 'Anulada'),
    ]

    numero = models.CharField(max_length=20, unique=True)
    tipo_factura = models.CharField(max_length=1, choices=TIPOS_FACTURA, verbose_name='Tipo')
    fecha_emision = models.DateField(default=timezone.now)
    cliente = models.CharField(max_length=200)
    cuit = models.CharField(max_length=13, blank=True, null=True)
    monto_total = models.DecimalField(max_digits=10, decimal_places=2)
    imagen = models.ImageField(upload_to='facturas/')
    estado = models.CharField(
        max_length=20,
        choices=ESTADOS_FACTURA,
        default='PENDIENTE'
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Factura {self.tipo_factura} {self.numero} - {self.cliente}"

    class Meta:
        verbose_name = "Factura"
        verbose_name_plural = "Facturas"
        ordering = ['-fecha_emision']
