from django.contrib import admin
from .models import Factura

@admin.register(Factura)
class FacturaAdmin(admin.ModelAdmin):
    list_display = ('numero', 'fecha_emision', 'cliente', 'monto_total', 'estado')
    list_filter = ('estado', 'fecha_emision')
    search_fields = ('numero', 'cliente')
    date_hierarchy = 'fecha_emision'
