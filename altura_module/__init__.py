"""
Módulo de extracción de alturas para red de riego
(Compatible con QGIS 3.x/Qt5 y QGIS 4.x/Qt6)
"""

from .altura_extractor import AlturaExtractor
from .altura_dialog import AlturaDialog
from .altura_utils import AlturaUtils

__version__ = "1.0.0"
__author__ = "AGROFT Precisión"

__all__ = ['AlturaExtractor', 'AlturaDialog', 'AlturaUtils']


def get_module_instance(iface):
    """
    Función de factoría para crear instancia del módulo siguiendo el patrón del plugin.
    Esta función no es necesaria para este módulo ya que usa diálogo modal,
    pero se incluye por consistencia con otros módulos del plugin.
    """
    return AlturaDialog(iface.mainWindow())