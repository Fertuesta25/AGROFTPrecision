def get_module_instance(iface):
    """
    Crea y devuelve una instancia del módulo de extracción de vértices
    """
    from .panel_vertices import PanelVertices
    return PanelVertices(iface)