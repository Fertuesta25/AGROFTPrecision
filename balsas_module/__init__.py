# balsas_module/__init__.py
"""
Módulo de Balsas de Riego para AGROFT Precisión
Versión 3.0 con soporte 3D
"""

def get_module_instance(iface):
    """
    Función factory para obtener una instancia del módulo de balsas
    """
    try:
        from .panel_balsas import PanelBalsas
        return PanelBalsas(iface)
    except ImportError as e:
        # En caso de error de importación, crear un panel básico
        from qgis.PyQt.QtWidgets import QDockWidget, QLabel
        dock = QDockWidget("Balsas - Error", iface.mainWindow())
        label = QLabel(f"Error al cargar módulo de balsas: {str(e)}")
        dock.setWidget(label)
        return dock

__version__ = "3.0.0"
__author__ = "AGROFT Precisión"
