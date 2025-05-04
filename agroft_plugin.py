import os
from qgis.PyQt.QtWidgets import QAction, QToolBar
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QIcon

from .filter_module.filter_dock import FilterDock
from .lineas_module.panel_lineas import LineasDesdeBasePanel
from .capas_module.crear_capas import CrearCapasRiego
from .puntos_module import get_module_instance as get_puntos_module
from .redriego_module.panel_redriego import PanelRedRiego
from .divisor_module.divisor_poligono import DivisorPoligono

class AgroFTPrecisionPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)
        self.toolbar = None
        
        # Componentes del plugin
        self.filter_dock = None
        self.lineas_panel = None
        self.crear_capas = None
        self.puntos_module = None
        self.panel_redriego = None
        self.divisor_poligono = None
        self.actions = []
        
    def initGui(self):
        # Crear barra de herramientas personalizada
        self.toolbar = self.iface.addToolBar("AGROFT Precisión")
        self.toolbar.setObjectName("AGROFTPrecisionToolbar")
        
        # 1. Acción para el Filtro por Campo
        icon_path = os.path.join(self.plugin_dir, "resources/icons/filter_icon.svg")
        filter_action = QAction(QIcon(icon_path), "Filtro por Campo", self.iface.mainWindow())
        filter_action.triggered.connect(self.toggle_filter_dock)
        self.toolbar.addAction(filter_action)
        self.actions.append(filter_action)
        
        # 2. Acción para Líneas desde Base
        icon_path = os.path.join(self.plugin_dir, "resources/icons/lineas_icon.svg")
        lineas_action = QAction(QIcon(icon_path), "Líneas desde Base", self.iface.mainWindow())
        lineas_action.triggered.connect(self.toggle_lineas_panel)
        self.toolbar.addAction(lineas_action)
        self.actions.append(lineas_action)

        # 3. Acción para Crear Capas
        icon_path = os.path.join(self.plugin_dir, "resources/icons/capas_icon.svg")
        crear_action = QAction(QIcon(icon_path), "Crear Capas", self.iface.mainWindow())
        crear_action.triggered.connect(self.crear_capas_ri)
        self.toolbar.addAction(crear_action)
        self.actions.append(crear_action)

        # 4. Acción para Puntos en Línea
        icon_path = os.path.join(self.plugin_dir, "resources/icons/point_icon.svg")
        puntos_action = QAction(QIcon(icon_path), "Puntos en Línea", self.iface.mainWindow())
        puntos_action.triggered.connect(self.generar_puntos)
        self.toolbar.addAction(puntos_action)
        self.actions.append(puntos_action)

        # 5. Acción para Red de Riego
        icon_path = os.path.join(self.plugin_dir, "resources/icons/redriego_icon.svg")
        redriego_action = QAction(QIcon(icon_path), "Red de Riego", self.iface.mainWindow())
        redriego_action.triggered.connect(self.redriego_panel)
        self.toolbar.addAction(redriego_action)
        self.actions.append(redriego_action)

        # 6 y 7. Acciones para Divisor de Polígonos
        # Acción para Dividir en Áreas Iguales
        icon_path = os.path.join(self.plugin_dir, "resources/icons/divisor_area_icon.png")
        divisor_area_action = QAction(QIcon(icon_path), "Dividir en Áreas Iguales", self.iface.mainWindow())
        divisor_area_action.triggered.connect(lambda: self.iniciar_divisor('area'))
        self.toolbar.addAction(divisor_area_action)
        self.actions.append(divisor_area_action)

        # Acción para Dividir en Partes Iguales
        icon_path = os.path.join(self.plugin_dir, "resources/icons/divisor_partes_icon.png")
        divisor_partes_action = QAction(QIcon(icon_path), "Dividir en Partes Iguales", self.iface.mainWindow())
        divisor_partes_action.triggered.connect(lambda: self.iniciar_divisor('conteo'))
        self.toolbar.addAction(divisor_partes_action)
        self.actions.append(divisor_partes_action)


        
        # También añadir al menú de plugins
        for action in self.actions:
            self.iface.addPluginToMenu("&AGROFT Precisión", action)
    
    def unload(self):
        """Método seguro para descargar el plugin"""
        # Limpiar acciones del menú
        try:
            for action in self.actions:
                self.iface.removePluginMenu("&AGROFT Precisión", action)
        except Exception as e:
            print(f"Error al eliminar acciones del menú: {str(e)}")
        
        # Limpiar barra de herramientas sin usar self.toolbar directamente
        try:
            # Buscar la barra de herramientas por su nombre
            for toolbar in self.iface.mainWindow().findChildren(QToolBar, "AGROFTPrecisionToolbar"):
                toolbar.clear()
        except Exception as e:
            print(f"Error al limpiar toolbar: {str(e)}")
        
        # Cerrar paneles y liberar recursos
        try:
            if self.panel_redriego:
                self.panel_redriego.close()
                self.panel_redriego.deleteLater()
                self.panel_redriego = None
        except Exception as e:
            print(f"Error al cerrar panel_redriego: {str(e)}")
        
        try:
            if self.filter_dock:
                self.iface.removeDockWidget(self.filter_dock)
                self.filter_dock.deleteLater()
                self.filter_dock = None
        except Exception as e:
            print(f"Error al cerrar filter_dock: {str(e)}")
        
        try:
            if self.lineas_panel:
                self.lineas_panel.close()
                self.lineas_panel.deleteLater()
                self.lineas_panel = None
        except Exception as e:
            print(f"Error al cerrar lineas_panel: {str(e)}")
        
        try:
            if self.puntos_module:
                self.puntos_module = None
        except Exception as e:
            print(f"Error al limpiar puntos_module: {str(e)}")
        
        try:
            if self.crear_capas:
                self.crear_capas = None
        except Exception as e:
            print(f"Error al limpiar crear_capas: {str(e)}")

        try:
            if self.divisor_poligono:
                # No necesitamos llamar a unload() porque no iniciamos la GUI
                self.divisor_poligono = None
        except Exception as e:
            print(f"Error al limpiar divisor_poligono: {str(e)}")
    
    def toggle_filter_dock(self):
        """Alterna la visibilidad del panel de filtrado"""
        if not self.filter_dock:
            self.filter_dock = FilterDock(self.iface)
            self.iface.addDockWidget(Qt.RightDockWidgetArea, self.filter_dock)
        else:
            if self.filter_dock.isVisible():
                self.filter_dock.hide()
            else:
                self.filter_dock.show_and_activate()

    
    def toggle_lineas_panel(self):
        """Alterna la visibilidad del panel de líneas desde base"""
        if not self.lineas_panel:
            self.lineas_panel = LineasDesdeBasePanel(self.iface)
            self.lineas_panel.show_and_activate()
        else:
            if self.lineas_panel.isVisible():
                self.lineas_panel.hide()
            else:
                self.lineas_panel.show_and_activate()

    def crear_capas_ri(self):
        if self.crear_capas is None:
            self.crear_capas = CrearCapasRiego(self.iface)
        self.crear_capas.crear_capas()

    def generar_puntos(self):
        """Ejecuta el módulo de puntos en línea"""
        if self.puntos_module is None:
            self.puntos_module = get_puntos_module(self.iface)
        self.puntos_module.toggle_panel()  # Cambiado de run() a toggle_panel()

    def redriego_panel(self):
        """Alterna la visibilidad del panel de red de riego"""
        if not self.panel_redriego:
            self.panel_redriego = PanelRedRiego(self.iface)
            # Acoplar el panel en el área derecha
            self.iface.addDockWidget(Qt.RightDockWidgetArea, self.panel_redriego)
        else:
            if self.panel_redriego.isVisible():
                self.panel_redriego.hide()
            else:
                self.panel_redriego.show()
                self.panel_redriego.raise_()

    def iniciar_divisor(self, modo):
        """Inicia el divisor de polígonos en el modo especificado"""
        if self.divisor_poligono is None:
            # Crear la instancia sin inicializar la GUI (no necesitamos las acciones del plugin)
            self.divisor_poligono = DivisorPoligono(self.iface)
            # No llamamos a initGui porque no queremos que cree su propia barra de herramientas
        
        # Inicia la división en el modo especificado directamente
        try:
            self.divisor_poligono.modo = modo
            self.divisor_poligono.dividir_poligono()
        except Exception as e:
            from qgis.PyQt.QtWidgets import QMessageBox
            QMessageBox.critical(None, "Error", str(e))
    