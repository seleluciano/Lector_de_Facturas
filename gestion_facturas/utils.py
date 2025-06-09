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
    print("Y asegúrese de que esté instalado en: C:\\Program Files\\Tesseract-OCR")

def detectar_esquinas(imagen):
    """
    Detecta las esquinas de la factura usando detección de bordes y contornos
    """
    # Convertir a escala de grises
    gris = cv2.cvtColor(imagen, cv2.COLOR_BGR2GRAY)
    
    # Aplicar desenfoque gaussiano para reducir ruido
    blur = cv2.GaussianBlur(gris, (5, 5), 0)
    
    # Detectar bordes usando Canny
    bordes = cv2.Canny(blur, 75, 200)
    
    # Dilatar los bordes para conectar líneas discontinuas
    kernel = np.ones((5,5), np.uint8)
    bordes = cv2.dilate(bordes, kernel, iterations=1)
    
    # Encontrar contornos
    contornos, _ = cv2.findContours(bordes, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    # Encontrar el contorno más grande (asumiendo que es la factura)
    if not contornos:
        return None
    
    contorno_factura = max(contornos, key=cv2.contourArea)
    
    # Aproximar el contorno a un polígono
    epsilon = 0.02 * cv2.arcLength(contorno_factura, True)
    aprox = cv2.approxPolyDP(contorno_factura, epsilon, True)
    
    # Si encontramos 4 puntos, asumimos que es la factura
    if len(aprox) == 4:
        return aprox.reshape(4, 2)
    
    return None

def ordenar_puntos(puntos):
    """
    Ordena los puntos en el orden: [top-left, top-right, bottom-right, bottom-left]
    """
    rect = np.zeros((4, 2), dtype=np.float32)
    
    # Suma de coordenadas
    s = puntos.sum(axis=1)
    rect[0] = puntos[np.argmin(s)]  # Top-left
    rect[2] = puntos[np.argmax(s)]  # Bottom-right
    
    # Diferencia de coordenadas
    diff = np.diff(puntos, axis=1)
    rect[1] = puntos[np.argmin(diff)]  # Top-right
    rect[3] = puntos[np.argmax(diff)]  # Bottom-left
    
    return rect

def corregir_perspectiva(imagen, puntos):
    """
    Corrige la perspectiva de la imagen usando los puntos detectados
    """
    # Ordenar puntos
    rect = ordenar_puntos(puntos)
    
    # Calcular dimensiones del nuevo rectángulo
    width = max(
        np.linalg.norm(rect[0] - rect[1]),
        np.linalg.norm(rect[2] - rect[3])
    )
    height = max(
        np.linalg.norm(rect[0] - rect[3]),
        np.linalg.norm(rect[1] - rect[2])
    )
    
    # Puntos de destino
    dst = np.array([
        [0, 0],
        [width - 1, 0],
        [width - 1, height - 1],
        [0, height - 1]
    ], dtype=np.float32)
    
    # Calcular matriz de transformación
    M = cv2.getPerspectiveTransform(rect, dst)
    
    # Aplicar transformación
    corregida = cv2.warpPerspective(imagen, M, (int(width), int(height)))
    
    return corregida

def mejorar_contraste(imagen):
    """
    Mejora el contraste de la imagen usando CLAHE y ajuste de brillo
    """
    # Convertir a escala de grises
    gris = cv2.cvtColor(imagen, cv2.COLOR_BGR2GRAY)
    
    # Aplicar CLAHE
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
    contraste = clahe.apply(gris)
    
    # Ajustar brillo
    alpha = 1.2  # Contraste
    beta = 10    # Brillo
    ajustada = cv2.convertScaleAbs(contraste, alpha=alpha, beta=beta)
    
    return ajustada

def preprocesar_imagen(imagen):
    """
    Preprocesa la imagen para mejorar la extracción de texto, similar a CamScanner
    """
    try:
        print(f"Dimensiones de la imagen: {imagen.shape}")
        
        # Convertir a escala de grises
        gris = cv2.cvtColor(imagen, cv2.COLOR_BGR2GRAY)
        print("Imagen convertida a escala de grises")
        
        # Detectar bordes
        bordes = cv2.Canny(gris, 75, 200)
        print("Bordes detectados")
        
        # Dilatar los bordes para conectar líneas discontinuas
        kernel = np.ones((5,5), np.uint8)
        bordes = cv2.dilate(bordes, kernel, iterations=1)
        
        # Encontrar contornos
        contornos, _ = cv2.findContours(bordes, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # Encontrar el contorno más grande (asumiendo que es la factura)
        if contornos:
            contorno_factura = max(contornos, key=cv2.contourArea)
            
            # Aproximar el contorno a un polígono
            epsilon = 0.02 * cv2.arcLength(contorno_factura, True)
            aprox = cv2.approxPolyDP(contorno_factura, epsilon, True)
            
            # Si encontramos 4 puntos, corregir la perspectiva
            if len(aprox) == 4:
                puntos = aprox.reshape(4, 2)
                
                # Ordenar puntos
                rect = np.zeros((4, 2), dtype=np.float32)
                s = puntos.sum(axis=1)
                rect[0] = puntos[np.argmin(s)]  # Top-left
                rect[2] = puntos[np.argmax(s)]  # Bottom-right
                diff = np.diff(puntos, axis=1)
                rect[1] = puntos[np.argmin(diff)]  # Top-right
                rect[3] = puntos[np.argmax(diff)]  # Bottom-left
                
                # Calcular dimensiones
                width = max(
                    np.linalg.norm(rect[0] - rect[1]),
                    np.linalg.norm(rect[2] - rect[3])
                )
                height = max(
                    np.linalg.norm(rect[0] - rect[3]),
                    np.linalg.norm(rect[1] - rect[2])
                )
                
                # Puntos de destino
                dst = np.array([
                    [0, 0],
                    [width - 1, 0],
                    [width - 1, height - 1],
                    [0, height - 1]
                ], dtype=np.float32)
                
                # Transformar perspectiva
                M = cv2.getPerspectiveTransform(rect, dst)
                imagen = cv2.warpPerspective(imagen, M, (int(width), int(height)))
                print("Perspectiva corregida")
        
        # Mejorar contraste usando CLAHE
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
        contraste = clahe.apply(gris)
        print("Contraste mejorado")
        
        # Ajustar brillo y contraste
        alpha = 1.2  # Contraste
        beta = 10    # Brillo
        ajustada = cv2.convertScaleAbs(contraste, alpha=alpha, beta=beta)
        print("Brillo y contraste ajustados")
        
        # Reducir ruido
        denoised = cv2.fastNlMeansDenoising(ajustada, None, 10, 7, 21)
        print("Ruido reducido")
        
        # Aplicar umbral adaptativo
        umbral = cv2.adaptiveThreshold(
            denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
            cv2.THRESH_BINARY, 11, 2
        )
        print("Umbral adaptativo aplicado")
        
        # Escalar la imagen si es muy pequeña
        height, width = umbral.shape
        if width < 1000:
            scale = 1000 / width
            umbral = cv2.resize(umbral, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
            print(f"Imagen escalada a {umbral.shape}")
        
        print(f"Tipo final de la imagen: {umbral.dtype}")
        print(f"Forma final de la imagen: {umbral.shape}")
        
        return umbral
        
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
        'numero': 0,
        'punto_venta': 0,
        'fecha': None,
        'cuit': None,
        'cuit_emisor': None,
        'razon_social_emisor': None,
        'tipo_factura': None,
        'condicion_venta': None,
        'condicion_iva': None,
        'subtotal': 0,
        'iva': 0,
        'percepcion_iibb': 0,
        'monto_total': 0,
        'tipo_copia': None,
        'razon_social_cliente': None,
        'productos': []
    }

    # Patrón flexible para números monetarios (con o sin separador de miles, con coma o punto decimal)
    patron_valor_numerico = r'(\d{1,3}(?:\.\d{3})*(?:,\d+)?)'

    # Patrones para buscar información
    patrones = {
        'punto_venta': [
            r'Punto\s*de\s*Venta(?:\s*|\s*:\s*)(\d{4})',
            r'PV\s*:\s*(\d{4})'
        ],
        'numero': [
            r'Nro(?:\.|s)?:?\s*(\d{8})',
            r'Comp(?:\.|s)?\s*Nro(?:\.|s)?:?\s*(\d{8})',
            r'(\d{8})'
        ],
        'fecha': [
            r'(\d{2}[/\-]\d{2}[/\-]\d{4})',
            r'(\d{2}\.\d{2}\.\d{4})'
        ],
        'cuit_cliente': [
            r'(?:CUIT|CUIL|DNI)\s*[.:\s]*(\d{2}[-\s]?\d{8}[-\s]?\d{1})',
            r'DNI:\s*(\d{2}[-\s]?\d{8}[-\s]?\d{1})'
        ],
        'cuit_emisor': [
            r'Domicilio\s*Comercial:[^\n]*CUIT:\s*(\d{2}[-\s]?\d{8}[-\s]?\d{1})',  # Patrón específico para el formato de la factura
            r'CUIT:\s*(\d{2}[-\s]?\d{8}[-\s]?\d{1})',  # Patrón general para CUIT
            r'(?:CUIT|CUIL)\s*(?:Emisor|Vendedor|Empresa)[.:\s]*(\d{2}[-\s]?\d{8}[-\s]?\d{1})',
            r'(?:CUIT|CUIL)\s*[.:\s]*(\d{2}[-\s]?\d{8}[-\s]?\d{1})',
            r'Raz[oó]n\s*Social[^\n]*CUIT:\s*(\d{2}[-\s]?\d{8}[-\s]?\d{1})',  # Patrón para cuando el CUIT está después de la razón social
            r'Global\s*Networks[^\n]*CUIT:\s*(\d{2}[-\s]?\d{8}[-\s]?\d{1})'  # Patrón específico para esta factura
        ],
        'razon_social_emisor': [
            r'(?:Raz[oó]n\s*Social|Denominaci[oó]n|Empresa|Vendedor)\s*(?:Emisor|Vendedor|Empresa)[.:\s]*([^\n]+?)(?:\s*Fecha|$)',  # Se detiene en "Fecha" o fin de línea
            r'(?:Raz[oó]n\s*Social|Denominaci[oó]n|Empresa|Vendedor)[.:\s]*([^\n]+?)(?:\s*Fecha|$)',  # Se detiene en "Fecha" o fin de línea
            r'Raz[oó]n\s*Soclal:\s*([^\n]+?)(?:\s*Fecha|$)',  # Se detiene en "Fecha" o fin de línea
            r'Emisor[.:\s]*([^\n]+?)(?:\s*Fecha|$)',  # Se detiene en "Fecha" o fin de línea
            r'Vendedor[.:\s]*([^\n]+?)(?:\s*Fecha|$)',  # Se detiene en "Fecha" o fin de línea
            r'Empresa[.:\s]*([^\n]+?)(?:\s*Fecha|$)'  # Se detiene en "Fecha" o fin de línea
        ],
        'monto_total': [
            rf'Importe\s*Total:\s*\$?\s*{patron_valor_numerico}',
            rf'Total:\s*\$?\s*{patron_valor_numerico}',
            rf'Total\s*Factura:\s*\$?\s*{patron_valor_numerico}',
            rf'Total\s*Final:\s*\$?\s*{patron_valor_numerico}',
            rf'Total\s*a\s*Pagar:\s*\$?\s*{patron_valor_numerico}',
            rf'Total\s*C\$\s*I\.V\.A\.:\s*\$?\s*{patron_valor_numerico}'
        ],
        'subtotal': [
            rf'Subtotal:\s*\$?\s*{patron_valor_numerico}',
            rf'Neto\s*Gravado:\s*\$?\s*{patron_valor_numerico}',
            rf'Subtotal\s*Neto:\s*\$?\s*{patron_valor_numerico}',
            rf'Importe\s*Neto:\s*\$?\s*{patron_valor_numerico}',
            rf'Neto:\s*\$?\s*{patron_valor_numerico}'
        ],
        'iva': [
            rf'IVA\s*(?:\d+%?)?:\s*\$?\s*{patron_valor_numerico}',
            rf'IVA:\s*\$?\s*{patron_valor_numerico}',
            rf'Impuesto\s*IVA:\s*\$?\s*{patron_valor_numerico}',
            rf'I\.V\.A\. ?:?\s*\$?\s*{patron_valor_numerico}',
            rf'IVA\s*Discriminado:\s*\$?\s*{patron_valor_numerico}',
            rf'IVA\s*Inscripto:\s*\$?\s*{patron_valor_numerico}',
            rf'NA:\s*\$?\s*{patron_valor_numerico}'  # Para el caso específico de "NA: $7.639,80"
        ],
        'percepcion_iibb': [
            rf'Percepci[oó]n\s*IIBB:\s*\$?\s*{patron_valor_numerico}',
            rf'IIBB:\s*\$?\s*{patron_valor_numerico}',
            rf'IIBB\s*(?:\d+%?)?:\s*\$?\s*{patron_valor_numerico}',
            rf'Percepci[oó]n\s*Ingresos\s*Brutos:\s*\$?\s*{patron_valor_numerico}',
            rf'Percepci[oó]n\s*IB:\s*\$?\s*{patron_valor_numerico}',
            rf'Percepci[oó]n\s*!IBB:\s*\$?\s*{patron_valor_numerico}'  # Para el caso específico de "Percepción !IBB"
        ],
        'otros_tributos': [
            rf'Otros\s*Tributos:\s*\$?\s*{patron_valor_numerico}',
            rf'Otros\s*Impuestos:\s*\$?\s*{patron_valor_numerico}',
            rf'Otros:\s*\$?\s*{patron_valor_numerico}',
            rf'Total\s*Otros\s*Tributos:\s*\$?\s*{patron_valor_numerico}',
            rf'Importe\s*Otros\s*Tributos:\s*\$?\s*{patron_valor_numerico}'
        ],
        'condicion_venta': [
            r'Condici[oó]n\s*(?:de\s*)?Venta:\s*([^\n]+)',
            r'Forma\s*de\s*Pago:\s*([^\n]+)',
            r'Congici[oó]n\s*de\s*venta:\s*([^\n]+)'  # Para el caso específico de "Congición de venta"
        ],
        'condicion_iva': [
            r'Condici[oó]n\s*IVA:\s*([^\n]+)',
            r'Condici[oó]n\s*frente\s*al\s*IVA:\s*([^\n]+)',
            r'Condici[oó]n\s*frente\s*al\s*A:\s*([^\n]+)'  # Para el caso específico de "Condición frente al A"
        ],
        'tipo_copia': [
            r'(Original|Duplicado)',
            r'Copia\s*(Original|Duplicado)'
        ],
        'razon_social_cliente': [
            r'(?:Raz[oó]n\s*Social|Cliente|Denominaci[oó]n|Nombre\s*o\s*Raz[oó]n\s*Social)[.:\s]*([^\n]+)',
            r'Apellido\s*y\s*Nombra\s*/\s*Raz[oó]n\s*Soclal:\s*([^\n]+)'  # Para el caso específico de "Apellido y Nombra / Razón Soclal"
        ]
    }

    # Buscar cada patrón en el texto
    for campo, lista_patrones in patrones.items():
        # Priorizar los patrones más específicos o completos
        for patron in lista_patrones:
            if campo == 'cuit_cliente':
                # Buscar todos los CUITs en el texto
                matches = list(re.finditer(patron, texto, re.IGNORECASE))
                if len(matches) >= 2:
                    # Tomar el segundo CUIT encontrado (asumiendo que el primero es el de la empresa)
                    datos['cuit'] = matches[1].group(1)
                break
            elif campo == 'cuit_emisor':
                # Buscar el CUIT del emisor
                matches = list(re.finditer(patron, texto, re.IGNORECASE))
                if matches:
                    datos['cuit_emisor'] = matches[0].group(1)
                break
            else:
                match = re.search(patron, texto, re.IGNORECASE)
                if match:
                    # Lógica específica para campos con grupos múltiples o nombres diferentes
                    if campo == 'punto_venta':
                         datos['punto_venta'] = match.group(1)
                    elif campo == 'numero':
                         datos['numero'] = match.group(1)
                    elif campo in ['iva', 'percepcion_iibb', 'monto_total', 'subtotal', 'otros_tributos']:
                        valor_str = match.group(len(match.groups()))
                        # Mejorar la limpieza del valor numérico
                        valor_limpio = re.sub(r'[^\d.,]', '', valor_str)
                        
                        # Manejar diferentes formatos de números
                        if ',' in valor_limpio and '.' in valor_limpio:
                            # Si hay ambos separadores, determinar cuál es el decimal
                            if valor_limpio.rfind('.') > valor_limpio.rfind(','):
                                valor_limpio = valor_limpio.replace(',', '')
                            else:
                                valor_limpio = valor_limpio.replace('.', '')
                                valor_limpio = valor_limpio.replace(',', '.')
                        elif ',' in valor_limpio:
                            valor_limpio = valor_limpio.replace(',', '.')
                        
                        try:
                            valor_float = float(valor_limpio)
                            datos[campo] = valor_float
                        except ValueError:
                            print(f"Advertencia: No se pudo convertir a float el valor extraído para {campo}: {valor_str} (limpiado a {valor_limpio})")
                            datos[campo] = 0
                    else:
                        datos[campo] = match.group(1)
                    break

    datos['tipo_factura'] = detectar_tipo_factura(texto)

    productos = extraer_productos(texto)
    if productos:
        datos['productos'] = productos

    print("Datos extraídos:", datos)  # Debug
    return datos

def extraer_productos(texto):
    """
    Extrae la información de los productos de la factura línea por línea.
    """
    # Patrón más flexible para cantidades (puede tener decimales)
    patron_cantidad = r'(\d+[.,]?\d*)'

    # Patrón flexible para números monetarios (el mismo que usamos arriba)
    # Captura el número completo en el grupo 1 (ej. '1234.56')
    # Importante: Este patrón ya define su propio grupo de captura (\d{1,3}...), 
    # así que cuando lo usemos dentro de otro patrón, el grupo capturado será el de este patrón.
    patron_valor_numerico = r'(\d{1,3}(?:\.\d{3})*(?:,\d+)?)'

    # Patrón para porcentajes (ej. 19%, 7%)
    patron_porcentaje = r'(\d+%?)'

    # Palabras clave a ignorar en las líneas de productos (totales, encabezados, etc.)
    palabras_ignorar_productos = [] # Se eliminan todas las palabras ignoradas

    # Nota: Usamos r'...' para evitar problemas con backslashes en regex.
    patron_linea_producto = re.compile(
        rf'^\s*(?:\d+)?\s*'  # Optional leading number (e.g., product code/line number)
        rf'{patron_cantidad}\s*'  # Group 1: Cantidad
        rf'(.+?)\s*'  # Group 2: Descripción (non-greedy to allow for spaces)
        rf'(\S+)?\s*'  # Group 3: U. Medida (optional, non-whitespace chars)
        rf'\$?\s*{patron_valor_numerico}\s*'  # Group 4: Precio Unitario
        rf'{patron_porcentaje}?\s*'  # Group 5: % Bonf. (optional)
        rf'\$?\s*{patron_valor_numerico}?\s*'  # Group 6: Imp. Bonf. (optional)
        rf'\$?\s*{patron_valor_numerico}\s*$',  # Group 7: Subtotal
        re.IGNORECASE
    )

    productos = []
    lineas = texto.split('\n')

    for linea in lineas:
        linea_limpia = linea.strip()

        # Ignorar líneas que contienen palabras clave de totales o encabezados
        if any(palabra.lower() in linea_limpia.lower() for palabra in palabras_ignorar_productos):
            continue

        match = patron_linea_producto.search(linea_limpia) # Buscar en la línea limpia
        if match:
            try:
                # Acceder a los grupos capturados (ajustados para el nuevo patrón):
                cantidad_str = match.group(1)
                descripcion = match.group(2).strip()
                unidad_medida = match.group(3).strip() if match.group(3) else '' # Nuevo campo
                precio_unitario_str = match.group(4)
                bonf_porcentaje_str = match.group(5) # Nuevo campo
                importe_bonificado_str = match.group(6)
                subtotal_str = match.group(7)

                # Extraer la cantidad de la descripción (último número)
                cantidad_descripcion = None
                palabras_descripcion = descripcion.split()
                if palabras_descripcion:
                    ultima_palabra = palabras_descripcion[-1]
                    if re.match(r'\d+[.,]?\d*$', ultima_palabra):
                        cantidad_descripcion = float(ultima_palabra.replace(',', '.'))
                        # Remover la cantidad de la descripción
                        descripcion = ' '.join(palabras_descripcion[:-1])

                # Usar la cantidad de la descripción si existe, sino usar la cantidad original
                cantidad = cantidad_descripcion if cantidad_descripcion is not None else float(cantidad_str.replace(',', '.')) if cantidad_str else 0.0

                # Función auxiliar para limpiar y convertir valores monetarios con formato argentino (miles con . y decimal con ,)
                def limpiar_y_convertir_moneda(valor_str):
                    if not valor_str: return 0.0
                    # Eliminar puntos de miles, reemplazar coma decimal por punto
                    valor_limpio = valor_str.replace('.', '').replace(',', '.')
                    try:
                        return float(valor_limpio)
                    except ValueError:
                        return 0.0

                precio_unitario = limpiar_y_convertir_moneda(precio_unitario_str)
                importe_bonificado = limpiar_y_convertir_moneda(importe_bonificado_str)
                subtotal = limpiar_y_convertir_moneda(subtotal_str)
                
                # Convertir porcentaje, eliminando el '%' si existe
                bonificacion_porcentaje = float(bonf_porcentaje_str.replace('%', '').replace(',', '.')) if bonf_porcentaje_str else 0.0

                productos.append({
                    'cantidad': cantidad,
                    'descripcion': descripcion,
                    'unidad_medida': unidad_medida,
                    'precio_unitario': precio_unitario,
                    'porcentaje_bonificacion': bonificacion_porcentaje,
                    'importe_bonificado': importe_bonificado,
                    'subtotal': subtotal,
                })
                print(f"Producto extraído: {productos[-1]}") # Debug

            except ValueError as e:
                print(f"Advertencia: No se pudo parsear los valores numéricos en la línea de producto \'{linea_limpia}\': {e}") # Debug
                continue # Saltar si hay error de parseo
            except IndexError as e:
                 print(f"Advertencia: Patrón de producto no encontró todos los grupos esperados en la línea \'{linea_limpia}\': {e}. Grupos encontrados: {match.groups()}") # Debug
                 continue # Saltar si el patrón no coincide completamente con la estructura esperada
            except Exception as e:
                 print(f"Advertencia: Error inesperado al procesar línea de producto \'{linea_limpia}\': {e}") # Debug
                 continue

    return productos

def detectar_tipo_factura(texto):
    """
    Detecta el tipo de factura basado en el texto extraído
    """
    # Buscar en las primeras líneas del texto
    lineas = texto.split('\n')
    for i in range(min(3, len(lineas))):  # Buscar en las primeras 3 líneas
        linea = lineas[i].strip()
        
        # Patrones específicos para el tipo de factura
        if re.search(r'^A\s*\|', linea, re.IGNORECASE) or re.search(r'^A\s*\|.*FACTURA', linea, re.IGNORECASE):
            return 'A'
        if re.search(r'^B\s*\|', linea, re.IGNORECASE) or re.search(r'^B\s*\|.*FACTURA', linea, re.IGNORECASE):
            return 'B'
        if re.search(r'^C\s*\|', linea, re.IGNORECASE) or re.search(r'^C\s*\|.*FACTURA', linea, re.IGNORECASE):
            return 'C'
    
    # Si no se encuentra en las primeras líneas, buscamos en todo el texto
    texto = texto.lower()

    # Patrones para identificar el tipo de factura
    patrones = {
        'A': [
            r'factura(?:\s+|\s*[\\s\\W]*)\bA\b', # Matches 'factura A', 'factura   A', 'factura (A)' etc.
            r'tipo(?:\s+|\s*[\\s\\W]*)\bA\b',
            r'comprobante(?:\s+|\s*[\\s\\W]*)\bA\b',
            r'iva\s*responsable\s*inscripto',
            r'^A\s*\|',  # Para el caso específico de "A | FACTURA"
            r'^A\s*\|.*FACTURA'  # Para el caso específico de "A | FACTURA"
        ],
        'B': [
            r'factura(?:\s+|\s*[\\s\\W]*)\bB\b',
            r'tipo(?:\s+|\s*[\\s\\W]*)\bB\b',
            r'comprobante(?:\s+|\s*[\\s\\W]*)\bB\b',
            r'iva\s*responsable\s*no\s*inscripto'
        ],
        'C': [
            r'factura(?:\s+|\s*[\\s\\W]*)\bC\b',
            r'tipo(?:\s+|\s*[\\s\\W]*)\bC\b',
            r'comprobante(?:\s+|\s*[\\s\\W]*)\bC\b',
            r'iva\s*exento'
        ]
    }

    # Buscar coincidencias
    for tipo, lista_patrones in patrones.items():
        for patron in lista_patrones:
            if re.search(patron, texto):
                return tipo

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
    Procesa una imagen de factura para extraer sus datos relevantes.
    """
    try:
        # Preprocesar la imagen
        imagen_procesada = preprocesar_imagen(imagen)
        
        # Extraer texto
        texto = extraer_texto(imagen_procesada)
        
        # Extraer datos
        datos = extraer_datos_factura(texto)
        
        # Detectar tipo de factura
        tipo = detectar_tipo_factura(texto)
        datos['tipo_factura'] = tipo
        
        return datos
        
    except Exception as e:
        print(f"Error en procesar_factura: {str(e)}")
        raise 