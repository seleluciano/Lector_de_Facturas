from django.shortcuts import render, redirect
from django.contrib import messages
from .models import Factura, ProductoFactura
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
import re

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

            # La fecha ya viene en formato dd/mm/aaaa del OCR, la pasamos directamente como string
            # No necesitamos parsearla a date object aquí para mostrarla en el input text
            # Si la extracción no encontró fecha, datos['fecha'] será None, lo cual es correcto.

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
            print("Datos que se pasan a la plantilla (facturas_procesadas):", facturas_procesadas) # Debug adicional
            return render(request, 'gestion_facturas/confirmar_datos.html', {
                'facturas': facturas_procesadas,
                'debug': settings.DEBUG
            })

        except Exception as e:
            print(f"Error en cargar_factura: {str(e)}")
            messages.error(request, f'Error al procesar la imagen: {str(e)}')
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
                # Obtener la fecha del formulario (esperamos dd/mm/aaaa del input text)
                fecha_str = request.POST.get(f'fecha_{i+1}')
                fecha = None
                if fecha_str:
                    try:
                        # Intentar parsear la fecha en formato dd/mm/aaaa
                        fecha = datetime.strptime(fecha_str, '%d/%m/%Y').date()
                    except ValueError:
                        messages.error(request, f'Formato de fecha inválido para guardar: {fecha_str}. Esperado DD/MM/YYYY.')
                        return redirect('gestion_facturas:cargar_factura')

                # Crear nueva factura
                nueva_factura = Factura(
                    numero=request.POST.get(f'numero_{i+1}'),
                    punto_venta=request.POST.get(f'punto_venta_{i+1}'),
                    fecha_emision=fecha, # Usar el objeto date
                    cuit=request.POST.get(f'cuit_{i+1}'),
                    monto_total=request.POST.get(f'total_{i+1}'),
                    tipo_factura=request.POST.get(f'tipo_factura_{i+1}'),
                    condicion_venta=request.POST.get(f'condicion_venta_{i+1}'),
                    condicion_iva=request.POST.get(f'condicion_iva_{i+1}'),
                    subtotal=request.POST.get(f'subtotal_{i+1}'),
                    iva=request.POST.get(f'iva_{i+1}'),
                    percepcion_iibb=request.POST.get(f'percepcion_iibb_{i+1}'),
                    otros_tributos=request.POST.get(f'otros_tributos_{i+1}'),
                    tipo_copia=request.POST.get(f'tipo_copia_{i+1}'),
                    razon_social_cliente=request.POST.get(f'razon_social_cliente_{i+1}')
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
                
                # Guardar la factura
                nueva_factura.save()

                # Guardar los productos
                # Obtener todos los campos de productos del formulario
                productos_data = {}
                # Iterar sobre los keys para encontrar los campos de producto
                for key in request.POST:
                     if key.startswith(f'producto_'):
                        # Extraer información del nombre del campo
                        # Formato esperado: producto_[tipo]_[factura]_[indice]
                        parts = key.split('_')
                        if len(parts) == 4:
                            tipo, factura_idx_str, prod_idx_str = parts[1], parts[2], parts[3]
                            
                            try:
                                factura_idx = int(factura_idx_str)
                                prod_idx = int(prod_idx_str)
                                if factura_idx == i + 1:  # Solo procesar productos de esta factura
                                    if prod_idx not in productos_data:
                                        productos_data[prod_idx] = {}
                                    productos_data[prod_idx][tipo] = request.POST.get(key)
                            except ValueError:
                                # Ignorar campos con índices no numéricos
                                continue


                # Crear los productos
                for prod_idx, prod_data in productos_data.items():
                    # Asegurarse de que la cantidad sea un número válido
                    cantidad_str = prod_data.get('cantidad', '').replace(',', '.')
                    # Obtener los nuevos campos
                    precio_unitario_str = prod_data.get('precio_unitario', '')
                    importe_bonificado_str = prod_data.get('importe_bonificado', '')
                    subtotal_producto_str = prod_data.get('subtotal', '')

                    try:
                        cantidad = float(cantidad_str)
                        # Convertir los nuevos campos a float, manejando posibles errores
                        precio_unitario = float(precio_unitario_str.replace(',', '.')) if precio_unitario_str else 0.0
                        importe_bonificado = float(importe_bonificado_str.replace(',', '.')) if importe_bonificado_str else 0.0
                        subtotal_producto = float(subtotal_producto_str.replace(',', '.')) if subtotal_producto_str else 0.0

                    except ValueError:
                        # Si la cantidad o algún importe no es un número válido, saltar este producto
                        print(f"Advertencia: Datos numéricos inválidos para el producto {prod_data.get('descripcion', '')}: Cantidad='{cantidad_str}', PU='{precio_unitario_str}', Bon='{importe_bonificado_str}', SubT='{subtotal_producto_str}'. Ignorando producto.")
                        continue # Saltar al siguiente producto

                    # Crear el objeto ProductoFactura
                    if 'descripcion' in prod_data:
                        ProductoFactura.objects.create(
                            factura=nueva_factura,
                            descripcion=prod_data['descripcion'],
                            cantidad=cantidad,
                            precio_unitario=precio_unitario,
                            importe_bonificado=importe_bonificado,
                            subtotal=subtotal_producto,
                        )
            
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
