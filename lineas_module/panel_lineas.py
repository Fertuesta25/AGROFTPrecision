from qgis.PyQt.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QComboBox,
    QDoubleSpinBox, QDockWidget, QSizePolicy, QMessageBox, QCheckBox,
    QSpacerItem, QHBoxLayout, QToolButton
)
from qgis.PyQt.QtCore import Qt, QCoreApplication
from qgis.PyQt.QtGui import QIcon
from qgis.core import QgsProject, Qgis, QgsFeature, QgsVectorLayer, QgsGeometry, QgsPointXY, QgsFeatureRequest, QgsWkbTypes
from qgis.utils import iface
from .maptool_direccion_avanzado import MapToolDireccionAvanzado
from .algoritmo_lineas import generar_lineas
import os
import math

class LineasDesdeBasePanel(QDockWidget):
    def __init__(self, iface):
        super().__init__("Líneas desde Base")
        self.iface = iface
        self.widget = QWidget()
        self.setWidget(self.widget)
        self.linea_direccion = None
        self.map_tool = None
        self.result_layer = None  # Para guardar referencia a la capa de resultado
        self.plugin_dir = os.path.dirname(os.path.dirname(__file__))  # Directorio del plugin

        # Configurar el dock para siempre aparecer a la derecha
        self.setAllowedAreas(Qt.DockWidgetArea.RightDockWidgetArea)
        
        # Crear layout principal con márgenes reducidos
        layout = QVBoxLayout()
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)
        
        # Añadir barra de herramientas en la parte superior que incluirá selección y copiar a red
        toolbar_layout = QHBoxLayout()
        toolbar_layout.setContentsMargins(0, 0, 0, 0)
        toolbar_layout.setSpacing(2)
        
        # Crear contenedor para botones de selección (izquierda)
        selection_layout = QHBoxLayout()
        selection_layout.setContentsMargins(0, 0, 0, 0)
        selection_layout.setSpacing(2)
        
        # Crear botones para las herramientas de selección
        self.btn_select = QToolButton()
        self.btn_select.setIcon(iface.actionSelect().icon())
        self.btn_select.setToolTip("Seleccionar objetos espaciales")
        self.btn_select.clicked.connect(lambda: self.activar_herramienta_seleccion(iface.actionSelect()))
        
        self.btn_select_polygon = QToolButton()
        self.btn_select_polygon.setIcon(iface.actionSelectPolygon().icon())
        self.btn_select_polygon.setToolTip("Seleccionar objetos espaciales por polígono")
        self.btn_select_polygon.clicked.connect(lambda: self.activar_herramienta_seleccion(iface.actionSelectPolygon()))
        
        self.btn_select_freehand = QToolButton()
        self.btn_select_freehand.setIcon(iface.actionSelectFreehand().icon())
        self.btn_select_freehand.setToolTip("Seleccionar objetos espaciales a mano alzada")
        self.btn_select_freehand.clicked.connect(lambda: self.activar_herramienta_seleccion(iface.actionSelectFreehand()))
        
        self.btn_select_radius = QToolButton()
        self.btn_select_radius.setIcon(iface.actionSelectRadius().icon())
        self.btn_select_radius.setToolTip("Seleccionar objetos espaciales por radio")
        self.btn_select_radius.clicked.connect(lambda: self.activar_herramienta_seleccion(iface.actionSelectRadius()))
        
        # Añadir botones para seleccionar todos y deseleccionar con íconos propios
        self.btn_select_all = QToolButton()
        self.btn_select_all.setText("✓")  # Usar un símbolo de texto
        self.btn_select_all.setToolTip("Seleccionar todos los objetos espaciales")
        self.btn_select_all.clicked.connect(self.seleccionar_todos)
        
        self.btn_deselect_all = QToolButton()
        self.btn_deselect_all.setText("✗")  # Usar un símbolo de texto
        self.btn_deselect_all.setToolTip("Deseleccionar todos los objetos espaciales")
        self.btn_deselect_all.clicked.connect(self.deseleccionar_todos)
        
        # Añadir botones al layout de selección
        selection_layout.addWidget(self.btn_select)
        selection_layout.addWidget(self.btn_select_polygon)
        selection_layout.addWidget(self.btn_select_freehand)
        selection_layout.addWidget(self.btn_select_radius)
        selection_layout.addWidget(self.btn_select_all)
        selection_layout.addWidget(self.btn_deselect_all)
        
        # Añadir botón para copiar a Red de riego (derecha)
        self.btn_copiar_red = QToolButton()
        self.btn_copiar_red.setIcon(QIcon(":/images/themes/default/mActionEditCopy.svg"))  # Usar ícono de copiar de QGIS
        self.btn_copiar_red.setToolTip("Copiar a Red de riego como laterales DN 16")
        self.btn_copiar_red.clicked.connect(self.copiar_a_red_riego)
        self.btn_copiar_red.setEnabled(False)  # Inicialmente deshabilitado hasta que se generen líneas
        
        # Configurar el layout principal de la barra de herramientas
        toolbar_layout.addLayout(selection_layout)  # Botones de selección a la izquierda
        toolbar_layout.addStretch()                 # Espacio en medio
        toolbar_layout.addWidget(self.btn_copiar_red)  # Botón de copiar a la derecha
        
        # Añadir la barra de herramientas al layout principal
        layout.addLayout(toolbar_layout)

        self.label_base = QLabel("Seleccionar línea base:")
        self.combo_base = QComboBox()
        self.combo_base.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        
        # Añadir checkbox para usar solo entidades seleccionadas
        self.check_seleccionadas = QCheckBox("Usar solo entidades seleccionadas")
        self.check_seleccionadas.setChecked(False)
        self.check_seleccionadas.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

        # NUEVA FUNCIONALIDAD: Agregar selección de capa de polígonos
        self.label_poligono = QLabel("Capa de polígonos (opcional):")
        self.combo_poligono = QComboBox()
        self.combo_poligono.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        
        # Agregar opción "Ninguna" al principio
        self.combo_poligono.addItem("Ninguna", None)
        
        # Checkbox para extender líneas hasta el borde del polígono
        self.check_extender = QCheckBox("Extender líneas hasta el borde del polígono")
        self.check_extender.setChecked(False)
        self.check_extender.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        
        self.btn_dibujar = QPushButton("📐 Dibujar dirección")
        self.btn_dibujar.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.btn_dibujar.clicked.connect(self.activar_dibujo)

        self.label_espaciado = QLabel("Espaciado (m):")
        self.spin_espaciado = QDoubleSpinBox()
        self.spin_espaciado.setRange(0.01, 1000)
        self.spin_espaciado.setValue(5.0)
        self.spin_espaciado.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self.label_longitud = QLabel("Longitud (m):")
        self.spin_longitud = QDoubleSpinBox()
        self.spin_longitud.setRange(0.01, 1000)
        self.spin_longitud.setValue(20.0)
        self.spin_longitud.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self.label_offset = QLabel("Offset inicial (m):")
        self.spin_offset = QDoubleSpinBox()
        self.spin_offset.setRange(0.0, 1000)
        self.spin_offset.setValue(1.0)
        self.spin_offset.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self.label_lado = QLabel("Lado:")
        self.combo_lado = QComboBox()
        self.combo_lado.addItems(["Derecha", "Izquierda", "Ambos lados"])
        self.combo_lado.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self.btn_generar = QPushButton("🛠 Generar líneas")
        self.btn_generar.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.btn_generar.clicked.connect(self.generar_lineas)

        # Conectar el evento de cambio del checkbox de extender
        self.check_extender.stateChanged.connect(self.actualizar_longitud_por_extension)

        # Añadir todos los widgets al layout
        for w in [
            self.label_base, self.combo_base, self.check_seleccionadas, 
            self.label_poligono, self.combo_poligono, self.check_extender,  # NUEVOS WIDGETS
            self.btn_dibujar,
            self.label_espaciado, self.spin_espaciado,
            self.label_longitud, self.spin_longitud,
            self.label_offset, self.spin_offset,
            self.label_lado, self.combo_lado,
            self.btn_generar
        ]:
            layout.addWidget(w)
        
        # Añadir un espaciador que absorba todo el espacio extra
        layout.addSpacerItem(QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding))

        # Configurar el widget contenedor para que se ajuste al tamaño preferido
        self.widget.setLayout(layout)
        self.widget.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        
        # Añadir el panel al dock de QGIS en la parte derecha
        iface.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self)
        
        # Hacer que el panel ocupe todo el espacio disponible
        self.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetFloatable | QDockWidget.DockWidgetFeature.DockWidgetMovable | QDockWidget.DockWidgetFeature.DockWidgetClosable)
        
        self.load_line_layers()
        self.load_polygon_layers()  # NUEVA FUNCIÓN
        
        # Conectar señales para mantener actualizada la lista de capas
        QgsProject.instance().layersAdded.connect(self.load_line_layers)
        QgsProject.instance().layersAdded.connect(self.load_polygon_layers)  # NUEVA CONEXIÓN
        QgsProject.instance().layersRemoved.connect(self.load_line_layers)
        QgsProject.instance().layersRemoved.connect(self.load_polygon_layers)  # NUEVA CONEXIÓN
        
        # Conectar señal para actualizar el combo cuando cambia la capa activa
        iface.currentLayerChanged.connect(self.actualizar_capa_activa)

    def actualizar_longitud_por_extension(self, state):
        """
        Actualiza el valor de longitud cuando se marca/desmarca la opción de extender hasta polígono
        
        Args:
            state: Estado del checkbox (Qt.CheckState.Checked o Qt.CheckState.Unchecked)
        """
        if state == Qt.CheckState.Checked:
            # Si se marca la opción de extender, fijar longitud a 1 metro y deshabilitar
            self.spin_longitud.setValue(1.0)
            self.spin_longitud.setEnabled(False)
        else:
            # Si se desmarca, volver a habilitar el campo
            self.spin_longitud.setEnabled(True)

    def actualizar_capa_activa(self, layer):
        """Actualiza el combo cuando se cambia la capa activa"""
        if layer and layer.type() == layer.VectorLayer:
            if layer.geometryType() == 1:  # Líneas
                # Buscar el índice de la capa activa en el combo
                index = self.combo_base.findData(layer.id())
                if index >= 0:
                    self.combo_base.setCurrentIndex(index)
            elif layer.geometryType() == 2:  # Polígonos
                # Buscar el índice de la capa activa en el combo
                index = self.combo_poligono.findData(layer.id())
                if index >= 0:
                    self.combo_poligono.setCurrentIndex(index)

    def activar_herramienta_seleccion(self, action):
        # Usar la capa activa para la selección
        active_layer = self.iface.activeLayer()
        
        # Si no hay capa activa o no es una capa de líneas, usar la del combo
        if not active_layer or active_layer.type() != active_layer.VectorLayer or active_layer.geometryType() != 1:
            if self.combo_base.count() > 0 and self.combo_base.currentData():
                layer_id = self.combo_base.currentData()
                active_layer = QgsProject.instance().mapLayer(layer_id)
                if active_layer:
                    self.iface.setActiveLayer(active_layer)
        
        # Activar la herramienta de selección
        if active_layer:
            action.trigger()
            # Marcar el checkbox de selección automáticamente
            self.check_seleccionadas.setChecked(True)
            # También actualizar el combo para mostrar la capa activa
            index = self.combo_base.findData(active_layer.id())
            if index >= 0:
                self.combo_base.setCurrentIndex(index)
            
            # Mostrar mensaje en la barra de estado
            self.iface.messageBar().pushMessage(
                "Selección", 
                f"Seleccionando objetos espaciales en la capa {active_layer.name()}", 
                Qgis.MessageLevel.Info, 
                3  # Duración en segundos
            )

    def seleccionar_todos(self):
        # Seleccionar todos los objetos de la capa activa
        active_layer = self.iface.activeLayer()
        
        # Si no hay capa activa o no es una capa de líneas, usar la del combo
        if not active_layer or active_layer.type() != active_layer.VectorLayer or active_layer.geometryType() != 1:
            if self.combo_base.count() > 0 and self.combo_base.currentData():
                layer_id = self.combo_base.currentData()
                active_layer = QgsProject.instance().mapLayer(layer_id)
                if active_layer:
                    self.iface.setActiveLayer(active_layer)
        
        if active_layer:
            active_layer.selectAll()
            self.check_seleccionadas.setChecked(True)
            # Actualizar el combo para mostrar la capa activa
            index = self.combo_base.findData(active_layer.id())
            if index >= 0:
                self.combo_base.setCurrentIndex(index)
            
            # Mostrar mensaje en la barra de estado
            self.iface.messageBar().pushMessage(
                "Selección", 
                f"Se han seleccionado {active_layer.selectedFeatureCount()} objetos en la capa {active_layer.name()}", 
                Qgis.MessageLevel.Success, 
                3  # Duración en segundos
            )
            
            # Forzar la actualización del canvas
            self.iface.mapCanvas().refresh()

    def deseleccionar_todos(self):
        # Deseleccionar todos los objetos de la capa activa
        active_layer = self.iface.activeLayer()
        
        # Si no hay capa activa o no es una capa de líneas, usar la del combo
        if not active_layer or active_layer.type() != active_layer.VectorLayer or active_layer.geometryType() != 1:
            if self.combo_base.count() > 0 and self.combo_base.currentData():
                layer_id = self.combo_base.currentData()
                active_layer = QgsProject.instance().mapLayer(layer_id)
                if active_layer:
                    self.iface.setActiveLayer(active_layer)
        
        if active_layer:
            # Guardar el número de objetos que estaban seleccionados
            num_selected = active_layer.selectedFeatureCount()
            
            # Deseleccionar
            active_layer.removeSelection()
            
            # Opcional: desmarcar el checkbox de usar selección
            self.check_seleccionadas.setChecked(False)
            
            # Actualizar el combo para mostrar la capa activa
            index = self.combo_base.findData(active_layer.id())
            if index >= 0:
                self.combo_base.setCurrentIndex(index)
            
            # Mostrar mensaje en la barra de estado
            self.iface.messageBar().pushMessage(
                "Deselección", 
                f"Se han deseleccionado {num_selected} objetos en la capa {active_layer.name()}", 
                Qgis.MessageLevel.Success, 
                3  # Duración en segundos
            )
            
            # Forzar la actualización del canvas
            self.iface.mapCanvas().refresh()

    def closeEvent(self, event):
        # Desactivar herramienta de mapa si está activa al cerrar el panel
        if self.map_tool and self.iface.mapCanvas().mapTool() == self.map_tool:
            self.iface.mapCanvas().unsetMapTool(self.map_tool)
        super().closeEvent(event)

    def load_line_layers(self):
        current_id = self.combo_base.currentData() if self.combo_base.count() > 0 else None
        self.combo_base.clear()
        
        has_layers = False
        for layer in QgsProject.instance().mapLayers().values():
            if layer.type() == layer.VectorLayer and layer.geometryType() == 1:
                self.combo_base.addItem(layer.name(), layer.id())
                has_layers = True
                
                # Mantener la selección previa si la capa sigue existiendo
                if layer.id() == current_id:
                    self.combo_base.setCurrentIndex(self.combo_base.count() - 1)
        
        # Verificar si la capa activa es una capa de líneas y seleccionarla en el combo
        active_layer = self.iface.activeLayer()
        if active_layer and active_layer.type() == active_layer.VectorLayer and active_layer.geometryType() == 1:
            index = self.combo_base.findData(active_layer.id())
            if index >= 0:
                self.combo_base.setCurrentIndex(index)
        
        # Habilitar o deshabilitar el botón según haya capas disponibles
        self.btn_generar.setEnabled(has_layers)
        
        if not has_layers:
            self.combo_base.addItem("No hay capas de líneas disponibles")

    # NUEVA FUNCIÓN
    def load_polygon_layers(self):
        """Carga las capas de polígonos en el combobox"""
        current_id = self.combo_poligono.currentData() if self.combo_poligono.count() > 1 else None
        self.combo_poligono.clear()
        
        # Añadir opción "Ninguna" al principio
        self.combo_poligono.addItem("Ninguna", None)
        
        sectores_encontrados = False
        
        for layer in QgsProject.instance().mapLayers().values():
            if layer.type() == layer.VectorLayer and layer.geometryType() == 2:  # Polígonos
                self.combo_poligono.addItem(layer.name(), layer.id())
                
                # Si encuentra la capa "Sectores", seleccionarla por defecto
                if layer.name() == "Sectores" and not sectores_encontrados:
                    self.combo_poligono.setCurrentIndex(self.combo_poligono.count() - 1)
                    sectores_encontrados = True
                    
                # Mantener la selección previa si la capa sigue existiendo
                if layer.id() == current_id:
                    self.combo_poligono.setCurrentIndex(self.combo_poligono.count() - 1)
        
        # Habilitar el checkbox de extender solo si hay capas de polígonos
        self.check_extender.setEnabled(self.combo_poligono.count() > 1)

    def activar_dibujo(self):
        # Limpiar herramienta anterior si existe
        if self.map_tool:
            if self.map_tool.rb:
                self.map_tool.rb.reset()
        
        self.map_tool = MapToolDireccionAvanzado(self.iface, self)
        self.iface.mapCanvas().setMapTool(self.map_tool)
        
        # Mostrar mensaje en la barra de estado
        self.iface.messageBar().pushMessage(
            "Dibujo de dirección", 
            "Dibuje una línea para definir la dirección de las líneas a generar", 
            Qgis.MessageLevel.Info, 
            5  # Duración en segundos
        )

    def set_linea_direccion(self, linea):
        self.linea_direccion = linea
        # Usar la barra de mensajes en lugar de una ventana emergente
        self.iface.messageBar().pushMessage(
            "Línea capturada", 
            "Dirección definida correctamente", 
            Qgis.MessageLevel.Success, 
            3  # Duración en segundos
        )

    def generar_lineas(self):
        """Función principal para generar líneas, con soporte para extender hasta polígonos"""
        if not self.linea_direccion:
            QMessageBox.warning(self, "Falta dirección", "Primero debe dibujar la línea de dirección.")
            return
                
        if self.combo_base.count() == 0 or not self.combo_base.currentData():
            QMessageBox.warning(self, "Sin capa base", "No hay capa de líneas seleccionada.")
            return
                
        layer_id = self.combo_base.currentData()
        base_layer = QgsProject.instance().mapLayer(layer_id)
        
        if not base_layer:
            QMessageBox.warning(self, "Error", "La capa seleccionada ya no existe.")
            self.load_line_layers()
            return
                
        if base_layer.featureCount() == 0:
            QMessageBox.warning(self, "Capa vacía", "La capa seleccionada no contiene entidades.")
            return
        
        # Verificar si se debe usar solo entidades seleccionadas
        usar_seleccion = self.check_seleccionadas.isChecked()
        
        # Si está marcada la opción de selección, verificar que haya entidades seleccionadas
        if usar_seleccion and base_layer.selectedFeatureCount() == 0:
            QMessageBox.warning(self, "Sin selección", "No hay entidades seleccionadas en la capa base.")
            return
        
        # Verificar si se debe extender hasta el polígono
        extender_poligono = self.check_extender.isChecked()
        polygon_layer = None
        
        if extender_poligono:
            if not self.combo_poligono.currentData():
                QMessageBox.warning(self, "Sin polígono seleccionado", "Está pendiente la selección de un polígono.")
                return
                
            polygon_layer_id = self.combo_poligono.currentData()
            polygon_layer = QgsProject.instance().mapLayer(polygon_layer_id)
            
            if not polygon_layer or polygon_layer.featureCount() == 0:
                QMessageBox.warning(self, "Capa polígono inválida", "La capa de polígonos seleccionada no existe o está vacía.")
                return
        
        espaciado = self.spin_espaciado.value()
        longitud = self.spin_longitud.value()
        offset = self.spin_offset.value()
        lado = self.combo_lado.currentIndex()
        
        try:
            # Mostrar mensaje de procesamiento
            self.iface.messageBar().pushMessage(
                "Generando líneas", 
                "Procesando...", 
                Qgis.MessageLevel.Info
            )
            
            # Procesar eventos para que se muestre el mensaje
            QCoreApplication.processEvents()
            
            if extender_poligono:
                # Crear la capa de líneas temporales utilizando la función integrada y luego extender
                temp_layer = generar_lineas(base_layer, self.linea_direccion, 
                                         espaciado, longitud, offset, lado, 
                                         None, usar_seleccion)
                
                # Extender las líneas hasta los polígonos
                self.result_layer = self.extender_lineas_hasta_poligono(temp_layer, polygon_layer)
                
                # Eliminar la capa temporal del proyecto (ya que se ha creado una nueva)
                QgsProject.instance().removeMapLayer(temp_layer.id())
            else:
                # Usar la función original sin extender
                self.result_layer = generar_lineas(base_layer, self.linea_direccion, 
                                         espaciado, longitud, offset, lado, 
                                         None, usar_seleccion)
                                         
            # Limpiar mensajes anteriores
            self.iface.messageBar().clearWidgets()
            
            if self.result_layer and self.result_layer.featureCount() > 0:
                # Habilitar el botón para copiar a Red de riego
                self.btn_copiar_red.setEnabled(True)
                
                # Mostrar mensaje de éxito en la barra de mensajes
                self.iface.messageBar().pushMessage(
                    "Éxito", 
                    f"Se han generado {self.result_layer.featureCount()} líneas.", 
                    Qgis.MessageLevel.Success, 
                    5  # Duración en segundos
                )
            else:
                self.btn_copiar_red.setEnabled(False)
                QMessageBox.warning(self, "Aviso", "No se generaron líneas. Verifique los parámetros.")
        except Exception as e:
            # Limpiar mensajes anteriores
            self.iface.messageBar().clearWidgets()
            self.btn_copiar_red.setEnabled(False)
            QMessageBox.critical(self, "Error", f"Error al generar líneas: {str(e)}")

    def extender_lineas_hasta_poligono(self, lineas_layer, polygon_layer):
        """
        Extiende las líneas generadas hasta los bordes del polígono que las contiene
        
        Args:
            lineas_layer: Capa con las líneas a extender
            polygon_layer: Capa de polígonos hasta donde extender
            
        Returns:
            Nueva capa de memoria con las líneas extendidas
        """
        # Crear una nueva capa en memoria para las líneas extendidas
        extended_layer = QgsVectorLayer(f"LineString?crs={lineas_layer.crs().authid()}", "Líneas extendidas", "memory")
        extended_provider = extended_layer.dataProvider()
        
        # Configurar los campos igual que la capa original
        extended_provider.addAttributes(lineas_layer.fields().toList())
        extended_layer.updateFields()
        
        # Convertir polígonos en una lista más una geometría unida para detectar contención
        polygons = list(polygon_layer.getFeatures())
        
        # Verificamos si hay al menos un polígono
        if not polygons:
            return lineas_layer
        
        # Estrategia: usar una unión de polígonos para detección inicial
        union_geom = polygons[0].geometry()
        for i in range(1, len(polygons)):
            union_geom = union_geom.combine(polygons[i].geometry())
        
        # Procesamos cada línea
        for linea_feature in lineas_layer.getFeatures():
            geom = linea_feature.geometry()
            if geom.isNull() or not geom.isGeosValid():
                continue
                
            # Obtener los puntos de la línea
            line = geom.asPolyline()
            if len(line) < 2:
                continue
            
            # Determinar el punto inicial (centro) de la línea para mayor robustez
            # Esto ayuda con líneas que podrían estar parcialmente fuera del polígono
            mid_point_idx = len(line) // 2
            mid_point = line[mid_point_idx]
            
            # Calcular la dirección usando puntos extremos para mayor precisión
            start_point = line[0]
            end_point = line[-1]
            
            # Vector dirección (normalizado)
            dx = end_point.x() - start_point.x()
            dy = end_point.y() - start_point.y()
            length = math.sqrt(dx*dx + dy*dy)
            
            if length == 0:
                continue  # Evitar divisiones por cero
                
            dx = dx / length
            dy = dy / length
            
            # Verificar si la línea está dentro de algún polígono
            if not union_geom.contains(QgsGeometry.fromPointXY(mid_point)):
                # Si el punto medio no está dentro de ningún polígono, mantener la línea original
                new_feature = QgsFeature(lineas_layer.fields())
                new_feature.setGeometry(geom)
                for i in range(linea_feature.attributeCount()):
                    new_feature.setAttribute(i, linea_feature.attribute(i))
                extended_provider.addFeature(new_feature)
                continue
            
            # Encontrar el polígono específico que contiene el punto medio
            containing_polygon = None
            for poly_feature in polygons:
                poly_geom = poly_feature.geometry()
                if poly_geom.contains(QgsGeometry.fromPointXY(mid_point)):
                    containing_polygon = poly_geom
                    break
            
            if not containing_polygon:
                # Caso improbable pero posible por errores numéricos, mantener original
                new_feature = QgsFeature(lineas_layer.fields())
                new_feature.setGeometry(geom)
                for i in range(linea_feature.attributeCount()):
                    new_feature.setAttribute(i, linea_feature.attribute(i))
                extended_provider.addFeature(new_feature)
                continue
            
            # Extender la línea con una distancia extremadamente grande
            extender_distance = 100000000  # 100,000 km para garantizar intersección
            
            # Crear puntos extremos para la línea extendida
            ext_start = QgsPointXY(mid_point.x() - dx * extender_distance, 
                                  mid_point.y() - dy * extender_distance)
            ext_end = QgsPointXY(mid_point.x() + dx * extender_distance, 
                                mid_point.y() + dy * extender_distance)
            
            # Crear una línea extendida a partir del punto medio
            extended_line = QgsGeometry.fromPolylineXY([ext_start, ext_end])
            
            # Calcular la intersección con el polígono contenedor
            intersection = extended_line.intersection(containing_polygon)
            
            # Si tenemos una intersección válida, usar esa geometría
            if not intersection.isEmpty():
                if intersection.type() == QgsWkbTypes.LineGeometry:
                    new_feature = QgsFeature(lineas_layer.fields())
                    new_feature.setGeometry(intersection)
                    for i in range(linea_feature.attributeCount()):
                        new_feature.setAttribute(i, linea_feature.attribute(i))
                    extended_provider.addFeature(new_feature)
                else:
                    # Mantener la línea original si la intersección no es una línea
                    new_feature = QgsFeature(lineas_layer.fields())
                    new_feature.setGeometry(geom)
                    for i in range(linea_feature.attributeCount()):
                        new_feature.setAttribute(i, linea_feature.attribute(i))
                    extended_provider.addFeature(new_feature)
            else:
                # Si no hay intersección, mantener la línea original
                new_feature = QgsFeature(lineas_layer.fields())
                new_feature.setGeometry(geom)
                for i in range(linea_feature.attributeCount()):
                    new_feature.setAttribute(i, linea_feature.attribute(i))
                extended_provider.addFeature(new_feature)
        
        # Agregar la capa al proyecto
        QgsProject.instance().addMapLayer(extended_layer)
        
        return extended_layer
    
    def copiar_a_red_riego(self):
        """Copia las líneas generadas a la capa Red de riego como laterales DN 16 y elimina la capa temporal"""
        
        if not self.result_layer or self.result_layer.featureCount() == 0:
            QMessageBox.warning(self, "Error", "No hay líneas generadas para copiar.")
            return
            
        # Buscar la capa Red de riego
        red_riego_layer = None
        for layer in QgsProject.instance().mapLayers().values():
            if layer.type() == layer.VectorLayer and layer.name() == "Red de riego":
                red_riego_layer = layer
                break
                
        if not red_riego_layer:
            QMessageBox.warning(self, "Error", "No se encontró la capa 'Red de riego'. Verifique que existe.")
            return
            
        try:
            # Verificar que los campos necesarios existen
            required_fields = ["Tipo", "DN"]
            missing_fields = []
            for field in required_fields:
                if red_riego_layer.fields().indexFromName(field) == -1:
                    missing_fields.append(field)
                    
            if missing_fields:
                QMessageBox.warning(self, "Error", f"La capa 'Red de riego' no tiene los campos necesarios: {', '.join(missing_fields)}")
                return
                
            # Comenzar la edición de la capa
            red_riego_layer.startEditing()
            
            # Mostrar mensaje de procesamiento
            self.iface.messageBar().pushMessage(
                "Copiando líneas", 
                "Procesando...", 
                Qgis.MessageLevel.Info
            )
            
            # Procesar eventos para que se muestre el mensaje
            QCoreApplication.processEvents()
            
            # Copiar todas las entidades
            features_added = 0
            for feature in self.result_layer.getFeatures():
                new_feature = QgsFeature(red_riego_layer.fields())
                
                # Copiar la geometría
                new_feature.setGeometry(feature.geometry())
                
                # Establecer atributos específicos
                for i, field in enumerate(red_riego_layer.fields()):
                    if field.name() == "Tipo":
                        new_feature.setAttribute(i, "Laterales")
                    elif field.name() == "DN":
                        new_feature.setAttribute(i, 16)
                    elif field.name() == "id":
                        # Si hay un campo id, intentar asignar un ID único
                        try:
                            max_id = 0
                            for f in red_riego_layer.getFeatures():
                                if f["id"] and int(f["id"]) > max_id:
                                    max_id = int(f["id"])
                            new_feature.setAttribute(i, max_id + 1)
                        except:
                            pass  # Si hay algún error, ignorar y dejar el ID vacío
                
                # Añadir la entidad
                red_riego_layer.addFeature(new_feature)
                features_added += 1
                
            # Guardar los cambios
            red_riego_layer.commitChanges()
            
            # Guardar referencia al ID de la capa resultado para eliminarla
            result_layer_id = self.result_layer.id()
            
            # Limpiar la referencia en la clase
            self.result_layer = None
            
            # Eliminar la capa de líneas generadas del proyecto
            QgsProject.instance().removeMapLayer(result_layer_id)
            
            # Deshabilitar el botón de copiar ya que no hay líneas para copiar
            self.btn_copiar_red.setEnabled(False)
            
            # Actualizar el canvas
            self.iface.mapCanvas().refresh()
            
            # Limpiar mensajes anteriores
            self.iface.messageBar().clearWidgets()
            
            # Mostrar mensaje de éxito
            self.iface.messageBar().pushMessage(
                "Éxito", 
                f"Se han copiado {features_added} líneas a la capa 'Red de riego' como laterales DN 16 y se ha eliminado la capa temporal.", 
                Qgis.MessageLevel.Success, 
                5  # Duración en segundos
            )
            
        except Exception as e:
            # En caso de error, cancelar la edición
            if red_riego_layer and red_riego_layer.isEditable():
                red_riego_layer.rollBack()
                
            # Limpiar mensajes anteriores
            self.iface.messageBar().clearWidgets()
            
            # Mostrar error
            QMessageBox.critical(self, "Error", f"Error al copiar las líneas: {str(e)}")

    def show_and_activate(self):
        """Muestra y activa el panel, trayéndolo al frente"""
        self.show()
        self.raise_()
        self.activateWindow()