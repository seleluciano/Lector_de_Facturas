import cv2
import numpy as np
import pytesseract
from PIL import Image
import re
import os
import sys

# Configurar la ruta de Tesseract
def configurar_tesseract():
    ruta_base = r'C:\Program Files\Tesseract-OCR'
    ruta_exe = os.path.join(ruta_base, 'tesseract.exe')
    
    if os.path.exists(ruta_exe):
        try:
            # Configurar la ruta de Tesseract
            pytesseract.pytesseract.tesseract_cmd = ruta_exe
            
            # Configurar TESSDATA_PREFIX
            tessdata_dir = os.path.join(ruta_base, 'tessdata')
            if os.path.exists(tessdata_dir):
                os.environ['TESSDATA_PREFIX'] = tessdata_dir
                print(f"Tesseract configurado en: {ruta_exe}")
                print(f"TESSDATA_PREFIX configurado en: {tessdata_dir}")
                return True
        except Exception as e:
            print(f"Error al configurar Tesseract: {str(e)}")
    
    print("No se pudo encontrar Tesseract en la ruta especificada")
    return False

# Intentar configurar Tesseract al importar el módulo
if not configurar_tesseract():
    print("ADVERTENCIA: Tesseract OCR no está instalado o no se encuentra en la ruta especificada.")
    print("Por favor, instale Tesseract OCR desde: https://github.com/UB-Mannheim/tesseract/wiki")
    print("Asegúrese de que esté instalado en: C:\\Program Files\\Tesseract-OCR")

def preprocesar_imagen(ruta_imagen):
    """
    Preprocesa la imagen para mejorar la extracción de texto
    """
    try:
        # Leer la imagen
        imagen = cv2.imread(ruta_imagen)
        if imagen is None:
            raise ValueError("No se pudo leer la imagen")

        # Convertir a escala de grises
        gris = cv2.cvtColor(imagen, cv2.COLOR_BGR2GRAY)

        # Aplicar umbral adaptativo
        umbral = cv2.adaptiveThreshold(
            gris, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
            cv2.THRESH_BINARY, 11, 2
        )

        # Reducir ruido
        denoised = cv2.fastNlMeansDenoising(umbral)

        return denoised
    except Exception as e:
        raise ValueError(f"Error en el preprocesamiento de la imagen: {str(e)}")

def extraer_texto(imagen):
    """
    Extrae el texto de la imagen usando Tesseract OCR
    """
    try:
        # Verificar que Tesseract esté configurado
        if not configurar_tesseract():
            raise ValueError(
                "Tesseract no está instalado o no se encuentra en el PATH. "
                "Por favor, instale Tesseract OCR desde: "
                "https://github.com/UB-Mannheim/tesseract/wiki"
            )
        
        # Configurar Tesseract
        config = '--psm 6 --oem 3'
        
        # Extraer texto
        texto = pytesseract.image_to_string(imagen, config=config)
        
        if not texto.strip():
            raise ValueError("No se pudo extraer texto de la imagen")
            
        return texto
    except Exception as e:
        raise ValueError(f"Error al extraer texto: {str(e)}")

def extraer_datos_factura(texto):
    """
    Extrae los datos relevantes de la factura del texto
    """
    datos = {
        'numero': None,
        'fecha': None,
        'cliente': None,
        'cuit': None,
        'monto_total': None
    }
    
    # Patrones para buscar información
    patrones = {
        'numero': r'Factura\s*[A-Z]\s*(\d+)',
        'fecha': r'(\d{2}/\d{2}/\d{4})',
        'cuit': r'CUIT:\s*(\d{2}-\d{8}-\d{1})',
        'monto_total': r'Total:\s*\$?\s*(\d+[.,]\d{2})'
    }
    
    # Buscar cada patrón en el texto
    for campo, patron in patrones.items():
        match = re.search(patron, texto)
        if match:
            datos[campo] = match.group(1)
    
    return datos

