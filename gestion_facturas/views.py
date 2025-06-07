from django.shortcuts import render, redirect
from django.contrib import messages
from .models import Factura
from .utils import procesar_factura, preprocesar_imagen
from django.core.files.storage import FileSystemStorage
import os
from datetime import datetime
import uuid
import tempfile
import shutil
from django.conf import settings
import cv2
import numpy as np
import base64
from io import BytesIO
from django.core.files.base import File

# Create your views here.

def index(request):
    return render(request, 'gestion_facturas/index.html')

def cargar_factura(request):
    if request.method == 'POST':
        try:
            # Obtener la imagen del request
            imagen = request.FILES.get('imagen')
            if not imagen:
                messages.error(request, 'No se proporcionó ninguna imagen')
                return redirect('gestion_facturas:cargar_factura')

            # Leer la imagen directamente
            imagen_bytes = imagen.read()
            imagen_array = np.frombuffer(imagen_bytes, np.uint8)
            imagen_cv = cv2.imdecode(imagen_array, cv2.IMREAD_COLOR)
            
            if imagen_cv is None:
                messages.error(request, 'No se pudo leer la imagen')
                return redirect('gestion_facturas:cargar_factura')

            # Convertir la imagen original a base64 para mostrarla
            _, buffer = cv2.imencode('.png', imagen_cv)
            imagen_original_base64 = base64.b64encode(buffer).decode('utf-8')

            # Procesar la factura
            datos = procesar_factura(imagen_cv)
            print("Datos extraídos:", datos)  # Debug

            # Crear diccionario con los datos de la factura procesada
            factura_procesada = {
                'imagen_original_base64': imagen_original_base64,
                'datos': datos
            }
            print("Factura procesada:", factura_procesada)  # Debug

            # Obtener facturas procesadas anteriormente
            facturas_procesadas = request.session.get('facturas_procesadas', [])
            facturas_procesadas.append(factura_procesada)
            request.session['facturas_procesadas'] = facturas_procesadas
            print("Facturas procesadas:", facturas_procesadas)  # Debug

            # Renderizar la plantilla con los datos
            return render(request, 'gestion_facturas/confirmar_datos.html', {
                'facturas': facturas_procesadas,
                'debug': settings.DEBUG
            })

        except Exception as e:
            print(f"Error en cargar_factura: {str(e)}")
            messages.error(request, f'Error al procesar la factura: {str(e)}')
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

def guardar_factura(request):
    if request.method == 'POST':
        try:
            # Obtener las facturas procesadas de la sesión
            facturas_procesadas = request.session.get('facturas_procesadas', [])
            
            for i, factura in enumerate(facturas_procesadas):
                # Obtener la fecha del formulario
                fecha_str = request.POST.get(f'fecha_{i+1}')
                try:
                    # Convertir la fecha de YYYY-MM-DD a datetime
                    fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
                except ValueError:
                    messages.error(request, f'Formato de fecha inválido: {fecha_str}')
                    return redirect('gestion_facturas:cargar_factura')

                # Crear nueva factura
                nueva_factura = Factura(
                    numero=request.POST.get(f'numero_{i+1}'),
                    fecha_emision=fecha,
                    cliente=request.POST.get(f'cliente_{i+1}'),
                    cuit=request.POST.get(f'cuit_{i+1}'),
                    monto_total=request.POST.get(f'total_{i+1}')
                )
                
                # Convertir la imagen base64 a archivo
                imagen_base64 = factura['imagen_original_base64']
                imagen_bytes = base64.b64decode(imagen_base64)
                
                # Crear un archivo temporal
                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
                temp_file.write(imagen_bytes)
                temp_file.close()
                
                # Guardar la imagen en el modelo
                with open(temp_file.name, 'rb') as f:
                    nueva_factura.imagen.save(f'factura_{nueva_factura.numero}.png', File(f), save=True)
                
                # Eliminar el archivo temporal
                os.unlink(temp_file.name)
                
                nueva_factura.save()
            
            # Limpiar la sesión
            if 'facturas_procesadas' in request.session:
                del request.session['facturas_procesadas']
            
            messages.success(request, 'Facturas guardadas exitosamente')
            return redirect('gestion_facturas:lista_facturas')
            
        except Exception as e:
            print(f"Error en guardar_factura: {str(e)}")
            messages.error(request, f'Error al guardar las facturas: {str(e)}')
            return redirect('gestion_facturas:cargar_factura')
    
    return redirect('gestion_facturas:cargar_factura')
