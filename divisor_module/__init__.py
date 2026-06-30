# divisor_module/__init__.py
"""
Inicialización del módulo divisor de polígonos
(Compatible con QGIS 3.x/Qt5 y QGIS 4.x/Qt6)
"""

def classFactory(iface):
    from .divisor_poligono import DivisorPoligono
    return DivisorPoligono(iface)

def get_module_instance(iface):
    """
    Función de factoría adicional para mantener la consistencia
    de llamadas con el archivo agroft_plugin.py
    """
    from .divisor_poligono import DivisorPoligono
    return DivisorPoligono(iface)