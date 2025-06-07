from django.db import models
from django.utils import timezone

class Factura(models.Model):
    CONDICION_VENTA = [
        ('CONTADO', 'Contado'),
        ('CUENTA_CORRIENTE', 'Cuenta Corriente'),
        ('TARJETA_DEBITO', 'Tarjeta de Débito'),
        ('TARJETA_CREDITO', 'Tarjeta de Crédito'),
        ('OTRO', 'Otro'),
    ]

    TIPO_FACTURA = [
        ('A', 'Factura A'),
        ('B', 'Factura B'),
        ('C', 'Factura C'),
    ]

    CONDICION_IVA = [
        ('RESPONSABLE_INSCRIPTO', 'Responsable Inscripto'),
        ('RESPONSABLE_NO_INSCRIPTO', 'Responsable No Inscripto'),
        ('EXENTO', 'Exento'),
        ('MONOTRIBUTO', 'Monotributo'),
        ('CONSUMIDOR_FINAL', 'Consumidor Final'),
    ]

    TIPO_COPIA = [
        ('ORIGINAL', 'Original'),
        ('DUPLICADO', 'Duplicado'),
    ]

    numero = models.CharField(max_length=20, unique=True)
    punto_venta = models.CharField(max_length=5)
    fecha_emision = models.DateField(default=timezone.now)
    cuit = models.CharField(max_length=13, blank=True, null=True)
    monto_total = models.DecimalField(max_digits=10, decimal_places=2)
    imagen = models.ImageField(upload_to='facturas/')
    tipo_factura = models.CharField(
        max_length=1,
        choices=TIPO_FACTURA,
        default='B'
    )
    condicion_venta = models.CharField(
        max_length=20,
        choices=CONDICION_VENTA,
        default='CONTADO'
    )
    condicion_iva = models.CharField(
        max_length=30,
        choices=CONDICION_IVA,
        default='CONSUMIDOR_FINAL'
    )
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    iva = models.DecimalField(max_digits=10, decimal_places=2)
    percepcion_iibb = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    otros_tributos = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    tipo_copia = models.CharField(
        max_length=10,
        choices=TIPO_COPIA,
        default='ORIGINAL'
    )
    razon_social_cliente = models.CharField(max_length=200, blank=True, null=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Factura {self.tipo_factura} {self.punto_venta}-{self.numero}"

    class Meta:
        verbose_name = "Factura"
        verbose_name_plural = "Facturas"
        ordering = ['-fecha_emision']

class ProductoFactura(models.Model):
    factura = models.ForeignKey(Factura, on_delete=models.CASCADE, related_name='productos')
    descripcion = models.CharField(max_length=200)
    cantidad = models.DecimalField(max_digits=10, decimal_places=2)
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    importe_bonificado = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, default=0)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    def __str__(self):
        return f"{self.descripcion} - {self.cantidad} unidades"

    class Meta:
        verbose_name = "Producto de Factura"
        verbose_name_plural = "Productos de Factura"
