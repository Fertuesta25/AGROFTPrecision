"""
Módulo de Puntos para AGROFT Precisión
--------------------------------------------
Este módulo permite generar puntos a lo largo de la geometría de una capa de líneas activa.
Incluye campos para Sector y caudal (Qe), y opcionalmente crea áreas de aspersor.
"""

import os
from qgis.PyQt.QtCore import (
    QSettings, QTranslator, QCoreApplication, Qt, QVariant, QMetaType
)
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import (
    QAction, QVBoxLayout, QLabel, QDoubleSpinBox, 
    QFormLayout, QPushButton, QWidget, QDockWidget, QMessageBox,
    QCheckBox, QGridLayout, QSpacerItem, QSizePolicy
)

from qgis.core import (
    QgsProject, QgsVectorLayer, QgsFeature, QgsGeometry, 
    QgsWkbTypes, QgsField, QgsMapLayerProxyModel, QgsFeatureRequest,
    QgsMessageLog, Qgis
)
from qgis.gui import QgsMapLayerComboBox, QgsCollapsibleGroupBox


class PuntosLineaModule:
    """Módulo para generar puntos a lo largo de líneas para el plugin AGROFT Precisión"""
    
    def __init__(self, iface):
        """Constructor.
        
        :param iface: Una instancia de la interfaz de QGIS.
        """
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)
        self.action = None
        self.panel = None
    
    def add_to_toolbar(self, toolbar):
        """Añade el botón a la barra de herramientas del plugin principal
        
        :param toolbar: La barra de herramientas donde añadir el botón
        :return: La acción creada
        """
        # No intentamos cargar el ícono nosotros mismos
        # El plugin principal ya tiene el ícono definido
        
        # Crear acción sin ícono (el ícono se añadirá en el plugin principal)
        self.action = QAction("Generar Puntos en Línea", self.iface.mainWindow())
        self.action.triggered.connect(self.toggle_panel)
        
        # Añadir a la barra de herramientas (sin ícono)
        toolbar.addAction(self.action)
        return self.action
    
    def toggle_panel(self):
        """Alterna la visibilidad del panel de puntos"""
        if not self.panel:
            self.panel = PuntosLineaPanel(self.iface)
            self.iface.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.panel)
            self.panel.show()  # Asegurarse de que se muestre
            self.panel.raise_()  # Traer al frente
            self.panel.activateWindow()  # Activar la ventana
        else:
            if self.panel.isVisible():
                self.panel.hide()  # Ocultar si está visible
            else:
                self.panel.show()  # Mostrar si está oculto
                self.panel.raise_()  # Traer al frente
                self.panel.activateWindow()  # Activar la ventana
    
    def run(self):
        """Método de compatibilidad que llama a toggle_panel"""
        self.toggle_panel()
        
    def unload(self):
        """Limpia recursos al descargar el plugin"""
        if self.panel:
            self.iface.removeDockWidget(self.panel)
            self.panel = None


