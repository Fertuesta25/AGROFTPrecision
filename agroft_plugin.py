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
from .dividirlineas_module import get_module_instance as get_dividirlineas_module
from .enumerar_poligonos_module import get_module_instance as get_enumerar_poligonos_module
from .vertices_module import get_module_instance as get_vertices_module  # Módulo de vértices
from .plantillas_module import get_module_instance as get_plantillas_module  # Nuevo módulo de plantillas
from .altura_module.altura_dialog import AlturaDialog  # NUEVO: Módulo de alturas
from .balsas_module import get_module_instance as get_balsas_module
from .disenador_module import get_module_instance as get_disenador_module
from .catch_module.catch_dialog import CatchDialog

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
        self.dividirlineas_module = None
        self.enumerar_poligonos_module = None
        self.vertices_module = None  # Módulo de vértices
        self.plantillas_module = None  # Nuevo módulo de plantillas
        self.balsas_module = None  # Nuevo módulo de balsas
        self.disenador_module = None  # Módulo Diseñador de Plantación PRO
        self.catch_dialog = None  # Módulo Uniformidad de Aspersión (Catch3D)
        self.actions = []
        
    def initGui(self):
        # Buscar si la barra ya existe antes de crearla
        main_window = self.iface.mainWindow()
        existing_toolbar = main_window.findChild(QToolBar, "AGROFTPrecisionToolbar")
        
        if existing_toolbar:
            self.toolbar = existing_toolbar
        else:
            # Crear barra de herramientas personalizada solo si no existe
            self.toolbar = self.iface.addToolBar("AGROFT Precisión")
            self.toolbar.setObjectName("AGROFTPrecisionToolbar")
        
        # Limpiar la barra de herramientas antes de añadir acciones
        self.toolbar.clear()

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
        icon_path = os.path.join(self.plugin_dir, "resources/icons/divisor_area_icon.svg")
        divisor_area_action = QAction(QIcon(icon_path), "Dividir en Áreas Iguales", self.iface.mainWindow())
        divisor_area_action.triggered.connect(lambda: self.iniciar_divisor('area'))
        self.toolbar.addAction(divisor_area_action)
        self.actions.append(divisor_area_action)

        # Acción para Dividir en Partes Iguales
        icon_path = os.path.join(self.plugin_dir, "resources/icons/divisor_partes_icon.svg")
        divisor_partes_action = QAction(QIcon(icon_path), "Dividir en Partes Iguales", self.iface.mainWindow())
        divisor_partes_action.triggered.connect(lambda: self.iniciar_divisor('conteo'))
        self.toolbar.addAction(divisor_partes_action)
        self.actions.append(divisor_partes_action)

        # 8. Acción para Dividir Líneas con Puntos
        icon_path = os.path.join(self.plugin_dir, "resources/icons/dividirlineas_icon.svg")
        dividirlineas_action = QAction(QIcon(icon_path), "Dividir Líneas con Puntos", self.iface.mainWindow())
        dividirlineas_action.triggered.connect(self.dividir_lineas)
        self.toolbar.addAction(dividirlineas_action)
        self.actions.append(dividirlineas_action)

        # 9. Acción para Enumerar Polígonos
        icon_path = os.path.join(self.plugin_dir, "resources/icons/enumerar_icon.svg")
        enumerar_action = QAction(QIcon(icon_path), "Enumerar Polígonos", self.iface.mainWindow())
        enumerar_action.triggered.connect(self.enumerar_poligonos)
        self.toolbar.addAction(enumerar_action)
        self.actions.append(enumerar_action)
        
        # 10. Acción para Extraer Vértices de Polígonos
        icon_path = os.path.join(self.plugin_dir, "resources/icons/vertices_icon.svg")
        vertices_action = QAction(QIcon(icon_path), "Extraer Vértices", self.iface.mainWindow())
        vertices_action.triggered.connect(self.extraer_vertices)
        self.toolbar.addAction(vertices_action)
        self.actions.append(vertices_action)
        
        # 11. NUEVA: Acción para el módulo de Plantillas de Mapas
        icon_path = os.path.join(self.plugin_dir, "resources/icons/plantillas_icon.svg")
        plantillas_action = QAction(QIcon(icon_path), "Plantillas de Mapas", self.iface.mainWindow())
        plantillas_action.triggered.connect(self.plantillas_panel)
        self.toolbar.addAction(plantillas_action)
        self.actions.append(plantillas_action)

        # 12. NUEVA: Acción para Extractor de Alturas
        icon_path = os.path.join(self.plugin_dir, "resources/icons/altura_icon.svg")
        altura_action = QAction(QIcon(icon_path), "Extraer Alturas de Red de Riego", self.iface.mainWindow())
        altura_action.triggered.connect(self.extractor_alturas)
        self.toolbar.addAction(altura_action)
        self.actions.append(altura_action)

        # 13. NUEVA: Acción para Cálculo de Balsas de Riego
        icon_path = os.path.join(self.plugin_dir, "resources/icons/balsas_icon.svg")
        balsas_action = QAction(QIcon(icon_path), "Cálculo de Balsas de Riego", self.iface.mainWindow())
        balsas_action.triggered.connect(self.balsas_panel)
        self.toolbar.addAction(balsas_action)
        self.actions.append(balsas_action)
        
        # 14. NUEVA: Diseñador de Plantación PRO (Oil Palm)
        icon_path = os.path.join(self.plugin_dir, "resources/icons/disenador_icon.svg")
        disenador_action = QAction(QIcon(icon_path), "Diseñador de Plantación PRO", self.iface.mainWindow())
        disenador_action.triggered.connect(self.disenador_panel)
        self.toolbar.addAction(disenador_action)
        self.actions.append(disenador_action)
        
        # 15. NUEVA: Uniformidad de Aspersión (Catch3D)
        icon_path = os.path.join(self.plugin_dir, "resources/icons/catch_icon.svg")
        catch_action = QAction(QIcon(icon_path), "Uniformidad de Aspersión", self.iface.mainWindow())
        catch_action.triggered.connect(self.uniformidad_aspersion)
        self.toolbar.addAction(catch_action)
        self.actions.append(catch_action)
        
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
        
        # Eliminar la barra de herramientas completamente
        try:
            main_window = self.iface.mainWindow()
            toolbar = main_window.findChild(QToolBar, "AGROFTPrecisionToolbar")
            if toolbar:
                main_window.removeToolBar(toolbar)
                # Si es necesario, también eliminar del objeto
                toolbar.deleteLater()
        except Exception as e:
            print(f"Error al eliminar toolbar: {str(e)}")
        
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

        try:
            if self.dividirlineas_module:
                self.dividirlineas_module.unload()
                self.dividirlineas_module = None
        except Exception as e:
            print(f"Error al limpiar dividirlineas_module: {str(e)}")
            
        try:
            if self.enumerar_poligonos_module:
                self.enumerar_poligonos_module.unload()
                self.enumerar_poligonos_module = None
        except Exception as e:
            print(f"Error al limpiar enumerar_poligonos_module: {str(e)}")
            
        try:
            if self.vertices_module:
                self.vertices_module.unload()
                self.vertices_module = None
        except Exception as e:
            print(f"Error al limpiar vertices_module: {str(e)}")
            
        try:
            if self.plantillas_module:  # Liberación del nuevo módulo
                self.plantillas_module.unload()
                self.plantillas_module = None
        except Exception as e:
            print(f"Error al limpiar plantillas_module: {str(e)}")

        try:
            if self.balsas_module:
                self.balsas_module.close()
                self.balsas_module.deleteLater()
                self.balsas_module = None
        except Exception as e:
            print(f"Error al limpiar balsas_module: {str(e)}")
        
        try:
            if self.disenador_module:
                self.disenador_module.cleanup()
                self.iface.removeDockWidget(self.disenador_module)
                self.disenador_module.deleteLater()
                self.disenador_module = None
        except Exception as e:
            print(f"Error al limpiar disenador_module: {str(e)}")
        
        try:
            if self.catch_dialog:
                self.catch_dialog.close()
                self.catch_dialog.deleteLater()
                self.catch_dialog = None
        except Exception as e:
            print(f"Error al limpiar catch_dialog: {str(e)}")
    
    def toggle_filter_dock(self):
        """Alterna la visibilidad del panel de filtrado"""
        if not self.filter_dock:
            self.filter_dock = FilterDock(self.iface)
            self.iface.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.filter_dock)
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
            self.iface.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.panel_redriego)
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

    def dividir_lineas(self):
        """Ejecuta el módulo de dividir líneas con puntos"""
        if self.dividirlineas_module is None:
            self.dividirlineas_module = get_dividirlineas_module(self.iface)
        self.dividirlineas_module.toggle_panel()
        
    def enumerar_poligonos(self):
        """Ejecuta el módulo de enumerar polígonos"""
        if self.enumerar_poligonos_module is None:
            self.enumerar_poligonos_module = get_enumerar_poligonos_module(self.iface)
        self.enumerar_poligonos_module.toggle_panel()
        
    def extraer_vertices(self):
        """Ejecuta el módulo de extracción de vértices de polígonos"""
        if self.vertices_module is None:
            self.vertices_module = get_vertices_module(self.iface)
        
        # Verificar si el panel está visible
        if not self.vertices_module.isVisible():
            self.vertices_module.show()
            self.vertices_module.raise_()
        else:
            # Si ya está visible, simplemente lo llevamos al frente
            self.vertices_module.raise_()
        
    def plantillas_panel(self):
        """Alterna la visibilidad del panel de plantillas de mapas"""
        if not self.plantillas_module:
            self.plantillas_module = get_plantillas_module(self.iface)
            # Acoplar el panel en el área derecha
            self.iface.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.plantillas_module)
        else:
            self.plantillas_module.toggle_panel()

    def extractor_alturas(self):
        """NUEVO: Ejecuta la herramienta de extracción de alturas"""
        try:
            # Crear y mostrar el diálogo de alturas
            self.altura_dialog = AlturaDialog(self.iface.mainWindow())
            self.altura_dialog.exec()
        except Exception as e:
            from qgis.PyQt.QtWidgets import QMessageBox
            QMessageBox.critical(
                self.iface.mainWindow(),
                "Error",
                f"Error ejecutando extractor de alturas: {str(e)}"
            )

    def balsas_panel(self):
        """Alterna la visibilidad del panel de balsas de riego"""
        if not self.balsas_module:
            self.balsas_module = get_balsas_module(self.iface)
            # Acoplar el panel en el área derecha
            self.iface.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.balsas_module)
        else:
            if self.balsas_module.isVisible():
                self.balsas_module.hide()
            else:
                self.balsas_module.show_and_activate()

    def disenador_panel(self):
        """Alterna la visibilidad del panel del Diseñador de Plantación PRO."""
        if not self.disenador_module:
            self.disenador_module = get_disenador_module(self.iface)
            self.iface.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.disenador_module)
        else:
            self.disenador_module.setVisible(not self.disenador_module.isVisible())

    def uniformidad_aspersion(self):
        """Abre el diálogo de Uniformidad de Aspersión (Catch3D)."""
        try:
            if self.catch_dialog is None:
                self.catch_dialog = CatchDialog(self.iface, self.iface.mainWindow())
            self.catch_dialog.show()
            self.catch_dialog.raise_()
            self.catch_dialog.activateWindow()
        except Exception as e:
            from qgis.PyQt.QtWidgets import QMessageBox
            QMessageBox.critical(
                self.iface.mainWindow(), "Error",
                f"Error abriendo Uniformidad de Aspersión: {str(e)}"
            )