from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from .models import Factura, ProductoFactura
from .utils import procesar_factura, preprocesar_imagen, extraer_texto
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
from django.http import HttpResponse

# Create your views here.

def index(request):
    return render(request, 'gestion_facturas/index.html')

def cargar_factura(request):
    if request.method == 'POST':
        try:
            # Limpiar caché y archivos temporales
            if 'facturas_procesadas' in request.session:
                del request.session['facturas_procesadas']
            if 'rutas_temporales' in request.session:
                for ruta in request.session['rutas_temporales']:
                    try:
                        if os.path.exists(ruta):
                            os.remove(ruta)
                    except Exception as e:
                        print(f"Error al eliminar archivo temporal: {str(e)}")
                del request.session['rutas_temporales']

            # Obtener la imagen del request
            imagen = request.FILES.get('imagen')
            if not imagen:
                messages.error(request, 'Por favor, seleccione al menos una imagen de factura para procesar')
                return redirect('gestion_facturas:cargar_factura')

            # Leer la imagen directamente
            imagen_bytes = imagen.read()
            imagen_array = np.frombuffer(imagen_bytes, np.uint8)
            imagen_cv = cv2.imdecode(imagen_array, cv2.IMREAD_COLOR)
            
            if imagen_cv is None:
                messages.error(request, 'No se pudo procesar la imagen. Por favor, asegúrese de que el archivo sea una imagen válida')
                return redirect('gestion_facturas:cargar_factura')

            # Convertir la imagen original a base64 para mostrarla
            _, buffer = cv2.imencode('.png', imagen_cv)
            imagen_original_base64 = base64.b64encode(buffer).decode('utf-8')

            # Procesar la factura
            datos = procesar_factura(imagen_cv)
            print("Datos extraídos:", datos)  # Debug

            # Extraer el texto directamente de la imagen procesada
            texto = extraer_texto(preprocesar_imagen(imagen_cv))

            # Crear diccionario con los datos de la factura procesada
            factura_procesada = {
                'imagen_original_base64': imagen_original_base64,
                'texto_extraido': texto,
                'datos': datos
            }
            print("Factura procesada:", factura_procesada)  # Debug

            # Obtener facturas procesadas anteriormente
            facturas_procesadas = request.session.get('facturas_procesadas', [])
            facturas_procesadas.append(factura_procesada)
            request.session['facturas_procesadas'] = facturas_procesadas

            return redirect('gestion_facturas:confirmar_datos')
        except Exception as e:
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
                    cuit=request.POST.get(f'cuit_{i}'),
                    monto_total=request.POST.get(f'monto_total_{i}')
                )
                
                # Guardar la imagen si existe
                if i < len(imagenes):
                    factura.imagen = imagenes[i]
                
                factura.save()
            
            # Limpiar caché y archivos temporales después de guardar
            if 'facturas_procesadas' in request.session:
                del request.session['facturas_procesadas']
            if 'rutas_temporales' in request.session:
                for ruta in request.session['rutas_temporales']:
                    try:
                        if os.path.exists(ruta):
                            os.remove(ruta)
                    except Exception as e:
                        print(f"Error al eliminar archivo temporal: {str(e)}")
                del request.session['rutas_temporales']
            
            messages.success(request, '¡Las facturas se han guardado correctamente!')
            return redirect('gestion_facturas:index')
        except Exception as e:
            messages.error(request, 'No se pudieron guardar las facturas. Por favor, verifique los datos e intente nuevamente')
            return redirect('gestion_facturas:cargar_factura')
    
    # Si es GET, mostrar el formulario con los datos procesados
    facturas = request.session.get('facturas_procesadas', [])
    if not facturas:
        messages.error(request, 'No hay facturas para confirmar')
        return redirect('gestion_facturas:cargar_factura')
    
    return render(request, 'gestion_facturas/confirmar_datos.html', {
        'facturas': facturas,
        'debug': settings.DEBUG
    })

def lista_facturas(request):
    facturas = Factura.objects.all().order_by('-fecha_emision')
    return render(request, 'gestion_facturas/lista_facturas.html', {'facturas': facturas})

