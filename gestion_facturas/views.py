from django.shortcuts import render, redirect
from django.contrib import messages
from .models import Factura
from .utils import procesar_factura
from django.core.files.storage import FileSystemStorage
import os
from datetime import datetime
import uuid

# Create your views here.

def index(request):
    return render(request, 'gestion_facturas/index.html')

def cargar_factura(request):
    if request.method == 'POST':
        if 'imagen' not in request.FILES:
            messages.error(request, 'Por favor seleccione una imagen')
            return redirect('gestion_facturas:cargar_factura')
        
        imagen = request.FILES['imagen']
        tipo_factura = request.POST.get('tipo')
        
        # Crear directorio temporal si no existe
        temp_dir = os.path.join('temp')
        if not os.path.exists(temp_dir):
            os.makedirs(temp_dir)
        
        # Generar nombre único para el archivo
        extension = os.path.splitext(imagen.name)[1]
        nombre_archivo = f"{uuid.uuid4()}{extension}"
        ruta_completa = os.path.join(temp_dir, nombre_archivo)
        
        # Guardar la imagen
        try:
            with open(ruta_completa, 'wb+') as destino:
                for chunk in imagen.chunks():
                    destino.write(chunk)
            
            # Verificar que el archivo se guardó correctamente
            if not os.path.exists(ruta_completa):
                raise FileNotFoundError("No se pudo guardar el archivo")
            
            # Procesar la factura
            datos = procesar_factura(ruta_completa)
            
            # Preparar datos para la confirmación
            context = {
                'tipo': tipo_factura,
                'datos': datos,
                'imagen_url': f'/media/temp/{nombre_archivo}'
            }
            
            return render(request, 'gestion_facturas/confirmar_datos.html', context)
            
        except Exception as e:
            messages.error(request, f'Error al procesar la imagen: {str(e)}')
            return redirect('gestion_facturas:cargar_factura')
        finally:
            # Limpiar archivo temporal
            try:
                if os.path.exists(ruta_completa):
                    os.remove(ruta_completa)
            except Exception as e:
                print(f"Error al eliminar archivo temporal: {str(e)}")
    
    return render(request, 'gestion_facturas/cargar_factura.html')

def confirmar_datos(request):
    if request.method == 'POST':
        try:
            # Crear nueva factura con los datos confirmados
            factura = Factura(
                tipo=request.POST.get('tipo'),
                numero=request.POST.get('numero'),
                fecha_emision=datetime.strptime(request.POST.get('fecha'), '%d/%m/%Y').date(),
                cliente=request.POST.get('cliente'),
                cuit=request.POST.get('cuit'),
                monto_total=request.POST.get('monto_total')
            )
            
            # Guardar la imagen
            if 'imagen' in request.FILES:
                factura.imagen = request.FILES['imagen']
            
            factura.save()
            messages.success(request, 'Factura guardada exitosamente')
            return redirect('gestion_facturas:lista_facturas')
        except Exception as e:
            messages.error(request, f'Error al guardar la factura: {str(e)}')
            return redirect('gestion_facturas:cargar_factura')
    
    return redirect('gestion_facturas:cargar_factura')

def lista_facturas(request):
    facturas = Factura.objects.all()
    return render(request, 'gestion_facturas/lista_facturas.html', {'facturas': facturas})
