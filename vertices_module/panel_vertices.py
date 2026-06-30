import os
import math
from qgis.PyQt.QtWidgets import (QDockWidget, QWidget, QVBoxLayout, QLabel, 
                               QPushButton, QComboBox, QMessageBox, QFileDialog,
                               QRadioButton, QButtonGroup, QHBoxLayout, QCheckBox, QGroupBox)
from qgis.PyQt.QtCore import Qt, QVariant, QMetaType
from qgis.PyQt.QtGui import QIcon, QColor
from qgis.core import (QgsVectorLayer, QgsFeature, QgsGeometry, QgsField, 
                     QgsFields, QgsPointXY, QgsProject, QgsWkbTypes,
                     QgsFeatureRequest, QgsSpatialIndex, QgsCoordinateTransform,
                     QgsSymbol, QgsMarkerSymbol, QgsSingleSymbolRenderer, Qgis,
                     QgsCoordinateReferenceSystem)
from qgis.utils import iface
from qgis.gui import QgsProjectionSelectionWidget

class PanelVertices(QDockWidget):
    def __init__(self, iface):
        super(PanelVertices, self).__init__("Extracción de Vértices de Polígonos")
        self.iface = iface
        self.plugin_dir = os.path.dirname(os.path.dirname(__file__))
        self.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)
        
        # Conectar evento de cierre para actualizar estado
        self.closeEvent = self.on_close_event
        
        # Crear y configurar la interfaz gráfica
        self.setup_gui()

    def on_close_event(self, event):
        """Maneja el evento de cierre de la ventana"""
        # No es necesario mantener una variable is_open, usamos isVisible() directamente
        event.accept()

    def setup_gui(self):
        """Configura la interfaz gráfica del panel"""
        # Widget principal
        main_widget = QWidget()
        layout = QVBoxLayout()
        main_widget.setLayout(layout)
        
        # Etiqueta para la capa
        layer_label = QLabel("Seleccione la capa de polígonos:")
        layout.addWidget(layer_label)
        
        # Selector de capa de polígonos
        self.layer_combo = QComboBox()
        layout.addWidget(self.layer_combo)
        
        # Botón para actualizar las capas
        refresh_button = QPushButton("Actualizar Capas")
        refresh_button.clicked.connect(self.update_layers)
        layout.addWidget(refresh_button)
        
        # Opciones para el sistema de coordenadas
        coords_layout = QHBoxLayout()
        coords_label = QLabel("Sistema de coordenadas para X,Y:")
        self.coords_group = QButtonGroup()
        self.rb_project = QRadioButton("Proyecto")
        self.rb_capa = QRadioButton("Capa")
        self.coords_group.addButton(self.rb_project)
        self.coords_group.addButton(self.rb_capa)
        self.rb_project.setChecked(True)
        
        coords_layout.addWidget(coords_label)
        coords_layout.addWidget(self.rb_project)
        coords_layout.addWidget(self.rb_capa)
        layout.addLayout(coords_layout)
        
        # Grupo para coordenadas adicionales en otro SRC
        self.coords_extra_group = QGroupBox("Coordenadas adicionales en otro SRC (opcionales)")
        coords_extra_layout = QVBoxLayout()
        self.coords_extra_group.setLayout(coords_extra_layout)
        self.coords_extra_group.setCheckable(True)
        self.coords_extra_group.setChecked(False)
        
        # Selector de SRC adicional
        crs_label = QLabel("Seleccione el sistema de referencia de coordenadas:")
        coords_extra_layout.addWidget(crs_label)
        
        self.crs_selector = QgsProjectionSelectionWidget()
        # Por defecto WGS84 (EPSG:4326)
        self.crs_selector.setCrs(QgsCoordinateReferenceSystem("EPSG:4326"))
        coords_extra_layout.addWidget(self.crs_selector)
        
        layout.addWidget(self.coords_extra_group)
        
        # Opción para incluir cálculo de azimut
        self.chk_azimut = QCheckBox("Incluir cálculo de azimut")
        self.chk_azimut.setChecked(True)  # Por defecto habilitado
        layout.addWidget(self.chk_azimut)
        
        # Opción para exportar a CSV
        self.chk_csv = QCheckBox("Exportar también a CSV")
        layout.addWidget(self.chk_csv)
        
        # Botón para ejecutar la extracción
        extract_button = QPushButton("Extraer Vértices")
        extract_button.clicked.connect(self.extract_vertices)
        layout.addWidget(extract_button)
        
        # Espacio flexible al final
        layout.addStretch(1)
        
        # Establecer el widget principal como widget central
        self.setWidget(main_widget)
        
        # Actualizar la lista de capas
        self.update_layers()

    def update_layers(self):
        """Actualiza la lista de capas de polígonos disponibles"""
        self.layer_combo.clear()
        
        # Obtener todas las capas de polígonos del proyecto
        for layer in QgsProject.instance().mapLayers().values():
            if layer.type() == QgsVectorLayer.VectorLayer and layer.geometryType() == QgsWkbTypes.PolygonGeometry:
                self.layer_combo.addItem(layer.name(), layer.id())

    def show_and_activate(self):
        """Muestra y activa el panel"""
        self.show()
        self.raise_()
        
    def toggle_panel(self):
        """Alterna la visibilidad del panel"""
        if self.isVisible():
            self.hide()
        else:
            self.show()
            self.raise_()

    def calculate_azimuth(self, p1, p2):
        """
        Calcula el azimut entre dos puntos en grados.
        El azimut es el ángulo medido en sentido horario desde el norte.
        
        Args:
            p1 (QgsPointXY): Punto de origen
            p2 (QgsPointXY): Punto de destino
            
        Returns:
            float: Azimut en grados (0-360)
        """
        # Vector desde p1 a p2
        dx = p2.x() - p1.x()
        dy = p2.y() - p1.y()
        
        # Calcular azimut (ángulo en sentido horario desde el eje Y positivo/Norte)
        azimuth = math.atan2(dx, dy)  # Atan2 invierte x,y para medir desde el Norte
        
        # Convertir a grados y normalizar a [0, 360]
        azimuth_deg = math.degrees(azimuth)
        if azimuth_deg < 0:
            azimuth_deg += 360
            
        return azimuth_deg

    def is_polygon_clockwise(self, points):
        """
        Determina si un polígono está orientado en sentido horario.
        Usa la fórmula de área con producto cruzado.
        """
        # Eliminar el último punto si es igual al primero (polígono cerrado)
        if points[0].x() == points[-1].x() and points[0].y() == points[-1].y():
            points = points[:-1]
            
        # Calcular el área con el signo usando el método del producto cruzado
        area = 0
        for i in range(len(points)):
            j = (i + 1) % len(points)
            area += (points[j].x() - points[i].x()) * (points[j].y() + points[i].y())
            
        # Si el área es negativa, el polígono está en sentido horario
        return area < 0

    def calculate_angle_clockwise(self, p1, p2, p3):
        """
        Calcula el ángulo interior para un vértice P2 en un polígono en sentido horario.
        
        Args:
            p1: Punto anterior
            p2: Punto vértice (donde queremos medir el ángulo)
            p3: Punto siguiente
            
        Returns:
            float: Ángulo interno en grados (0-360)
        """
        # Crear vectores desde p2 a p1 y p3
        v1x = p1.x() - p2.x()
        v1y = p1.y() - p2.y()
        v2x = p3.x() - p2.x()
        v2y = p3.y() - p2.y()
        
        # Calcular el producto escalar
        dot = v1x * v2x + v1y * v2y
        # Calcular las magnitudes de los vectores
        mag1 = math.sqrt(v1x**2 + v1y**2)
        mag2 = math.sqrt(v2x**2 + v2y**2)
        
        # Evitar división por cero
        if mag1 == 0 or mag2 == 0:
            return 0
            
        # Calcular el coseno del ángulo
        cos_angle = dot / (mag1 * mag2)
        # Limitar al rango [-1, 1] para evitar errores numéricos
        cos_angle = max(-1.0, min(1.0, cos_angle))
        
        # Calcular el ángulo en radianes usando arccos
        angle_rad = math.acos(cos_angle)
        
        # Determinar si es un ángulo convexo o cóncavo usando producto cruzado
        cross = v1x * v2y - v1y * v2x
        
        # Convertir a grados
        angle_deg = math.degrees(angle_rad)
        
        # Para polígonos en sentido horario: 
        # - Si el producto cruzado es negativo, es un ángulo convexo (< 180°)
        # - Si el producto cruzado es positivo, es un ángulo cóncavo (> 180°)
        if cross > 0:
            angle_deg = 360 - angle_deg
            
        return angle_deg

    def extract_vertices(self):
        """Extrae los vértices de los polígonos seleccionados"""
        # Verificar si hay capas seleccionadas
        if self.layer_combo.count() == 0:
            QMessageBox.warning(self, "Advertencia", "No hay capas de polígonos disponibles")
            return
        
        # Obtener la capa seleccionada
        layer_id = self.layer_combo.currentData()
        if not layer_id:
            QMessageBox.warning(self, "Advertencia", "Seleccione una capa de polígonos")
            return
        
        layer = QgsProject.instance().mapLayer(layer_id)
        if not layer:
            QMessageBox.warning(self, "Error", "No se pudo acceder a la capa seleccionada")
            return
        
        # Sistema de coordenadas para X,Y
        use_project_crs = self.rb_project.isChecked()
        
        # Verificar si se usarán coordenadas adicionales
        use_extra_coords = self.coords_extra_group.isChecked()
        extra_crs = None
        transform_to_extra = None
        
        if use_extra_coords:
            extra_crs = self.crs_selector.crs()
            if not extra_crs.isValid():
                QMessageBox.warning(self, "Error", "El sistema de coordenadas adicional no es válido")
                return
        
        # Verificar si se incluirá el azimut
        include_azimuth = self.chk_azimut.isChecked()
        
        # Crear los campos para la capa de salida
        fields = QgsFields()
        
        # Campos básicos
        vertice_field = QgsField()
        vertice_field.setName("Vertice")
        vertice_field.setType(QMetaType.Type.Int)
        fields.append(vertice_field)
        
        lado_field = QgsField()
        lado_field.setName("Lado")
        lado_field.setType(QMetaType.Type.QString)
        fields.append(lado_field)
        
        distancia_field = QgsField()
        distancia_field.setName("Distancia")
        distancia_field.setType(QMetaType.Type.Double)
        distancia_field.setTypeName("double")
        distancia_field.setLength(10)
        distancia_field.setPrecision(3)
        fields.append(distancia_field)
        
        angulo_field = QgsField()
        angulo_field.setName("Angulo")
        angulo_field.setType(QMetaType.Type.Double)
        angulo_field.setTypeName("double")
        angulo_field.setLength(10)
        angulo_field.setPrecision(2)
        fields.append(angulo_field)
        
        # Campo para azimut si está habilitado
        if include_azimuth:
            azimut_field = QgsField()
            azimut_field.setName("Azimut")
            azimut_field.setType(QMetaType.Type.Double)
            azimut_field.setTypeName("double")
            azimut_field.setLength(10)
            azimut_field.setPrecision(2)
            fields.append(azimut_field)
        
        x_field = QgsField()
        x_field.setName("X")
        x_field.setType(QMetaType.Type.Double)
        x_field.setTypeName("double")
        x_field.setLength(15)
        x_field.setPrecision(6)
        fields.append(x_field)
        
        y_field = QgsField()
        y_field.setName("Y")
        y_field.setType(QMetaType.Type.Double)
        y_field.setTypeName("double")
        y_field.setLength(15)
        y_field.setPrecision(6)
        fields.append(y_field)
        
        # Campos para coordenadas adicionales si están habilitadas
        if use_extra_coords:
            x2_field = QgsField()
            x2_field.setName(f"X_{extra_crs.authid().replace(':', '_')}")
            x2_field.setType(QMetaType.Type.Double)
            x2_field.setTypeName("double")
            x2_field.setLength(15)
            x2_field.setPrecision(6)
            fields.append(x2_field)
            
            y2_field = QgsField()
            y2_field.setName(f"Y_{extra_crs.authid().replace(':', '_')}")
            y2_field.setType(QMetaType.Type.Double)
            y2_field.setTypeName("double")
            y2_field.setLength(15)
            y2_field.setPrecision(6)
            fields.append(y2_field)
        
        id_field = QgsField()
        id_field.setName("ID_Poligono")
        id_field.setType(QMetaType.Type.Int)
        fields.append(id_field)
        
        # Crear capa temporal de puntos con el mismo sistema de coordenadas que la original
        # Esto evita problemas de transformación y visualización
        # Usamos el sistema de coordenadas de la capa original para crear la capa de vértices
        capa_id = f"vertices_{layer.name().lower().replace(' ', '_')}"
        vertices_layer = QgsVectorLayer(f"Point?crs={layer.crs().authid()}", f"Vertices_{layer.name()}", "memory")
        
        # Establecer ID personalizado como propiedad de la capa
        vertices_layer.setCustomProperty("identificador", capa_id)
        vertices_provider = vertices_layer.dataProvider()
        
        # Añadir los campos a la capa
        vertices_provider.addAttributes(fields.toList())
        vertices_layer.updateFields()
        
        # Transformación de coordenadas si es necesario
        project_crs = QgsProject.instance().crs()
        layer_crs = layer.crs()
        
        transform = None
        # Verificamos si hay una transformación necesaria y si es válida
        if use_project_crs and project_crs != layer_crs:
            try:
                transform = QgsCoordinateTransform(layer_crs, project_crs, QgsProject.instance())
                # Probamos la transformación con un punto para verificar que funcione
                test_point = QgsPointXY(layer.extent().center())
                transform.transform(test_point)  # Verifica si la transformación es válida
            except Exception as e:
                # Si hay error en la transformación, mostramos mensaje y usamos las coordenadas originales
                self.iface.messageBar().pushMessage(
                    "Advertencia", 
                    "No se pudo aplicar la transformación de coordenadas. Se usarán las coordenadas del sistema de la capa.",
                    level=Qgis.MessageLevel.Warning,
                    duration=5
                )
                transform = None
                use_project_crs = False
        
        # Transformación para coordenadas adicionales si están habilitadas
        if use_extra_coords:
            # Determinamos desde qué CRS transformaremos (proyecto o capa)
            source_crs = project_crs if use_project_crs else layer_crs
            try:
                transform_to_extra = QgsCoordinateTransform(source_crs, extra_crs, QgsProject.instance())
                # Verificar que funciona
                test_point = QgsPointXY(0, 0)
                transform_to_extra.transform(test_point)
            except Exception as e:
                self.iface.messageBar().pushMessage(
                    "Advertencia", 
                    f"No se pudo configurar la transformación a {extra_crs.authid()}. No se incluirán coordenadas adicionales.",
                    level=Qgis.MessageLevel.Warning,
                    duration=5
                )
                use_extra_coords = False
                transform_to_extra = None
        
        # Variable para saber si exportaremos a CSV
        export_to_csv = self.chk_csv.isChecked()
        
        # Solo preparamos datos para CSV si la opción está marcada
        features_data = []
        if export_to_csv:
            # Preparar encabezados según las opciones habilitadas
            csv_headers = ["ID_Poligono", "Vertice", "Lado", "Distancia", "Angulo"]
            if include_azimuth:
                csv_headers.append("Azimut")
            csv_headers.extend(["X", "Y"])
            if use_extra_coords:
                csv_headers.extend([f"X_{extra_crs.authid().replace(':', '_')}", 
                                  f"Y_{extra_crs.authid().replace(':', '_')}"])
        
        # Contador para ID de polígono
        polygon_id = 1
        
        # Procesar cada polígono de la capa
        for polygon_feature in layer.getFeatures():
            # Obtener la geometría
            geometry = polygon_feature.geometry()
            
            # Asegurarnos de que es un polígono
            if geometry.type() != QgsWkbTypes.PolygonGeometry:
                continue
                
            # Extraer vértices (para multipolígonos, procesar cada parte)
            if geometry.isMultipart():
                polygons = geometry.asMultiPolygon()
            else:
                polygons = [geometry.asPolygon()]
            
            for polygon in polygons:
                for ring in polygon:
                    # Cerrar el anillo si no está cerrado
                    if ring[0] != ring[-1]:
                        ring.append(ring[0])
                    
                    # Obtener los vértices del anillo (evitando el último, que es duplicado)
                    num_vertices = len(ring) - 1
                    
                    # Guardar los puntos transformados si es necesario
                    transformed_points = []
                    for point in ring:
                        try:
                            if transform:
                                # Transformar al CRS del proyecto si es necesario
                                point_xy = QgsPointXY(point)
                                transformed_point = transform.transform(point_xy)
                                transformed_points.append(transformed_point)
                            else:
                                transformed_points.append(QgsPointXY(point))
                        except Exception as e:
                            # Si falla la transformación para este punto, usamos el punto original
                            print(f"Error transformando punto: {str(e)}")
                            transformed_points.append(QgsPointXY(point))
                    
                    # Determinar la orientación del polígono (horario o antihorario)
                    is_clockwise = self.is_polygon_clockwise(transformed_points)
                    
                    # Procesar todos los vértices
                    for i in range(num_vertices):
                        # Punto anterior, actual y siguiente
                        prev_i = (i - 1) % num_vertices
                        next_i = (i + 1) % num_vertices
                        
                        # Puntos para cálculos
                        prev_point = transformed_points[prev_i]
                        current_point = transformed_points[i]
                        next_point = transformed_points[next_i]
                        
                        # Calcular distancia al siguiente punto
                        distance = math.sqrt((next_point.x() - current_point.x())**2 + 
                                            (next_point.y() - current_point.y())**2)
                        
                        # Aplicar diferentes cálculos de ángulos según la orientación del polígono
                        if is_clockwise:
                            # Para polígonos en sentido horario
                            # Para obtener el ángulo interno en sentido horario, usamos los puntos en orden: previo, actual, siguiente
                            angle = self.calculate_angle_clockwise(prev_point, current_point, next_point)
                        else:
                            # Para polígonos en sentido antihorario
                            # Para obtener el ángulo interno en sentido antihorario, usamos los puntos en orden inverso: siguiente, actual, previo
                            angle = self.calculate_angle_clockwise(next_point, current_point, prev_point)
                        
                        # Calcular azimut si está habilitado
                        azimuth = 0
                        if include_azimuth:
                            azimuth = self.calculate_azimuth(current_point, next_point)
                        
                        # Crear lado (formato: 1-2, 2-3, etc.)
                        vertex_num = i + 1
                        next_vertex_num = next_i + 1
                        lado = f"{vertex_num}-{next_vertex_num}"
                        
                        # Transformar a coordenadas adicionales si está habilitado
                        extra_x = 0
                        extra_y = 0
                        if use_extra_coords and transform_to_extra:
                            try:
                                extra_point = transform_to_extra.transform(current_point)
                                extra_x = extra_point.x()
                                extra_y = extra_point.y()
                            except Exception as e:
                                print(f"Error transformando a coordenadas adicionales: {str(e)}")
                        
                        # Crear feature con punto
                        feature = QgsFeature(fields)
                        feature.setGeometry(QgsGeometry.fromPointXY(current_point))
                        
                        # Configurar atributos según opciones habilitadas
                        attributes = [
                            vertex_num,             # Vértice
                            lado,                   # Lado
                            distance,               # Distancia
                            angle,                  # Ángulo
                        ]
                        
                        if include_azimuth:
                            attributes.append(azimuth)  # Azimut
                            
                        attributes.extend([
                            current_point.x(),      # X
                            current_point.y(),      # Y
                        ])
                        
                        if use_extra_coords:
                            attributes.extend([
                                extra_x,            # X en SRC adicional
                                extra_y,            # Y en SRC adicional
                            ])
                            
                        attributes.append(polygon_id)  # ID_Poligono
                        
                        feature.setAttributes(attributes)
                        
                        # Añadir a la capa
                        vertices_provider.addFeature(feature)
                        
                        # Solo añadir al CSV si la opción está marcada
                        if export_to_csv:
                            # Preparar datos CSV según opciones habilitadas
                            row_data = [
                                polygon_id, 
                                vertex_num, 
                                lado, 
                                f"{distance:.3f}", 
                                f"{angle:.2f}"
                            ]
                            
                            if include_azimuth:
                                row_data.append(f"{azimuth:.2f}")
                                
                            row_data.extend([
                                f"{current_point.x():.6f}", 
                                f"{current_point.y():.6f}"
                            ])
                            
                            if use_extra_coords:
                                row_data.extend([
                                    f"{extra_x:.6f}",
                                    f"{extra_y:.6f}"
                                ])
                                
                            features_data.append(row_data)
                
                # Incrementar ID de polígono para el siguiente
                polygon_id += 1
        
        # Actualizar la capa
        vertices_layer.updateExtents()
        
        # Aplicar estilo a la capa para visualización correcta
        self.apply_style_to_layer(vertices_layer)
        
        # Añadir al proyecto
        QgsProject.instance().addMapLayer(vertices_layer)
        
        # Exportar a CSV SOLAMENTE si está marcada la opción
        if export_to_csv and features_data:
            try:
                self.export_to_csv(csv_headers, features_data)
            except Exception as e:
                # Mostrar error como mensaje de estado
                self.iface.messageBar().pushMessage(
                    "Error", 
                    f"No se pudo exportar a CSV: {str(e)}", 
                    level=Qgis.MessageLevel.Warning,
                    duration=5
                )
        
        # Preparar mensaje de éxito con detalles de las opciones utilizadas
        mensaje = f"Se han extraído {vertices_provider.featureCount()} vértices. La capa '{vertices_layer.name()}' se ha creado."
        
        if include_azimuth:
            mensaje += " Incluye cálculo de azimut."
            
        if use_extra_coords:
            mensaje += f" Incluye coordenadas en {extra_crs.authid()}."
            
        # Mostrar mensaje de éxito como mensaje de estado
        self.iface.messageBar().pushMessage(
            "Extracción Completada", 
            mensaje,
            level=Qgis.MessageLevel.Success,
            duration=5
        )

    def apply_style_to_layer(self, layer):
        """Aplica estilo de visualización a la capa de vértices"""
        if not layer:
            return
            
        # Configurar el símbolo para los puntos
        symbol = QgsMarkerSymbol.createSimple({
            'name': 'circle',
            'color': '255,0,0,255',  # Rojo
            'size': '2.5',
            'outline_color': '0,0,0,255',  # Borde negro
            'outline_width': '0.4'
        })
        
        # Aplicar el símbolo a la capa
        renderer = QgsSingleSymbolRenderer(symbol)
        layer.setRenderer(renderer)
        
        # Configurar etiquetas básicas para el número de vértice
        try:
            # Habilitar etiquetas simples con el campo Vertice
            layer.setLabelsEnabled(True)
            layer.setCustomProperty("labeling/fieldName", "Vertice")
            layer.setCustomProperty("labeling/enabled", "true")
        except Exception as e:
            print(f"Error al configurar etiquetas: {str(e)}")
        
        # Actualizar la capa
        layer.triggerRepaint()

    def export_to_csv(self, headers, data):
        """Exporta los datos a un archivo CSV"""
        # Solicitar ubicación del archivo
        filename, _ = QFileDialog.getSaveFileName(self, "Guardar CSV",
                                                "", "Archivos CSV (*.csv)")
        if not filename:
            return
        
        # Añadir extensión .csv si no la tiene
        if not filename.lower().endswith('.csv'):
            filename += '.csv'
        
        # Escribir archivo CSV
        import csv
        with open(filename, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
            
            # Escribir encabezados
            writer.writerow(headers)
            
            # Escribir datos
            for row in data:
                writer.writerow(row)

    def get_layer_id(self, layer):
        """Obtiene el ID personalizado de una capa de vértices"""
        if not layer:
            return None
        return layer.customProperty("identificador", None)
        
    def unload(self):
        """Limpia recursos al descargar el panel"""
        self.close()