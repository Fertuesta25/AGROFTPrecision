"""
Configuración del módulo de extracción de alturas
"""

# Configuraciones por defecto
CONFIGURACION_DEFECTO = {
    # Tolerancias para detección de problemas
    'tolerancia_contrapendiente': 0.1,  # metros
    'pendiente_minima': 0.1,  # porcentaje
    'pendiente_maxima': 15.0,  # porcentaje
    
    # Configuración de análisis
    'puntos_perfil_defecto': 50,  # número de puntos para perfil longitudinal
    'precision_alturas': 2,  # decimales para alturas
    'precision_pendientes': 4,  # decimales para pendientes
    
    # Configuración de excavación (valores aproximados)
    'ancho_zanja_defecto': 0.6,  # metros
    'profundidad_zanja_defecto': 0.8,  # metros
    
    # Límites de validación para DEM
    'altura_minima_mundo': -500,  # metros bajo nivel del mar
    'altura_maxima_mundo': 8000,  # metros sobre nivel del mar
    'resolucion_dem_advertencia': 100,  # metros/pixel
    
    # Configuración de interfaz
    'nombre_capa_defecto': 'Red_Riego_Alturas',
    'formatos_salida': [
        ('Shapefile', 'ESRI Shapefile', '.shp'),
        ('GeoPackage', 'GPKG', '.gpkg'),
        ('GeoJSON', 'GeoJSON', '.geojson'),
        ('KML', 'KML', '.kml')
    ],
    
    # Configuración de reportes
    'generar_reporte_html': True,
    'incluir_estadisticas_detalladas': True,
    'incluir_graficos_perfil': False,  # Para futuras versiones
    
    # Mensajes de usuario
    'mensajes': {
        'procesamiento_iniciado': 'Iniciando extracción de alturas...',
        'procesamiento_completado': '¡Procesamiento completado exitosamente!',
        'error_dem_no_valido': 'El DEM seleccionado no es válido',
        'error_lineas_no_validas': 'La capa de líneas seleccionada no es válida',
        'advertencia_crs_diferente': 'Los sistemas de coordenadas del DEM y las líneas son diferentes',
        'advertencia_dem_baja_resolucion': 'El DEM tiene baja resolución, los resultados pueden ser imprecisos'
    }
}

# Clasificaciones de pendiente
CLASIFICACION_PENDIENTES = {
    'muy_suave': (0, 0.5),
    'suave': (0.5, 2.0),
    'moderada': (2.0, 5.0),
    'pronunciada': (5.0, 10.0),
    'muy_pronunciada': (10.0, 20.0),
    'extrema': (20.0, float('inf'))
}

# Códigos de color para clasificación de pendientes (para futuras mejoras visuales)
COLORES_PENDIENTES = {
    'muy_suave': '#4CAF50',      # Verde
    'suave': '#8BC34A',          # Verde claro
    'moderada': '#FFEB3B',       # Amarillo
    'pronunciada': '#FF9800',    # Naranja
    'muy_pronunciada': '#F44336', # Rojo
    'extrema': '#9C27B0'         # Púrpura
}

# Configuración de estilos para reportes HTML
ESTILOS_HTML = {
    'color_principal': '#2e7d32',
    'color_secundario': '#4caf50',
    'color_advertencia': '#ff9800',
    'color_error': '#f44336',
    'color_exito': '#4caf50',
    'fuente_principal': 'Arial, sans-serif',
    'tamaño_fuente_base': '14px'
}

def obtener_configuracion():
    """Obtiene la configuración completa del módulo"""
    return CONFIGURACION_DEFECTO.copy()

def obtener_clasificacion_pendiente(pendiente_porcentaje):
    """
    Obtiene la clasificación de una pendiente dada
    
    Args:
        pendiente_porcentaje (float): Pendiente en porcentaje
        
    Returns:
        tuple: (clasificacion, color) donde clasificacion es el nombre y color es el código hex
    """
    if pendiente_porcentaje is None:
        return 'no_definida', '#666666'
    
    pendiente_abs = abs(pendiente_porcentaje)
    
    for clasificacion, (minimo, maximo) in CLASIFICACION_PENDIENTES.items():
        if minimo <= pendiente_abs < maximo:
            return clasificacion, COLORES_PENDIENTES[clasificacion]
    
    return 'extrema', COLORES_PENDIENTES['extrema']

def validar_configuracion(config):
    """
    Valida que la configuración proporcionada sea correcta
    
    Args:
        config (dict): Configuración a validar
        
    Returns:
        bool: True si la configuración es válida
    """
    try:
        # Validar que existan las claves principales
        claves_requeridas = [
            'tolerancia_contrapendiente',
            'pendiente_minima',
            'pendiente_maxima',
            'puntos_perfil_defecto'
        ]
        
        for clave in claves_requeridas:
            if clave not in config:
                return False
        
        # Validar rangos de valores
        if config['tolerancia_contrapendiente'] < 0:
            return False
        
        if config['pendiente_minima'] < 0 or config['pendiente_maxima'] < 0:
            return False
        
        if config['pendiente_minima'] >= config['pendiente_maxima']:
            return False
        
        if config['puntos_perfil_defecto'] < 2:
            return False
        
        return True
        
    except Exception:
        return False

# Configuración de formatos de archivo soportados
FORMATOS_DEM_SOPORTADOS = [
    "GeoTIFF (*.tif *.tiff)",
    "IMG (*.img)", 
    "ASCII Grid (*.asc)",
    "HGT (*.hgt)",
    "NetCDF (*.nc)",
    "Todos los archivos (*)"
]

FORMATOS_VECTORIALES_SOPORTADOS = [
    "Shapefile (*.shp)",
    "GeoPackage (*.gpkg)", 
    "GeoJSON (*.geojson)",
    "KML (*.kml)",
    "GPX (*.gpx)",
    "Todos los archivos (*)"
]

# Configuración de logging (para futuras mejoras)
LOG_CONFIG = {
    'nivel': 'INFO',
    'formato': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    'archivo': 'altura_extractor.log',
    'max_tamaño': 1024 * 1024,  # 1 MB
    'backup_count': 3
}