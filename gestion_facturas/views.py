from django.shortcuts import render, redirect
from django.contrib import messages
from .models import Factura
from .utils import procesar_factura
from django.core.files.storage import FileSystemStorage
import os
from datetime import datetime
import uuid
import tempfile
import shutil
from django.conf import settings

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
        
        # Crear directorio temporal en media si no existe
        temp_dir = os.path.join(settings.MEDIA_ROOT, 'temp')
        if not os.path.exists(temp_dir):
            os.makedirs(temp_dir)
        
        for imagen in imagenes:
            try:
                print(f"Procesando archivo: {imagen.name}")
                
                # Verificar el formato del archivo
                extension = os.path.splitext(imagen.name)[1].lower()
                if extension not in ['.png', '.jpg', '.jpeg', '.pdf']:
                    raise ValueError(f"Formato de archivo no soportado: {extension}. Solo se permiten archivos PNG, JPG y PDF.")
                
                # Generar nombre único para el archivo
                nombre_archivo = f"{uuid.uuid4()}{extension}"
                ruta_completa = os.path.join(temp_dir, nombre_archivo)
                
                # Guardar el archivo en el directorio temporal
                try:
                    with open(ruta_completa, 'wb+') as destino:
                        for chunk in imagen.chunks():
                            destino.write(chunk)
                except Exception as e:
                    raise ValueError(f"Error al guardar el archivo: {str(e)}")
                
                # Verificar que el archivo se guardó correctamente
                if not os.path.exists(ruta_completa):
                    raise FileNotFoundError("No se pudo guardar el archivo")
                
                # Verificar el tamaño del archivo
                if os.path.getsize(ruta_completa) == 0:
                    raise ValueError("El archivo está vacío")
                
                print(f"Archivo guardado en: {ruta_completa}")
                
                # Procesar la factura
                datos = procesar_factura(ruta_completa)
                
                # Agregar a la lista de facturas procesadas
                facturas_procesadas.append({
                    'datos': datos,
                    'imagen_url': f'/media/temp/{nombre_archivo}',
                    'nombre_original': imagen.name,
                    'ruta_temporal': ruta_completa
                })
                
            except Exception as e:
                print(f"Error al procesar {imagen.name}: {str(e)}")
                messages.error(request, f'Error al procesar {imagen.name}: {str(e)}')
                # Limpiar archivo temporal si existe
                if 'ruta_completa' in locals() and os.path.exists(ruta_completa):
                    try:
                        os.remove(ruta_completa)
                    except Exception as e:
                        print(f"Error al eliminar archivo temporal: {str(e)}")
        
        if facturas_procesadas:
            # Guardar las rutas temporales en la sesión para limpiar después
            request.session['rutas_temporales'] = [f['ruta_temporal'] for f in facturas_procesadas]
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
            
            # Limpiar archivos temporales
            rutas_temporales = request.session.get('rutas_temporales', [])
            for ruta in rutas_temporales:
                try:
                    if os.path.exists(ruta):
                        os.remove(ruta)
                except Exception as e:
                    print(f"Error al eliminar archivo temporal: {str(e)}")
            
            # Limpiar la sesión
            if 'rutas_temporales' in request.session:
                del request.session['rutas_temporales']
            
            messages.success(request, 'Facturas guardadas exitosamente')
            return redirect('gestion_facturas:lista_facturas')
        except Exception as e:
            messages.error(request, f'Error al guardar las facturas: {str(e)}')
            return redirect('gestion_facturas:cargar_factura')
    
    return redirect('gestion_facturas:cargar_factura')

def lista_facturas(request):
    facturas = Factura.objects.all()
    return render(request, 'gestion_facturas/lista_facturas.html', {'facturas': facturas})
