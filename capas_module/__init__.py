"""
Plugin principal para la creación y filtrado de capas de riego
(Compatible con QGIS 3.x/Qt5 y QGIS 4.x/Qt6)
"""

def classFactory(iface):
    """
    Esta función es el punto de entrada que QGIS requiere para iniciar el plugin.
    Carga el panel lateral para filtrar y gestionar las capas activas.
    """
    # Se importa aquí adentro para evitar problemas de dependencias circulares al arrancar QGIS
    # (Nota: cambia 'crear_capas_riego' por el nombre real de tu archivo .py si es distinto)
    from .crear_capas import CrearCapasRiego
    
    return CrearCapasRiego(iface)