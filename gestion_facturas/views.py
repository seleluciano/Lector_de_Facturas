from django.shortcuts import render, redirect
from django.contrib import messages
from .models import Factura
from .utils import procesar_factura
from django.core.files.storage import FileSystemStorage
import os
from datetime import datetime
import uuid
import tempfile

# Create your views here.

def index(request):
    return render(request, 'gestion_facturas/index.html')

def cargar_factura(request):
    if request.method == 'POST':
        if 'imagen' not in request.FILES:
            messages.error(request, 'Por favor seleccione al menos una imagen')
            return redirect('gestion_facturas:cargar_factura')
        
        imagenes = request.FILES.getlist('imagen')
        facturas_procesadas = []
        
        # Usar el directorio temporal del sistema
        temp_dir = tempfile.gettempdir()
        
        for imagen in imagenes:
            try:
                # Generar nombre único para el archivo
                extension = os.path.splitext(imagen.name)[1]
                nombre_archivo = f"{uuid.uuid4()}{extension}"
                ruta_completa = os.path.join(temp_dir, nombre_archivo)
                
                # Guardar la imagen con manejo de permisos
                try:
                    with open(ruta_completa, 'wb+') as destino:
                        for chunk in imagen.chunks():
                            destino.write(chunk)
                except PermissionError:
                    raise PermissionError(f"No hay permisos para escribir en el directorio temporal: {temp_dir}")
                
                # Verificar que el archivo se guardó correctamente
                if not os.path.exists(ruta_completa):
                    raise FileNotFoundError("No se pudo guardar el archivo")
                
                # Verificar permisos de lectura
                if not os.access(ruta_completa, os.R_OK):
                    raise PermissionError(f"No hay permisos de lectura para el archivo: {ruta_completa}")
                
                # Procesar la factura
                datos = procesar_factura(ruta_completa)
                
                # Agregar a la lista de facturas procesadas
                facturas_procesadas.append({
                    'datos': datos,
                    'imagen_url': f'/media/temp/{nombre_archivo}',
                    'nombre_original': imagen.name
                })
                
            except Exception as e:
                messages.error(request, f'Error al procesar {imagen.name}: {str(e)}')
            finally:
                # Limpiar archivo temporal
                try:
                    if os.path.exists(ruta_completa):
                        os.remove(ruta_completa)
                except Exception as e:
                    print(f"Error al eliminar archivo temporal: {str(e)}")
        
        if facturas_procesadas:
            return render(request, 'gestion_facturas/confirmar_datos.html', {
                'facturas': facturas_procesadas
            })
        else:
            messages.error(request, 'No se pudo procesar ninguna factura')
            return redirect('gestion_facturas:cargar_factura')
    
    return render(request, 'gestion_facturas/cargar_factura.html')

def confirmar_datos(request):
    if request.method == 'POST':
        try:
            # Obtener los datos de todas las facturas
            facturas_data = request.POST.getlist('factura_data[]')
            imagenes = request.FILES.getlist('imagen')
            
            for i, factura_data in enumerate(facturas_data):
                # Crear nueva factura
                factura = Factura(
                    numero=request.POST.get(f'numero_{i}'),
                    fecha_emision=datetime.strptime(request.POST.get(f'fecha_{i}'), '%d/%m/%Y').date(),
                    cliente=request.POST.get(f'cliente_{i}'),
                    cuit=request.POST.get(f'cuit_{i}'),
                    monto_total=request.POST.get(f'monto_total_{i}')
                )
                
                # Guardar la imagen si existe
                if i < len(imagenes):
                    factura.imagen = imagenes[i]
                
                factura.save()
            
            messages.success(request, 'Facturas guardadas exitosamente')
            return redirect('gestion_facturas:lista_facturas')
        except Exception as e:
            messages.error(request, f'Error al guardar las facturas: {str(e)}')
            return redirect('gestion_facturas:cargar_factura')
    
    return redirect('gestion_facturas:cargar_factura')

def lista_facturas(request):
    facturas = Factura.objects.all()
    return render(request, 'gestion_facturas/lista_facturas.html', {'facturas': facturas})
