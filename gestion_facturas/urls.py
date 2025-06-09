from django.contrib import admin
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from . import views

app_name = 'gestion_facturas'

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.index, name='index'),
    path('facturas/', views.lista_facturas, name='lista_facturas'),
    path('facturas/cargar/', views.cargar_factura, name='cargar_factura'),
    path('facturas/confirmar/', views.confirmar_datos, name='confirmar_datos'),
    path('facturas/guardar/', views.guardar_factura, name='guardar_factura'),
    path('imagen/<int:factura_id>/', views.ver_imagen, name='ver_imagen'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT) 