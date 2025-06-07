import cv2
import numpy as np
import pytesseract
from PIL import Image
import re
import os
import sys
from pdf2image import convert_from_path
import tempfile
import uuid

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

def preprocesar_imagen(imagen):
    """
    Preprocesa la imagen para mejorar la extracción de texto
    """
    try:
        print(f"Dimensiones de la imagen: {imagen.shape}")

        # Convertir a escala de grises
        gris = cv2.cvtColor(imagen, cv2.COLOR_BGR2GRAY)
        print("Imagen convertida a escala de grises")

        # Aplicar umbral adaptativo
        umbral = cv2.adaptiveThreshold(
            gris, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
            cv2.THRESH_BINARY, 11, 2
        )
        print("Umbral adaptativo aplicado")

        # Reducir ruido
        denoised = cv2.fastNlMeansDenoising(umbral)
        print("Ruido reducido")

        # Aumentar el contraste
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
        contraste = clahe.apply(gris)
        print("Contraste aumentado")

        # Combinar resultados
        resultado = cv2.bitwise_and(denoised, contraste)
        print("Resultados combinados")

        # Escalar la imagen si es muy pequeña
        height, width = resultado.shape
        if width < 1000:
            scale = 1000 / width
            resultado = cv2.resize(resultado, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
            print(f"Imagen escalada a {resultado.shape}")

        # Asegurarse de que la imagen sea del tipo correcto
        if resultado.dtype != np.uint8:
            print("Convirtiendo resultado final a uint8")
            resultado = (resultado * 255).astype(np.uint8)

        print(f"Tipo final de la imagen: {resultado.dtype}")
        print(f"Forma final de la imagen: {resultado.shape}")
        
        return resultado
    except Exception as e:
        print(f"Error detallado en preprocesamiento: {str(e)}")
        raise ValueError(f"Error en el preprocesamiento de la imagen: {str(e)}")

def extraer_texto(imagen):
    """
    Extrae el texto de una imagen usando Tesseract OCR
    """
    try:
        # Configurar Tesseract
        configurar_tesseract()
        
        # Convertir la imagen a formato PIL
        if isinstance(imagen, np.ndarray):
            imagen_pil = Image.fromarray(cv2.cvtColor(imagen, cv2.COLOR_BGR2RGB))
        else:
            imagen_pil = imagen
            
        # Realizar OCR
        texto = pytesseract.image_to_string(imagen_pil, lang='spa')
        return texto.strip()
    except Exception as e:
        print(f"Error en extraer_texto: {str(e)}")
        raise

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
        'numero': [
            r'Factura\s*[A-Z]\s*(\d+)',
            r'Comp\.\s*[A-Z]\s*(\d+)',
            r'[A-Z]\s*(\d{8})'
        ],
        'fecha': [
            r'(\d{2}/\d{2}/\d{4})',
            r'(\d{2}-\d{2}-\d{4})',
            r'(\d{2}\.\d{2}\.\d{4})'
        ],
        'cuit': [
            r'CUIT:\s*(\d{2}-\d{8}-\d{1})',
            r'CUIT\s*(\d{2}-\d{8}-\d{1})',
            r'(\d{2}-\d{8}-\d{1})'
        ],
        'monto_total': [
            r'Total:\s*\$?\s*(\d+[.,]\d{2})',
            r'Importe\s*Total:\s*\$?\s*(\d+[.,]\d{2})',
            r'Total\s*Neto:\s*\$?\s*(\d+[.,]\d{2})'
        ]
    }
    
    # Buscar cada patrón en el texto
    for campo, lista_patrones in patrones.items():
        for patron in lista_patrones:
            match = re.search(patron, texto)
            if match:
                datos[campo] = match.group(1)
                break
    
    print("Datos extraídos:", datos)  # Debug
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

def convertir_pdf_a_imagen(ruta_pdf):
    """
    Convierte la primera página de un PDF a una imagen
    """
    try:
        # Convertir PDF a imagen
        imagenes = convert_from_path(ruta_pdf, first_page=1, last_page=1)
        if not imagenes:
            raise ValueError("No se pudo convertir el PDF a imagen")
        
        # Guardar la imagen temporalmente
        temp_dir = tempfile.gettempdir()
        temp_path = os.path.join(temp_dir, f"temp_pdf_{uuid.uuid4()}.png")
        imagenes[0].save(temp_path, 'PNG')
        
        return temp_path
    except Exception as e:
        raise ValueError(f"Error al convertir PDF a imagen: {str(e)}")

def procesar_factura(imagen):
    """
    Procesa una factura y extrae la información relevante directamente de la imagen original
    """
    try:
        print(f"Procesando imagen de dimensiones: {imagen.shape}")
        
        # Extraer texto directamente de la imagen original
        texto = extraer_texto(imagen)
        print("Texto extraído:", texto)  # Debug
        
        # Extraer datos
        datos = extraer_datos_factura(texto)
        
        # Detectar tipo de factura
        tipo = detectar_tipo_factura(texto)
        datos['tipo'] = tipo
        
        return datos
    except Exception as e:
        print(f"Error en procesar_factura: {str(e)}")
        raise 