def detectar_tipo_factura(texto):
    """
    Detecta el tipo de factura basado en el texto extraído
    """
    texto = texto.lower()
    
    # Patrones para identificar el tipo de factura
    patrones = {
        'A': [
            r'factura\s+a',
            r'tipo\s+a',
            r'comprobante\s+a'
        ],
        'B': [
            r'factura\s+b',
            r'tipo\s+b',
            r'comprobante\s+b'
        ],
        'C': [
            r'factura\s+c',
            r'tipo\s+c',
            r'comprobante\s+c'
        ]
    }
    
    # Buscar coincidencias
    for tipo, lista_patrones in patrones.items():
        for patron in lista_patrones:
            if re.search(patron, texto):
                return tipo
    
    # Si no se encuentra un tipo específico, intentar detectar por otros patrones
    if re.search(r'iva\s+responsable\s+inscripto', texto):
        return 'A'
    elif re.search(r'iva\s+responsable\s+no\s+inscripto', texto):
        return 'B'
    elif re.search(r'iva\s+exento', texto):
        return 'C'
    
    # Si no se puede determinar, devolver None
    return None

def procesar_factura(ruta_imagen):
    """
    Procesa una imagen de factura y extrae la información relevante
    """
    try:
        # Verificar que el archivo existe y es accesible
        if not os.path.exists(ruta_imagen):
            raise ValueError(f"No se encontró el archivo: {ruta_imagen}")
        
        # Verificar permisos de lectura
        if not os.access(ruta_imagen, os.R_OK):
            raise ValueError(f"No hay permisos de lectura para el archivo: {ruta_imagen}")

        # Leer la imagen
        imagen = cv2.imread(ruta_imagen)
        if imagen is None:
            raise ValueError("No se pudo leer la imagen")

        # Convertir a escala de grises
        gris = cv2.cvtColor(imagen, cv2.COLOR_BGR2GRAY)

        # Aplicar umbral adaptativo
        umbral = cv2.adaptiveThreshold(
            gris, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
        )

        # Verificar que Tesseract está configurado
        if not configurar_tesseract():
            raise ValueError("Tesseract no está configurado correctamente")

        # Extraer texto con manejo de errores específico
        try:
            texto = pytesseract.image_to_string(umbral, lang='spa')
        except Exception as e:
            raise ValueError(f"Error al extraer texto con Tesseract: {str(e)}")

        if not texto.strip():
            raise ValueError("No se pudo extraer texto de la imagen")

        # Detectar tipo de factura
        tipo = detectar_tipo_factura(texto)

        # Extraer información usando expresiones regulares
        numero = re.search(r'factura\s+n[°º]\s*:?\s*(\d+)', texto, re.IGNORECASE)
        fecha = re.search(r'fecha\s*:?\s*(\d{1,2}/\d{1,2}/\d{2,4})', texto, re.IGNORECASE)
        cliente = re.search(r'cliente\s*:?\s*([^\n]+)', texto, re.IGNORECASE)
        cuit = re.search(r'cuit\s*:?\s*(\d{2}-\d{8}-\d{1})', texto, re.IGNORECASE)
        monto = re.search(r'total\s*:?\s*\$?\s*(\d+[.,]\d{2})', texto, re.IGNORECASE)

        # Crear diccionario con los datos extraídos
        datos = {
            'tipo': tipo,
            'numero': numero.group(1) if numero else '',
            'fecha': fecha.group(1) if fecha else '',
            'cliente': cliente.group(1).strip() if cliente else '',
            'cuit': cuit.group(1) if cuit else '',
            'monto_total': monto.group(1) if monto else ''
        }

        return datos

    except Exception as e:
        raise Exception(f"Error al procesar la factura: {str(e)}")
    finally:
        # Limpiar recursos
        if 'imagen' in locals():
            del imagen
        if 'gris' in locals():
            del gris
        if 'umbral' in locals():
            del umbral 