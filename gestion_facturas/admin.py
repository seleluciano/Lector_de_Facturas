from django.contrib import admin
from .models import Factura, ProductoFactura

@admin.register(Factura)
class FacturaAdmin(admin.ModelAdmin):
    list_display = ('numero', 'punto_venta', 'fecha_emision', 'tipo_factura', 'razon_social_cliente', 'monto_total')
    list_filter = ('tipo_factura', 'fecha_emision', 'condicion_venta', 'condicion_iva')
    search_fields = ('numero', 'cuit', 'razon_social_cliente')
    date_hierarchy = 'fecha_emision'

@admin.register(ProductoFactura)
class ProductoFacturaAdmin(admin.ModelAdmin):
    list_display = ('factura', 'descripcion', 'cantidad')
    list_filter = ('factura__tipo_factura', 'factura__fecha_emision')
    search_fields = ('descripcion', 'factura__numero')
