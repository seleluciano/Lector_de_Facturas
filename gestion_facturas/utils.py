import cv2
import numpy as np
import pytesseract
from PIL import Image
import re
import os

# Configurar la ruta de Tesseract
if os.name == 'nt':  # Windows
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

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
        # Verificar que Tesseract esté instalado
        if not os.path.exists(pytesseract.pytesseract.tesseract_cmd):
            raise ValueError(
                "Tesseract no está instalado o no se encuentra en la ruta especificada. "
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

def procesar_factura(ruta_imagen):
    """
    Procesa una factura completa y retorna los datos extraídos
    """
    try:
        # Preprocesar la imagen
        imagen_procesada = preprocesar_imagen(ruta_imagen)
        
        # Extraer texto
        texto = extraer_texto(imagen_procesada)
        
        # Extraer datos
        datos = extraer_datos_factura(texto)
        
        return datos
    except Exception as e:
        raise ValueError(f"Error al procesar la factura: {str(e)}") 