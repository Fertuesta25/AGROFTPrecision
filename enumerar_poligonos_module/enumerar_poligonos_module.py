import os
from qgis.PyQt.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                                QLabel, QComboBox, QLineEdit, QMessageBox, QDockWidget)
from qgis.PyQt.QtCore import Qt, QVariant
from qgis.PyQt.QtGui import QColor
from qgis.core import (QgsProject, QgsFeature, QgsGeometry, QgsField, QgsFields, 
                      QgsVectorLayer, QgsFeatureRequest, QgsWkbTypes, 
                      QgsPointXY, QgsVectorFileWriter, QgsCoordinateTransform, QgsCoordinateReferenceSystem)
from qgis.gui import QgsMapToolEmitPoint, QgsRubberBand

class EnumerarPoligonosPanel(QDockWidget):
    def __init__(self, iface):
        super(EnumerarPoligonosPanel, self).__init__("Enumerar Polígonos")
        self.iface = iface
        self.canvas = iface.mapCanvas()
        self.plugin_dir = os.path.dirname(os.path.dirname(__file__))
        self.poligonos_capa = None
        self.campo_enumeracion = None
        self.prefijo_enumeracion = ""
        self.linea_puntos = []
        self.maptool = None
        self.rubber_band = None
        
        # Configurar la interfaz
        self.setup_ui()
        
    def setup_ui(self):
        """Configurar la interfaz gráfica"""
        self.setMinimumWidth(300)
        main_widget = QWidget()
        main_layout = QVBoxLayout(main_widget)
        
        # Selector de capa de polígonos
        layer_layout = QHBoxLayout()
        layer_label = QLabel("Capa de polígonos:")
        self.layer_combo = QComboBox()
        layer_layout.addWidget(layer_label)
        layer_layout.addWidget(self.layer_combo)
        main_layout.addLayout(layer_layout)
        
        # Campo para la enumeración
        field_layout = QHBoxLayout()
        field_label = QLabel("Campo para enumerar:")
        self.field_combo = QComboBox()
        field_layout.addWidget(field_label)
        field_layout.addWidget(self.field_combo)
        main_layout.addLayout(field_layout)
        
        # Prefijo para la enumeración
        prefix_layout = QHBoxLayout()
        prefix_label = QLabel("Prefijo (opcional):")
        self.prefix_edit = QLineEdit()
        prefix_layout.addWidget(prefix_label)
        prefix_layout.addWidget(self.prefix_edit)
        main_layout.addLayout(prefix_layout)
        
        # Botones de acción
        buttons_layout = QHBoxLayout()
        
        self.dibujar_btn = QPushButton("Dibujar línea de dirección")
        self.dibujar_btn.clicked.connect(self.iniciar_dibujo)
        buttons_layout.addWidget(self.dibujar_btn)
        
        self.enumerar_btn = QPushButton("Enumerar polígonos")
        self.enumerar_btn.clicked.connect(self.enumerar_poligonos)
        self.enumerar_btn.setEnabled(False)
        buttons_layout.addWidget(self.enumerar_btn)
        
        main_layout.addLayout(buttons_layout)
        
        # Botón para limpiar
        self.limpiar_btn = QPushButton("Limpiar")
        self.limpiar_btn.clicked.connect(self.limpiar_dibujo)
        main_layout.addWidget(self.limpiar_btn)
        
        # Información
        info_label = QLabel("Dibuje una línea en el mapa para definir la dirección\n"
                          "de enumeración de los polígonos.")
        info_label.setStyleSheet("color: gray; font-style: italic;")
        main_layout.addWidget(info_label)
        
        main_layout.addStretch()
        self.setWidget(main_widget)
        
        # Actualizar capas
        self.actualizar_capas()
        
    def actualizar_capas(self):
        """Actualiza el combo box con las capas de polígonos disponibles"""
        self.layer_combo.clear()
        for layer in QgsProject.instance().mapLayers().values():
            if layer.type() == 0:  # Capa vectorial
                if layer.geometryType() == QgsWkbTypes.PolygonGeometry:
                    self.layer_combo.addItem(layer.name(), layer.id())
        
        self.layer_combo.currentIndexChanged.connect(self.actualizar_campos)
        if self.layer_combo.count() > 0:
            self.actualizar_campos()
    
    def actualizar_campos(self):
        """Actualiza el combo box con los campos de la capa seleccionada"""
        self.field_combo.clear()
        if self.layer_combo.count() == 0:
            return
        
        layer_id = self.layer_combo.currentData()
        layer = QgsProject.instance().mapLayer(layer_id)
        
        if layer:
            # Verificar campos existentes
            for field in layer.fields():
                self.field_combo.addItem(field.name(), field.name())
            
            # Opción para crear un nuevo campo
            self.field_combo.addItem("Crear nuevo campo...", "NUEVO_CAMPO")
    
    def iniciar_dibujo(self):
        """Inicia la herramienta de dibujo para la línea de dirección"""
        self.limpiar_dibujo()
        
        # Crear herramienta de mapa para capturar puntos
        self.maptool = QgsMapToolEmitPoint(self.canvas)
        self.maptool.canvasClicked.connect(self.agregar_punto)
        self.canvas.setMapTool(self.maptool)
        
        # Crear banda de goma para mostrar la línea
        self.rubber_band = QgsRubberBand(self.canvas, QgsWkbTypes.LineGeometry)
        self.rubber_band.setColor(QColor(255, 0, 0, 180))
        self.rubber_band.setWidth(2)
        
        # Mensaje para el usuario
        self.iface.messageBar().pushMessage(
            "Enumerar Polígonos", 
            "Haga clic para agregar puntos a la polilínea. Clic derecho para finalizar.",
            level=1, # Info
            duration=5
        )
        
        # Activar botón de dibujo
        self.dibujar_btn.setEnabled(False)
    
    def agregar_punto(self, point, button):
        """Añade un punto a la línea de dirección"""
        if button == Qt.LeftButton:
            # Agregar punto izquierdo a la línea
            punto = QgsPointXY(point)
            self.linea_puntos.append(punto)
            
            # Actualizar la banda de goma
            if len(self.linea_puntos) > 0:
                self.rubber_band.reset(QgsWkbTypes.LineGeometry)
                for p in self.linea_puntos:
                    self.rubber_band.addPoint(p)
            
            # Habilitar el botón de enumerar si tenemos al menos 2 puntos
            if len(self.linea_puntos) >= 2:
                self.enumerar_btn.setEnabled(True)
                
        elif button == Qt.RightButton and len(self.linea_puntos) >= 2:
            # Finalizar la línea con clic derecho
            self.canvas.unsetMapTool(self.maptool)
            self.dibujar_btn.setEnabled(True)
            
            # Confirmar al usuario
            self.iface.messageBar().pushMessage(
                "Enumerar Polígonos", 
                f"Polilínea completada con {len(self.linea_puntos)} puntos. Haga clic en 'Enumerar polígonos' para continuar.",
                level=1, # Info
                duration=3
            )
    
    def limpiar_dibujo(self):
        """Limpia el dibujo actual"""
        if self.rubber_band:
            self.rubber_band.reset(QgsWkbTypes.LineGeometry)  # Usar QgsWkbTypes.LineGeometry
        
        self.linea_puntos = []
        self.enumerar_btn.setEnabled(False)
        self.dibujar_btn.setEnabled(True)
    
    def enumerar_poligonos(self):
        """Enumera los polígonos según la dirección de la polilínea"""
        if len(self.linea_puntos) < 2:
            QMessageBox.warning(None, "Advertencia", "Dibuje una polilínea primero para definir la dirección.")
            return
        
        # Obtener la capa seleccionada
        if self.layer_combo.count() == 0:
            QMessageBox.warning(None, "Advertencia", "No hay capas de polígonos disponibles.")
            return
        
        layer_id = self.layer_combo.currentData()
        layer = QgsProject.instance().mapLayer(layer_id)
        
        if not layer:
            QMessageBox.warning(None, "Advertencia", "No se pudo acceder a la capa seleccionada.")
            return
        
        # Verificar campo seleccionado o crear uno nuevo
        field_name = self.field_combo.currentData()
        if field_name == "NUEVO_CAMPO":
            # Crear un nuevo campo para la enumeración
            field_name = "Enum_ID"
            
            # Verificar si el campo ya existe
            index = layer.fields().indexFromName(field_name)
            if index == -1:  # El campo no existe
                layer.startEditing()
                layer.addAttribute(QgsField(field_name, QVariant.String))
                layer.commitChanges()
            
        # Obtener polilínea de dirección
        linea = QgsGeometry.fromPolylineXY(self.linea_puntos)
        
        # Obtener polígonos que intersectan con la polilínea
        poligonos_intersectados = []
        poligonos_ignorados = 0
        
        # Definir una tolerancia para la intersección (en unidades de mapa)
        tolerancia = 0.1  # Ajustar según sea necesario
        
        for feature in layer.getFeatures():
            geom = feature.geometry()
            if geom:
                # Comprobar si hay intersección directa
                if linea.crosses(geom) or linea.contains(geom) or geom.contains(linea):
                    centroide = geom.centroid().asPoint()
                    poligonos_intersectados.append((centroide, feature.id()))
                else:
                    # Si no hay intersección directa, comprobar si la línea está cerca del polígono
                    buffer_linea = linea.buffer(tolerancia, 5)  # 5 segmentos para aproximar el buffer circular
                    if buffer_linea.intersects(geom):
                        centroide = geom.centroid().asPoint()
                        poligonos_intersectados.append((centroide, feature.id()))
                    else:
                        poligonos_ignorados += 1
        
        # Si no hay polígonos intersectados, mostrar mensaje y salir
        if not poligonos_intersectados:
            QMessageBox.warning(None, "Advertencia", 
                             "La polilínea no intersecta con ningún polígono. Dibuje otra línea que pase por los polígonos.")
            return
        
        # Ordenar centroides según el punto más cercano a lo largo de la polilínea
        def distancia_a_lo_largo_de_linea(centroide):
            # Calcular distancia a lo largo de la polilínea
            punto_centroide = QgsGeometry.fromPointXY(centroide[0])
            
            # Encontrar el punto más cercano sobre la línea
            distancia_a_lo_largo = linea.lineLocatePoint(punto_centroide)
            
            return distancia_a_lo_largo
        
        centroides_ordenados = sorted(poligonos_intersectados, key=distancia_a_lo_largo_de_linea)
        
        # Enumerar los polígonos
        prefijo = self.prefix_edit.text()
        
        layer.startEditing()
        
        # Crear una capa temporal para visualizar el orden si es necesario
        mostrar_orden = False  # Cambiado a False para producción
        if mostrar_orden:
            # Crear capa temporal para visualizar el orden
            memoria_capa = QgsVectorLayer("LineString?crs=" + layer.crs().authid(), "Orden_Enumeración", "memory")
            memoria_proveedor = memoria_capa.dataProvider()
            memoria_capa.startEditing()
            
            # Generar líneas de centroides a los puntos de la línea
            for i, (centroide, _) in enumerate(centroides_ordenados):
                # Encontrar punto más cercano en la línea
                punto_centroide = QgsGeometry.fromPointXY(centroide)
                punto_cercano = linea.nearestPoint(punto_centroide).asPoint()
                
                # Crear línea de centroide a punto cercano
                linea_temp = QgsGeometry.fromPolylineXY([centroide, punto_cercano])
                
                # Agregar a capa temporal
                feat = QgsFeature()
                feat.setGeometry(linea_temp)
                memoria_proveedor.addFeature(feat)
                
            memoria_capa.commitChanges()
            QgsProject.instance().addMapLayer(memoria_capa)
        
        # Actualizar SOLO los valores de los polígonos intersectados
        for i, (_, feature_id) in enumerate(centroides_ordenados):
            # Enumeración empezando desde 1
            valor = f"{prefijo}{i+1}"
            
            # Actualizar el campo de enumeración
            layer.changeAttributeValue(feature_id, layer.fields().indexFromName(field_name), valor)
        
        layer.commitChanges()
        
        # Informar al usuario
        QMessageBox.information(None, "Información", 
                            f"Se han enumerado {len(centroides_ordenados)} polígonos que intersectan con la polilínea dibujada. "
                            f"Se preservó la numeración de {poligonos_ignorados} polígonos no intersectados.")
        
        # Limpiar dibujo después de enumerar
        self.limpiar_dibujo()
    
    def show_and_activate(self):
        """Muestra y activa el panel"""
        self.show()
        self.activateWindow()
        self.raise_()
        self.actualizar_capas()  # Refrescar las capas disponibles

    def closeEvent(self, event):
        """Maneja el evento de cierre del panel"""
        if self.rubber_band:
            self.rubber_band.reset(QgsWkbTypes.LineGeometry)  # Usar QgsWkbTypes.LineGeometry
        if self.maptool:
            self.canvas.unsetMapTool(self.maptool)
        event.accept()

def get_module_instance(iface):
    """Función para obtener una instancia del módulo"""
    return EnumerarPoligonosModule(iface)

class EnumerarPoligonosModule:
    def __init__(self, iface):
        self.iface = iface
        self.panel = None
    
    def toggle_panel(self):
        """Alterna la visibilidad del panel"""
        if not self.panel:
            self.panel = EnumerarPoligonosPanel(self.iface)
            self.iface.addDockWidget(Qt.RightDockWidgetArea, self.panel)
        else:
            if self.panel.isVisible():
                self.panel.hide()
            else:
                self.panel.show_and_activate()
    
    def unload(self):
        """Libera recursos del módulo"""
        if self.panel:
            self.panel.close()
            self.panel.deleteLater()
            self.panel = None