def guardar_factura(request):
    if request.method == 'POST':
        try:
            # Obtener datos de la sesión
            facturas = request.session.get('facturas_procesadas', [])
            if not facturas:
                messages.error(request, 'No hay facturas para guardar. Por favor, cargue al menos una factura')
                return redirect('gestion_facturas:confirmar_datos')
            
            for i, factura in enumerate(facturas):
                # Convertir valores numéricos de formato argentino a decimal
                def convertir_valor(valor):
                    if isinstance(valor, str):
                        # Eliminar el símbolo de moneda y espacios
                        valor = valor.replace('$', '').replace(' ', '')
                        # Reemplazar coma por punto para el decimal
                        valor = valor.replace(',', '.')
                        try:
                            return float(valor)
                        except ValueError:
                            return 0.0
                    return valor

                # Convertir la fecha al formato correcto
                fecha_str = request.POST.get(f'fecha_{i+1}')
                fecha = None
                if fecha_str:
                    try:
                        fecha = datetime.strptime(fecha_str, '%d/%m/%Y').date()
                    except ValueError:
                        messages.error(request, f'El formato de la fecha "{fecha_str}" no es válido. Por favor, use el formato DD/MM/YYYY')
                        return redirect('gestion_facturas:confirmar_datos')

                # Obtener la imagen de la sesión
                imagen_data = factura.get('imagen_original_base64')
                if not imagen_data:
                    messages.error(request, 'No se encontró la imagen de la factura. Por favor, intente cargar la factura nuevamente')
                    return redirect('gestion_facturas:confirmar_datos')

                # Convertir la imagen base64 a archivo
                try:
                    imagen_bytes = base64.b64decode(imagen_data)
                    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
                    temp_file.write(imagen_bytes)
                    temp_file.close()
                except Exception as e:
                    messages.error(request, 'No se pudo procesar la imagen de la factura. Por favor, intente nuevamente')
                    return redirect('gestion_facturas:confirmar_datos')

                # Crear nueva factura
                try:
                    nueva_factura = Factura(
                        tipo_factura=request.POST.get(f'tipo_factura_{i+1}'),
                        punto_venta=request.POST.get(f'punto_venta_{i+1}'),
                        numero=request.POST.get(f'numero_{i+1}'),
                        fecha_emision=fecha,
                        tipo_copia=request.POST.get(f'tipo_copia_{i+1}'),
                        cuit=request.POST.get(f'cuit_{i+1}'),
                        cuit_emisor=request.POST.get(f'cuit_emisor_{i+1}'),
                        razon_social_cliente=request.POST.get(f'razon_social_cliente_{i+1}'),
                        razon_social_emisor=request.POST.get(f'razon_social_emisor_{i+1}'),
                        condicion_venta=request.POST.get(f'condicion_venta_{i+1}'),
                        condicion_iva=request.POST.get(f'condicion_iva_{i+1}'),
                        subtotal=convertir_valor(request.POST.get(f'subtotal_{i+1}')),
                        iva=convertir_valor(request.POST.get(f'iva_{i+1}')),
                        percepcion_iibb=convertir_valor(request.POST.get(f'percepcion_iibb_{i+1}')),
                        otros_tributos=convertir_valor(request.POST.get(f'otros_tributos_{i+1}')),
                        monto_total=convertir_valor(request.POST.get(f'total_{i+1}'))
                    )
                    nueva_factura.save()

                    # Guardar la imagen
                    with open(temp_file.name, 'rb') as f:
                        nueva_factura.imagen.save(f'factura_{nueva_factura.numero}.png', File(f), save=True)

                    # Eliminar el archivo temporal
                    os.unlink(temp_file.name)

                    # Guardar productos
                    productos = factura.get('datos', {}).get('productos', [])
                    for j, producto in enumerate(productos):
                        nuevo_producto = ProductoFactura(
                            factura=nueva_factura,
                            descripcion=request.POST.get(f'producto_descripcion_{i+1}_{j+1}'),
                            cantidad=convertir_valor(request.POST.get(f'producto_cantidad_{i+1}_{j+1}')),
                            precio_unitario=convertir_valor(request.POST.get(f'producto_precio_unitario_{i+1}_{j+1}')),
                            importe_bonificado=convertir_valor(request.POST.get(f'producto_importe_bonificado_{i+1}_{j+1}')),
                            subtotal=convertir_valor(request.POST.get(f'producto_subtotal_{i+1}_{j+1}'))
                        )
                        nuevo_producto.save()

                except Exception as e:
                    messages.error(request, 'No se pudo guardar la factura. Por favor, verifique los datos e intente nuevamente')
                    if os.path.exists(temp_file.name):
                        os.unlink(temp_file.name)
                    return redirect('gestion_facturas:confirmar_datos')

            # Limpiar la sesión
            if 'facturas_procesadas' in request.session:
                del request.session['facturas_procesadas']

            messages.success(request, '¡Las facturas se han guardado correctamente!')
            return redirect('gestion_facturas:index')

        except Exception as e:
            messages.error(request, 'No se pudieron guardar las facturas. Por favor, intente nuevamente o contacte al soporte técnico')
            return redirect('gestion_facturas:confirmar_datos')

    return redirect('gestion_facturas:index')

