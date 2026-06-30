# dividirlineas_module/__init__.py
"""
Inicialización del módulo de división de líneas
(Compatible con QGIS 3.x/Qt5 y QGIS 4.x/Qt6)
"""

def classFactory(iface):
    from .dividir_lineas_plugin import DividirLineasPlugin
    return DividirLineasPlugin(iface)

def get_module_instance(iface):
    from .dividir_lineas_plugin import DividirLineasPlugin
    return DividirLineasPlugin(iface)