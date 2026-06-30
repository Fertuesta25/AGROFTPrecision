"""
Plugin de Filtrado para QGIS
Este plugin crea un panel lateral donde se puede seleccionar un campo
y filtrar la capa activa por los valores de ese campo.
"""

# Punto de entrada heredado (el modulo se carga desde agroft_plugin.py).
# Se mantiene por compatibilidad y referencia la clase real FilterDock.
def classFactory(iface):
    from .filter_dock import FilterDock
    return FilterDock(iface)