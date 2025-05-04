from qgis.core import QgsVectorLayer

def apply_layer_filter(layer, field_name, numeric_range=None, text_value=None, zoom=True, iface=None):
    """
    Aplica un filtro a la capa especificada.
    
    Args:
        layer: Capa a filtrar (QgsVectorLayer)
        field_name: Nombre del campo para filtrar
        numeric_range: Tupla (min, max) para filtros numéricos
        text_value: Valor de texto para filtros de texto
        zoom: Si es True, hace zoom a los elementos filtrados
        iface: Instancia de la interfaz de QGIS
    """
    if not isinstance(layer, QgsVectorLayer):
        return False
        
    # Crear expresión de filtro
    if numeric_range:
        min_val, max_val = numeric_range
        filter_exp = f"\"{field_name}\" >= {min_val} AND \"{field_name}\" <= {max_val}"
    elif text_value:
        filter_exp = f"\"{field_name}\" = '{text_value}'"
    else:
        return False
        
    # Aplicar filtro
    layer.setSubsetString(filter_exp)
    
    # Hacer zoom si se especificó
    if zoom and iface and layer.featureCount() > 0:
        iface.mapCanvas().zoomToFeatureExtent(layer.extent())
    
    # Actualizar la vista del mapa
    if iface:
        iface.mapCanvas().refresh()
    
    return True

def clear_layer_filter(layer, zoom=True, iface=None):
    """
    Elimina cualquier filtro aplicado a la capa.
    
    Args:
        layer: Capa a limpiar (QgsVectorLayer)
        zoom: Si es True, hace zoom a la extensión completa
        iface: Instancia de la interfaz de QGIS
    """
    if not isinstance(layer, QgsVectorLayer):
        return False
        
    # Quitar el filtro
    layer.setSubsetString("")
    
    # Hacer zoom si se especificó
    if zoom and iface:
        iface.mapCanvas().zoomToFeatureExtent(layer.extent())
    
    # Actualizar la vista del mapa
    if iface:
        iface.mapCanvas().refresh()
    
    return True