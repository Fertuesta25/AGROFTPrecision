"""
Integración del módulo de puntos con el plugin principal AGROFT Precisión
Este archivo se encarga de gestionar la integración con la barra de herramientas principal
"""

from qgis.PyQt.QtWidgets import QAction
from qgis.PyQt.QtGui import QIcon
import os
from .puntos_linea import PuntosLineaModule

class PuntosIntegration:
    """Clase para integrar el módulo de puntos en la barra de herramientas principal"""
    
    def __init__(self, iface):
        """Constructor
        
        :param iface: Una instancia de la interfaz de QGIS
        """
        self.iface = iface
        self.puntos_module = PuntosLineaModule(iface)
        self.action = None
        
    def add_to_toolbar(self, toolbar):
        """Añade el botón a la barra de herramientas principal
        
        :param toolbar: La barra de herramientas donde se añadirá el botón
        :return: La acción creada
        """
        # Obtener el módulo de puntos y añadirlo a la barra de herramientas
        self.action = self.puntos_module.add_to_toolbar(toolbar)
        return self.action
        
    def unload(self):
        """Limpia recursos al descargar el plugin"""
        self.puntos_module.unload()