def detalle_factura(request, factura_id):
    try:
        factura = Factura.objects.get(id=factura_id)
        productos = factura.productos.all()
        return render(request, 'gestion_facturas/detalle_factura.html', {
            'factura': factura,
            'productos': productos
        })
    except Factura.DoesNotExist:
        messages.error(request, 'No se encontró la factura solicitada')
        return redirect('gestion_facturas:lista_facturas')

def ver_imagen(request, factura_id):
    try:
        factura = Factura.objects.get(id=factura_id)
        if factura.imagen:
            return render(request, 'gestion_facturas/ver_imagen.html', {
                'factura': factura
            })
        else:
            messages.error(request, 'No se encontró la imagen de la factura')
            return redirect('gestion_facturas:lista_facturas')
    except Factura.DoesNotExist:
        messages.error(request, 'No se encontró la factura solicitada')
        return redirect('gestion_facturas:lista_facturas')

def eliminar_factura(request, factura_id):
    if request.method == 'POST':
        factura = get_object_or_404(Factura, id=factura_id)
        
        # Eliminar la imagen si existe
        if factura.imagen:
            try:
                if os.path.isfile(factura.imagen.path):
                    os.remove(factura.imagen.path)
            except Exception as e:
                messages.warning(request, f"Error al eliminar la imagen: {str(e)}")
        
        # Eliminar la factura
        factura.delete()
        messages.success(request, 'Factura eliminada correctamente')
        
    return redirect('gestion_facturas:index')

def editar_factura(request, factura_id):
    if request.method == 'POST':
        factura = get_object_or_404(Factura, id=factura_id)
        
        try:
            # Actualizar los campos de la factura
            factura.tipo_factura = request.POST.get('tipo_factura')
            factura.punto_venta = request.POST.get('punto_venta')
            factura.numero = request.POST.get('numero')
            factura.fecha_emision = request.POST.get('fecha')
            factura.condicion_venta = request.POST.get('condicion_venta')
            factura.condicion_iva = request.POST.get('condicion_iva')
            factura.razon_social_cliente = request.POST.get('razon_social_cliente')
            factura.cuit = request.POST.get('cuit')
            factura.razon_social_emisor = request.POST.get('razon_social_emisor')
            factura.cuit_emisor = request.POST.get('cuit_emisor')
            
            # Convertir y actualizar campos numéricos
            factura.subtotal = float(request.POST.get('subtotal', 0))
            factura.iva = float(request.POST.get('iva', 0))
            factura.percepcion_iibb = float(request.POST.get('percepcion_iibb', 0))
            factura.monto_total = float(request.POST.get('monto_total', 0))
            
            factura.save()
            messages.success(request, 'Factura actualizada correctamente')
        except ValueError as e:
            messages.error(request, f'Error en los valores numéricos: {str(e)}')
        except Exception as e:
            messages.error(request, f'Error al actualizar la factura: {str(e)}')
            
        return redirect('gestion_facturas:index')
        
    return redirect('gestion_facturas:index')
