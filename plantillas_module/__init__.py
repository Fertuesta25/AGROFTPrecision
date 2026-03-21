from .panel_plantillas import PanelPlantillas

def get_module_instance(iface):
    """
    Función para obtener una instancia del módulo de plantillas.
    Sigue el patrón utilizado por otros módulos en el plugin.
    """
    return PanelPlantillas(iface)