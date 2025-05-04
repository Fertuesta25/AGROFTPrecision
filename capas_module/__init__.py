"""
Plugin de Filtrado para QGIS
Este plugin crea un panel lateral donde se puede seleccionar un campo
y filtrar la capa activa por los valores de ese campo.
"""
# Esta función es necesaria para que QGIS cargue el plugin
def classFactory(iface):
    return CrearCapasRiego(iface)