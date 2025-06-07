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
        'punto_venta': None,
        'fecha': None,
        'cuit': None,
        'monto_total': None,
        'tipo_factura': None,
        'condicion_venta': None,
        'condicion_iva': None,
        'subtotal': None,
        'iva': None,
        'percepcion_iibb': None,
        'tipo_copia': None,
        'razon_social_cliente': None,
        'productos': []
    }

    # Patrón flexible para números monetarios (con o sin separador de miles, con coma o punto decimal)
    # Captura el número completo en el grupo 1
    patron_valor_numerico = r'(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d+)?)'

    # Patrones para buscar información
    patrones = {
        'numero_completo': [
            r'[A-Z]\s*(\d{4})-(\d{8})',  # Formato: A 0001-12345678
            r'[A-Z]\s*(\d{4})\s*-\s*(\d{8})',
            r'[A-Z]\s*(\d{4})[^\d]*(\d{8})'
        ],
        'fecha': [
            r'(\d{2}/\d{2}/\d{4})',
            r'(\d{2}-\d{2}-\d{4})',
            r'(\d{2}\.\d{2}\.\d{4})'
        ],
        'cuit_cliente': [
            r'CUIT\s*Cliente:\s*(\d{2}-\d{8}-\d{1})',
            r'CUIT\s*del\s*Cliente:\s*(\d{2}-\d{8}-\d{1})',
            r'CUIT\s*Comprador:\s*(\d{2}-\d{8}-\d{1})',
            r'CUIT\s*:\s*(\d{2}-\d{8}-\d{1})' # Agregar patrón CUIT general por si no dice Cliente/Comprador
        ],
        'monto_total': [
            rf'Importe\s*Total:\s*\$?\s*{patron_valor_numerico}',
            rf'Total:\s*\$?\s*{patron_valor_numerico}',
        ],
        'subtotal': [
            rf'Subtotal:\s*\$?\s*{patron_valor_numerico}',
            rf'Neto\s*Gravado:\s*\$?\s*{patron_valor_numerico}'
        ],
        'iva': [
            rf'IVA\s*(?:\d+%?):\s*\$?\s*{patron_valor_numerico}', # Priorizar patrón con porcentaje
            rf'IVA:\s*\$?\s*{patron_valor_numerico}',
            rf'Impuesto\s*IVA:\s*\$?\s*{patron_valor_numerico}', # Añadir patrón 'Impuesto IVA:'
            rf'I\.V\.A\. ?:?\s*\$?\s*{patron_valor_numerico}' # Añadir patrón 'I.V.A.' con o sin ':'
        ],
        'percepcion_iibb': [
            rf'Percepción\s*IIBB:\s*\$?\s*{patron_valor_numerico}',
            rf'IIBB:\s*\$?\s*{patron_valor_numerico}',
            rf'IIBB\s*(?:\d+%?):\s*\$?\s*{patron_valor_numerico}' # Hacer el grupo de porcentaje no capturante
        ],
        'otros_tributos': [
            rf'Otros\s*Tributos:\s*\$?\s*{patron_valor_numerico}',
            rf'Otros\s*Impuestos:\s*\$?\s*{patron_valor_numerico}',
            rf'Otros:\s*\$?\s*{patron_valor_numerico}', # Patrón más genérico por si solo dice "Otros" antes del valor
        ],
        'condicion_venta': [
            r'Condición\s*de\s*Venta:\s*([^\n]+)',
            r'Forma\s*de\s*Pago:\s*([^\n]+)'
        ],
        'condicion_iva': [
            r'Condición\s*IVA:\s*([^\n]+)',
            r'Condición\s*frente\s*al\s*IVA:\s*([^\n]+)'
        ],
        'tipo_copia': [
            r'(Original|Duplicado)',
            r'Copia\s*(Original|Duplicado)'
        ],
        'razon_social_cliente': [
            r'Razón\s*Social:\s*([^\n]+)', # Patrón para "Razón Social: [Nombre]"
            r'Cliente:\s*([^\n]+)', # Patrón para "Cliente: [Nombre]"
            r'Nombre\s*o\s*Razón\s*Social:\s*([^\n]+)', # Patrón para "Nombre o Razón Social: [Nombre]"
            r'Denominación:\s*([^\n]+)' # Patrón para "Denominación: [Nombre]"
        ]
    }

    # Buscar cada patrón en el texto
    for campo, lista_patrones in patrones.items():
        # Priorizar los patrones más específicos o completos
        for patron in lista_patrones:
            match = re.search(patron, texto, re.IGNORECASE)
            if match:
                # Lógica específica para campos con grupos múltiples o nombres diferentes
                if campo == 'numero_completo':
                    if len(match.groups()) >= 2:
                         datos['punto_venta'] = match.group(1)
                         datos['numero'] = match.group(2)
                    else:
                         print(f"Advertencia: Patrón de número completo ('{patron}') no extrajo dos grupos en el texto.") # Debug
                         pass # Continuar al siguiente patrón si este no capturó ambos

                elif campo in ['iva', 'percepcion_iibb', 'monto_total', 'subtotal']:
                    # Para los campos monetarios, el valor numérico está en el último grupo capturado por patron_valor_numerico
                    # Este siempre es el último grupo del match, ya que patron_valor_numerico tiene un solo grupo capturante.
                    valor_str = match.group(len(match.groups()))
                    
                    # Limpiar el string numérico para convertir a float:
                    # 1. Eliminar separadores de miles (puntos o comas seguidos de 3 dígitos al final de un grupo de miles)
                    #    o simplemente eliminar todos los puntos y comas excepto el último si hay decimales.
                    # Una forma más segura es eliminar todos los caracteres que no sean dígitos, excepto si es un punto
                    # inmediatamente seguido por dígitos (posible decimal).
                    
                    # Eliminar todos los caracteres que no sean dígitos o punto/coma
                    valor_limpio = re.sub(r'[^\d.,]', '', valor_str)
                    
                    # Reemplazar la última coma o punto por un punto (asumiendo que es el separador decimal)
                    if ',' in valor_limpio and '.' in valor_limpio:
                        # Si hay ambos, asumimos que el último es el decimal
                        if valor_limpio.rfind('.') > valor_limpio.rfind(','):
                            valor_limpio = valor_limpio.replace(',', '')
                        else:
                            valor_limpio = valor_limpio.replace('.', '')
                            valor_limpio = valor_limpio.replace(',', '.')
                    elif ',' in valor_limpio:
                         valor_limpio = valor_limpio.replace(',', '.')
                    # Si solo hay puntos, asumimos que el último es el decimal y los demás son de miles (eliminados implícitamente)
                    # Si no hay puntos ni comas, ya está bien.

                    try:
                        datos[campo] = float(valor_limpio)
                    except ValueError:
                         print(f"Advertencia: No se pudo convertir a float el valor extraído para {campo}: {valor_str} (limpiado a {valor_limpio})") # Debug
                         datos[campo] = None # Si falla la conversión, dejar como None

                elif campo == 'cuit_cliente':
                     datos['cuit'] = match.group(1)

                elif campo == 'razon_social_cliente':
                     datos['razon_social_cliente'] = match.group(1).strip()

                else:
                    # Para la mayoría de los campos, el primer grupo es el valor deseado
                    datos[campo] = match.group(1)

                # Si encontramos una coincidencia para este campo, pasamos al siguiente campo principal
                # Esto asegura que el primer patrón que coincida para un campo dado sea el que se use
                break

    # Detectar tipo de factura (la función detectar_tipo_factura ya maneja esto)
    datos['tipo_factura'] = detectar_tipo_factura(texto)

    # Extraer productos (la función extraer_productos ya maneja esto y evita los totales)
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
    patron_valor_numerico = r'(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d+)?)'

    # Palabras clave a ignorar en las líneas de productos (totales, encabezados, etc.)
    palabras_ignorar_productos = [
        'Código Producto / Servicio', 'U. Medida',
        'Subtotal:', 'Importe Total:', 'Total:','Neto Gravado', # Palabras clave de totales
        # Mantenemos palabras clave específicas de productos si queremos ignorar algunas líneas,
        # pero eliminamos las que corresponden a los campos que queremos extraer.
        'TOTAL NETO', 'TOTAL IVA', 'TOTAL PERCEPCIONES', 'TOTAL OTROS TRIBUTOS', # Añadir más palabras de totales
        'TOTAL FACTURA', 'IMPORTE TOTAL'
    ]

    # Patrón para encontrar líneas de productos con Cantidad, Descripción, Precio Unitario, Bonificación y Subtotal:
    # ^\s* - Inicio de línea con opcionales espacios
    # (\d+[.,]?\d*) - Cantidad (captura usando patron_cantidad)
    # \s+ - Uno o más espacios
    # (.+?) - Descripción (captura cualquier cosa de forma no codiciosa)
    # \s+ - Uno o más espacios
    # \$?\s*(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d+)?) - Precio Unitario (opcional $, número flexible, captura)
    # \s+ - Uno o más espacios
    # \$?\s*(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d+)?) - Importe Bonificado (opcional $, número flexible, captura)
    # \s+ - Uno o más espacios
    # \$?\s*(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d+)?) - Subtotal de línea (opcional $, número flexible, captura)
    # \s*$ - Opcionales espacios hasta el fin de línea
    # Nota: Usamos r'...' para evitar problemas con backslashes en regex.
    # Asegurarse de que el número de grupos capturados coincida con el acceso posterior (group(1) a group(5)).
    patron_linea_producto = re.compile(
        rf'^\s*{patron_cantidad}\s+(.+?)\s+\$?\s*{patron_valor_numerico}\s+\$?\s*{patron_valor_numerico}\s+\$?\s*{patron_valor_numerico}\s*$',
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
                # Acceder a los grupos capturados:
                # Grupo 1: Cantidad (del patron_cantidad)
                # Grupo 2: Descripción
                # Grupo 3: Precio Unitario (del primer patron_valor_numerico)
                # Grupo 4: Importe Bonificado (del segundo patron_valor_numerico)
                # Grupo 5: Subtotal (del tercer patron_valor_numerico)

                cantidad_str = match.group(1) # Grupo 1: Cantidad
                descripcion = match.group(2).strip() # Grupo 2: Descripción
                precio_unitario_str = match.group(3) # Grupo 3: Precio Unitario
                importe_bonificado_str = match.group(4) # Grupo 4: Importe Bonificado
                subtotal_str = match.group(5) # Grupo 5: Subtotal

                # Limpiar y convertir a float. Usar 0.0 si el string está vacío después de limpiar.
                cantidad = float(cantidad_str.replace(',', '.')) if cantidad_str else 0.0
                # Usamos la misma lógica de limpieza para los valores monetarios que en extraer_datos_factura
                precio_unitario = float(re.sub(r'[^\d.,]', '', precio_unitario_str).replace(',', '.')) if precio_unitario_str else 0.0
                importe_bonificado = float(re.sub(r'[^\d.,]', '', importe_bonificado_str).replace(',', '.')) if importe_bonificado_str else 0.0
                subtotal = float(re.sub(r'[^\d.,]', '', subtotal_str).replace(',', '.')) if subtotal_str else 0.0

                productos.append({
                    'cantidad': cantidad,
                    'descripcion': descripcion,
                    'precio_unitario': precio_unitario,
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
    texto = texto.lower()

    # Patrones para identificar el tipo de factura
    patrones = {
        'A': [
            r'factura\s+a',
            r'tipo\s+a',
            r'comprobante\s+a',
            r'iva\s+responsable\s+inscripto'
        ],
        'B': [
            r'factura\s+b',
            r'tipo\s+b',
            r'comprobante\s+b',
            r'iva\s+responsable\s+no\s+inscripto'
        ],
        'C': [
            r'factura\s+c',
            r'tipo\s+c',
            r'comprobante\s+c',
            r'iva\s+exento'
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
        datos['tipo_factura'] = tipo # Asegurarse de usar 'tipo_factura' según el modelo
        
        return datos
        
    except Exception as e:
        print(f"Error en procesar_factura: {str(e)}")
        raise 