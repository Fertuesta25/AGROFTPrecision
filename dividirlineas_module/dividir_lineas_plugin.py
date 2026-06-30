# dividirlineas_module/dividir_lineas_plugin.py
"""
Plugin para dividir líneas con puntos
(Compatible con QGIS 3.x/Qt5 y QGIS 4.x/Qt6)
"""
from qgis.PyQt.QtWidgets import QAction, QMessageBox
from qgis.PyQt.QtGui import QIcon
import os
from .dividir_lineas import DividirLineasDialog

class DividirLineasPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.dialog = None
        self.plugin_dir = os.path.dirname(__file__)
        
    def initGui(self):
        """Este método sería llamado si este fuera un plugin independiente"""
        # Nota: Asegúrate de que esta ruta coincida con tu estructura física real (ej. .png o .svg)
        icon_path = os.path.join(self.plugin_dir, "resources/icons/dividirlineas_icon.svg")
        self.action = QAction(QIcon(icon_path), "Dividir Líneas con Puntos", self.iface.mainWindow())
        self.action.triggered.connect(self.run)
        self.iface.addPluginToVectorMenu("&Dividir Líneas", self.action)
    
    def unload(self):
        """Limpia los recursos del plugin"""
        try:
            if self.dialog:
                self.dialog.close()
                self.dialog.deleteLater()
                self.dialog = None
        except Exception as e:
            print(f"Error al cerrar el diálogo: {str(e)}")
    
    def toggle_panel(self):
        """Alterna la visibilidad del panel de dividir líneas"""
        if not self.dialog:
            self.run()
        else:
            if self.dialog.isVisible():
                self.dialog.hide()
            else:
                self.dialog.show()
                self.dialog.activateWindow()
                self.dialog.raise_()
    
    def run(self):
        """Ejecuta el plugin mostrando el diálogo"""
        try:
            if not self.dialog:
                self.dialog = DividirLineasDialog(self.iface)
            
            # Actualizar las capas disponibles
            self.dialog.cargar_capas()
            
            # Mostrar el diálogo
            self.dialog.show()
            self.dialog.activateWindow()
            self.dialog.raise_()
            
        except Exception as e:
            QMessageBox.critical(self.iface.mainWindow(), "Error", 
                               f"No se pudo abrir la herramienta de dividir líneas: {str(e)}")