class PuntosLineaPanel(QDockWidget):
    """Panel para configurar y generar puntos a lo largo de líneas"""
    
    def __init__(self, iface):
        """Constructor.
        
        :param iface: Una instancia de la interfaz de QGIS.
        """
        super(PuntosLineaPanel, self).__init__("Generar Puntos en Línea", iface.mainWindow())
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)
        self.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)
        
        # Crear el widget contenedor
        self.dock_widget = QWidget()
        
        # Inicializar interfaz
        self.setup_ui()
        self.setWidget(self.dock_widget)
        
        # Configuración inicial
        self.select_default_layer()
        self.select_laterales()
    
    def setup_ui(self):
        """Configura los elementos de la interfaz de usuario"""
        # Layout principal - usar QGridLayout para un control más preciso del espaciado
        main_layout = QGridLayout()
        main_layout.setContentsMargins(8, 8, 8, 8)  # Márgenes mínimos
        main_layout.setSpacing(4)  # Espaciado muy reducido entre elementos
        main_layout.setVerticalSpacing(6)  # Espaciado vertical aún más reducido
        
        row = 0
        # 1. Selector de capa
        self.layer_label = QLabel("Capa de líneas:")
        main_layout.addWidget(self.layer_label, row, 0)
        row += 1
        
        self.layer_combo = QgsMapLayerComboBox()
        self.layer_combo.setFilters(QgsMapLayerProxyModel.LineLayer)
        self.layer_combo.layerChanged.connect(self.on_layer_changed)
        self.layer_combo.setMaximumHeight(22)  # Altura máxima para compactarlo
        main_layout.addWidget(self.layer_combo, row, 0)
        row += 1
        
        # 2. Casilla para usar solo entidades seleccionadas
        self.selected_only_check = QCheckBox("Solo entidades seleccionadas")
        self.selected_only_check.setChecked(True)  # Marcada por defecto
        self.selected_only_check.setMaximumHeight(18)  # Altura máxima para checkbox
        main_layout.addWidget(self.selected_only_check, row, 0)
        row += 1
        
        # 3. Distancia entre puntos
        self.distance_label = QLabel("Distancia entre puntos (m):")
        main_layout.addWidget(self.distance_label, row, 0)
        row += 1
        
        self.distance_spin = QDoubleSpinBox()
        self.distance_spin.setRange(0.1, 10000)
        self.distance_spin.setValue(5)
        self.distance_spin.setMaximumHeight(22)  # Altura máxima
        main_layout.addWidget(self.distance_spin, row, 0)
        row += 1
        
        # 4. Desplazamiento inicial
        self.inicio_label = QLabel("Desplazamiento inicial (m):")
        main_layout.addWidget(self.inicio_label, row, 0)
        row += 1
        
        self.inicio_spin = QDoubleSpinBox()
        self.inicio_spin.setRange(0, 10000)
        self.inicio_spin.setValue(2)
        self.inicio_spin.setMaximumHeight(22)  # Altura máxima
        main_layout.addWidget(self.inicio_spin, row, 0)
        row += 1
        
        # 5. Caudal del emisor (Qe)
        self.qe_label = QLabel("Caudal del emisor (l/h):")
        main_layout.addWidget(self.qe_label, row, 0)
        row += 1
        
        self.qe_spin = QDoubleSpinBox()
        self.qe_spin.setRange(0.01, 1000)
        self.qe_spin.setValue(2.0)
        self.qe_spin.setDecimals(3)
        self.qe_spin.setSingleStep(0.1)
        self.qe_spin.setMaximumHeight(22)  # Altura máxima
        main_layout.addWidget(self.qe_spin, row, 0)
        row += 1
        
        # 6. Group box colapsable para creación de área por aspersor (opcional)
        self.aspersor_group = QgsCollapsibleGroupBox("Creación de área por aspersor (Opcional)")
        self.aspersor_group.setCollapsed(True)  # Replegado por defecto
        self.aspersor_group.setFlat(True)  # Estilo plano para reducir espacio vertical
        self.aspersor_group.setMaximumHeight(200)  # Altura máxima cuando está expandido
        
        aspersor_layout = QGridLayout()
        aspersor_layout.setContentsMargins(4, 4, 4, 4)  # Márgenes mínimos
        aspersor_layout.setVerticalSpacing(4)  # Espaciado vertical mínimo
        
        # Radio del buffer
        self.buffer_label = QLabel("Radio de mojado (m):")
        aspersor_layout.addWidget(self.buffer_label, 0, 0)
        
        self.buffer_spin = QDoubleSpinBox()
        self.buffer_spin.setRange(0, 1000)
        self.buffer_spin.setValue(0)
        self.buffer_spin.setSpecialValueText("No generar")  # Texto especial cuando es 0
        self.buffer_spin.setMaximumHeight(22)  # Altura máxima
        aspersor_layout.addWidget(self.buffer_spin, 1, 0)
        
        self.aspersor_group.setLayout(aspersor_layout)
        main_layout.addWidget(self.aspersor_group, row, 0)
        row += 1
        
        # Añadir un espaciador fijo para separar el GroupBox del botón
        fixed_spacer = QSpacerItem(20, 10, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        main_layout.addItem(fixed_spacer, row, 0)
        row += 1
        
        # 7. Botón de generar
        self.generate_button = QPushButton("Generar Puntos")
        self.generate_button.clicked.connect(self.generate_points)
        self.generate_button.setMaximumHeight(25)  # Ligeramente más alto que los otros controles
        main_layout.addWidget(self.generate_button, row, 0)
        row += 1
        
        # Agregar un espaciador elástico al final
        spacer_item = QSpacerItem(20, 0, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)
        main_layout.addItem(spacer_item, row, 0)
        
        # Configurar el layout en el widget
        self.dock_widget.setLayout(main_layout)
    
    def select_default_layer(self):
        """Selecciona por defecto la capa 'Red de Riego' si existe"""
        for i in range(self.layer_combo.count()):
            layer_name = self.layer_combo.itemText(i)
            if layer_name.lower() == "red de riego":
                self.layer_combo.setCurrentIndex(i)
                return
    
    def select_laterales(self):
        """Selecciona las entidades de tipo 'Laterales' en la capa 'Red de Riego'"""
        layer = self.layer_combo.currentLayer()
        if not layer:
            return
            
        # Verificar si la capa tiene el campo 'Tipo'
        fields = [field.name() for field in layer.fields()]
        if "Tipo" not in fields:
            return
            
        # Seleccionar entidades de tipo 'Laterales'
        layer.removeSelection()
        request = QgsFeatureRequest().setFilterExpression("\"Tipo\" = 'Laterales'")
        laterales_ids = [feature.id() for feature in layer.getFeatures(request)]
        if laterales_ids:
            layer.selectByIds(laterales_ids)
            self.iface.mapCanvas().refresh()
    
    def on_layer_changed(self, layer):
        """Se ejecuta cuando se cambia la capa seleccionada"""
        if not layer:
            return
            
        # Si existe el campo 'Tipo' intentar seleccionar los laterales
        fields = [field.name() for field in layer.fields()]
        if "Tipo" in fields:
            self.select_laterales()
    
    def apply_style_to_layer(self, layer, style_filename):
        """Aplica un estilo QML a una capa
        
        :param layer: Capa a la que aplicar el estilo
        :param style_filename: Nombre del archivo QML de estilo
        """
        # Construir la ruta al archivo QML
        style_path = os.path.join(self.plugin_dir, "styles", style_filename)
        
        # Verificar si el archivo existe
        if os.path.exists(style_path):
            # Cargar el estilo
            layer.loadNamedStyle(style_path)
            layer.triggerRepaint()
            self.iface.layerTreeView().refreshLayerSymbology(layer.id())
        else:
            # Si no existe, mostrar una advertencia en la consola
            QgsMessageLog.logMessage(
                f"Archivo de estilo no encontrado: {style_path}", 
                "Puntos en Línea", 
                Qgis.MessageLevel.Warning
            )
    
    def generate_points(self):
        """Genera puntos a lo largo de las líneas con la configuración actual"""
        # 1. Obtener los parámetros configurados por el usuario
        selected_layer = self.layer_combo.currentLayer()
        distance = self.distance_spin.value()
        inicio = self.inicio_spin.value()
        qe = self.qe_spin.value()
        selected_only = self.selected_only_check.isChecked()
        buffer_radius = self.buffer_spin.value()
        
        # 2. Validar la capa y la selección
        if not selected_layer:
            QMessageBox.warning(self, "Error", "Por favor, seleccione una capa de líneas.")
            return
            
        if selected_layer.geometryType() != QgsWkbTypes.LineGeometry:
            QMessageBox.warning(self, "Error", "La capa seleccionada debe ser de tipo línea.")
            return
        
        # 3. Obtener las entidades a procesar
        features_to_process = []
        if selected_only:
            features_to_process = selected_layer.selectedFeatures()
            if not features_to_process:
                QMessageBox.warning(self, "Advertencia", 
                                    "No hay entidades seleccionadas. Marque todas las entidades o "
                                    "desactive la opción 'Solo entidades seleccionadas'.")
                return
        else:
            features_to_process = list(selected_layer.getFeatures())
        
        # 4. Crear la capa de puntos de salida
        crs = selected_layer.crs()
        output_layer = QgsVectorLayer(f"Point?crs={crs.authid()}", "Puntos_Generados", "memory")
        output_provider = output_layer.dataProvider()
        
        # 5. Añadir campos a la capa de salida
        output_provider.addAttributes([
            QgsField("Sector", QMetaType.Type.Int),
            QgsField("Qe", QMetaType.Type.Double)
        ])
        output_layer.updateFields()
        
        # 6. Generar puntos para cada línea
        features = []
        for feature in features_to_process:
            line_geom = feature.geometry()
            if line_geom:
                line_length = line_geom.length()
                # Generar puntos a lo largo de la línea
                current_distance = inicio  # Comenzar desde el desplazamiento inicial
                while current_distance <= line_length:
                    # Crear un punto a la distancia actual
                    point = line_geom.interpolate(current_distance)
                    
                    # Crear una nueva feature para el punto
                    point_feature = QgsFeature(output_layer.fields())
                    point_feature.setGeometry(point)
                    # Solo asignar el valor de Qe (Sector queda como NULL)
                    point_feature.setAttribute("Qe", qe)
                    
                    features.append(point_feature)
                    current_distance += distance
        
        # 7. Añadir todas las features a la capa de salida
        output_provider.addFeatures(features)
        output_layer.updateExtents()
        
        # 8. Añadir la capa al proyecto
        QgsProject.instance().addMapLayer(output_layer)
        
        # 9. Aplicar estilo QML para la capa de puntos
        self.apply_style_to_layer(output_layer, "emisores.qml")
        
        # 10. Generar capa de buffer si se especificó un radio mayor que 0
        if buffer_radius > 0:
            buffer_layer = self.generate_buffer_layer(output_layer, buffer_radius)
            # Aplicar estilo QML para la capa de buffer
            self.apply_style_to_layer(buffer_layer, "area_de_aspersor.qml")
        
        # 11. Mostrar mensaje de éxito
        self.iface.messageBar().pushMessage(
            "Éxito", f"Se generaron {len(features)} puntos a lo largo de las líneas.", level=Qgis.MessageLevel.Info, duration=3
        )
    
    def generate_buffer_layer(self, source_layer, radius):
        """Genera una capa de buffer a partir de la capa de puntos
        
        :param source_layer: Capa de puntos fuente
        :param radius: Radio del buffer
        :return: La capa de buffer creada
        """
        # Crear la capa de polígonos para los buffers
        crs = source_layer.crs()
        buffer_layer = QgsVectorLayer(f"Polygon?crs={crs.authid()}", "Area_de_aspersor", "memory")
        buffer_provider = buffer_layer.dataProvider()
        
        # Crear los buffers para cada punto
        features = []
        for point_feature in source_layer.getFeatures():
            # Obtener la geometría del punto
            point_geom = point_feature.geometry()
            
            # Crear buffer
            buffer_geom = point_geom.buffer(radius, 25)  # 25 segmentos para aproximar el círculo
            
            # Crear feature para el buffer
            buffer_feature = QgsFeature()
            buffer_feature.setGeometry(buffer_geom)
            
            features.append(buffer_feature)
        
        # Añadir los buffers a la capa
        buffer_provider.addFeatures(features)
        buffer_layer.updateExtents()
        
        # Añadir la capa al proyecto
        QgsProject.instance().addMapLayer(buffer_layer)
        
        # Mensaje de éxito
        self.iface.messageBar().pushMessage(
            "Éxito", f"Se generó la capa de área de aspersores con radio {radius}.", level=Qgis.MessageLevel.Info, duration=3
        )
        
        # Retornar la capa para poder aplicarle estilos
        return buffer_layer


# Función para crear una instancia del módulo
def get_module_instance(iface):
    return PuntosLineaModule(iface)