from qgis.core import NULL

def find_min_max_values(layer, field_name):
    """
    Encuentra los valores mínimo y máximo para un campo numérico.
    
    Args:
        layer: Capa vectorial
        field_name: Nombre del campo
        
    Returns:
        Tupla (min_val, max_val)
    """
    min_val = float('inf')
    max_val = float('-inf')
    
    for feature in layer.getFeatures():
        value = feature[field_name]
        if value != NULL:
            value = float(value)
            min_val = min(min_val, value)
            max_val = max(max_val, value)
    
    # Si no se encontraron valores válidos, usar valores predeterminados
    if min_val == float('inf'):
        min_val = 0
    if max_val == float('-inf'):
        max_val = 100
    
    return min_val, max_val

def get_unique_field_values(layer, field_name):
    """
    Obtiene los valores únicos para un campo.
    
    Args:
        layer: Capa vectorial
        field_name: Nombre del campo
        
    Returns:
        Conjunto de valores únicos
    """
    unique_values = set()
    for feature in layer.getFeatures():
        value = feature[field_name]
        if value != NULL:
            unique_values.add(str(value))
    
    return unique_values