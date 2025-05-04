# Archivo: ui/panel_redriego.py
from qgis.PyQt.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QLabel, QComboBox, QLineEdit,
    QCheckBox, QGridLayout, QSizePolicy, QDialog, QToolTip, QDockWidget, QSlider, QHBoxLayout, QToolButton, QSpacerItem,
    QGroupBox, QTextEdit  # Añade estas dos clases
)
from qgis.PyQt.QtGui import QColor, QPainter, QFontMetrics, QRegExpValidator, QIntValidator
from qgis.PyQt.QtCore import (
    Qt, pyqtSignal, QPoint, QRect, QRegExp
)
from qgis.gui import (
    QgsProjectionSelectionWidget, 
    QgsMapToolEmitPoint, 
    QgsRubberBand,
    QgsVertexMarker,
    QgsMapCanvasSnappingUtils,
    QgsSnapIndicator
)
from qgis.core import (
    QgsProject,
    QgsVectorLayer,
    QgsField,
    QgsFeature,
    QgsGeometry,
    QgsWkbTypes,
    QgsCoordinateReferenceSystem,
    QgsPoint,
    QgsPointXY,
    QgsDistanceArea,
    QgsCoordinateTransform,
    QgsSnappingConfig,
    Qgis,
    QgsFeatureRequest  # Añade esta clase
)

from qgis.utils import iface
from PyQt5.QtCore import QVariant
import os
import math
from collections import defaultdict  # Para agrupar las tuberías por diámetro

# Widget personalizado para entrada flotante de longitud directamente en el canvas
class FloatingLengthInput(QWidget):
    """Widget flotante personalizado para mostrar e introducir longitudes"""
    valueChanged = pyqtSignal(float)
    
    def __init__(self, canvas, initial_value=0.0):
        super().__init__(canvas)  # Pasamos el canvas como padre para asegurar visibilidad correcta
        
        # Configuración básica del widget
        self.setFixedSize(120, 30)
        
        # Crear campo de texto
        self.edit = QLineEdit(self)
        self.edit.setGeometry(0, 0, 120, 30)
        self.edit.setAlignment(Qt.AlignCenter)
        self.edit.setValidator(QRegExpValidator(QRegExp("\\d+(\\.\\d+)?")))
        self.edit.setText(str(initial_value))
        self.edit.returnPressed.connect(self.on_value_entered)
        
        # Estilo para hacer el campo más limpio
        self.edit.setStyleSheet("""
            QLineEdit {
                background-color: rgba(255, 255, 255, 220);
                border: 1px solid rgba(100, 100, 100, 150);
                border-radius: 5px;
                padding: 2px;
                font-weight: bold;
                color: black;
                font-size: 12pt;
            }
        """)
        
        # Asegurarnos de que el widget sea visible por encima de otros elementos
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFocusPolicy(Qt.NoFocus)  # No queremos que el widget principal tome el foco
        
    def update_value(self, value):
        """Actualiza el valor mostrado sin emitir señal"""
        if not self.edit.hasFocus():
            self.edit.setText(f"{value:.2f}")
    
    def on_value_entered(self):
        """Emite la señal cuando se introduce un nuevo valor"""
        try:
            value = float(self.edit.text())
            self.valueChanged.emit(value)
        except ValueError:
            pass
            
    def position_at(self, pos):
        """Posiciona el widget exactamente donde se necesita"""
        global_pos = self.parent().mapToGlobal(pos)
        # Posicionamos el widget al lado del cursor
        self.move(global_pos.x() + 15, global_pos.y() - 15)

# Definición de la herramienta de dibujo integrada directamente en este archivo
class LineDrawingTool(QgsMapToolEmitPoint):
    """Herramienta personalizada para dibujar líneas con longitud específica"""
    lineCaptured = pyqtSignal(object, float)  # Geometría, longitud
    
    def __init__(self, canvas, initial_length, layer_crs):
        super().__init__(canvas)
        self.canvas = canvas
        self.target_length = initial_length
        self.layer_crs = layer_crs
        self.project_crs = canvas.mapSettings().destinationCrs()
        
        # Añadir esta línea para controlar la entrada numérica directa
        self.is_numeric_input_started = False

        # Añadir esta línea para guardar el último punto dibujado
        self.last_end_point = None  # El último punto final dibujado
        self.continuous_mode = True  # Modo continuo activado por defecto

        # Almacenar la última posición del ratón
        self.last_mouse_pos = None
        
        # Configurar la herramienta flotante de entrada
        self.floating_input = None
        
        # Configurar snapping
        self.snapping_utils = QgsMapCanvasSnappingUtils(canvas)
        self.snapping_utils.setConfig(QgsProject.instance().snappingConfig())
        self.snap_indicator = QgsSnapIndicator(canvas)
        
        # Configurar el transformador de coordenadas si es necesario
        self.need_transform = (self.layer_crs.srsid() != self.project_crs.srsid())
        if self.need_transform:
            self.transform = QgsCoordinateTransform(
                self.project_crs, 
                self.layer_crs, 
                QgsProject.instance()
            )
        
        # Configurar las bandas de goma (rubber bands) para visualización
        self.rubber_band = QgsRubberBand(canvas, QgsWkbTypes.LineGeometry)
        self.rubber_band.setColor(QColor(0, 0, 255, 100))
        self.rubber_band.setWidth(2)
        
        self.temp_rubber_band = QgsRubberBand(canvas, QgsWkbTypes.LineGeometry)
        self.temp_rubber_band.setColor(QColor(255, 0, 0, 100))
        self.temp_rubber_band.setWidth(2)
        
        # Configurar el marcador de vértice
        self.vertex_marker = QgsVertexMarker(canvas)
        self.vertex_marker.setColor(QColor(255, 0, 0))
        self.vertex_marker.setPenWidth(2)
        self.vertex_marker.setIconSize(5)
        self.vertex_marker.setIconType(QgsVertexMarker.ICON_CIRCLE)
        self.vertex_marker.hide()
        
        # Configurar objeto para calcular distancias
        self.distance_area = QgsDistanceArea()
        self.distance_area.setSourceCrs(self.layer_crs, QgsProject.instance().transformContext())
        self.distance_area.setEllipsoid(QgsProject.instance().ellipsoid())
        
        # Lista para almacenar puntos capturados
        self.points = []
        # Longitud actual para mostrar
        self.current_length = 0.0
        
    def toLayerCoordinates(self, point):
        """Convierte las coordenadas del mapa al SRC de la capa"""
        if self.need_transform:
            try:
                return self.transform.transform(point)
            except Exception as e:
                # Si hay error de transformación, usar coordenadas originales
                return point
        else:
            return point
        
    def reset(self):
        """Reinicia la herramienta de dibujo conservando el último punto en modo continuo"""
        # Guardar una referencia al último punto antes de resetear
        last_point = self.last_end_point
        
        # Limpiar todo
        self.points = []
        self.rubber_band.reset(QgsWkbTypes.LineGeometry)
        self.temp_rubber_band.reset(QgsWkbTypes.LineGeometry)
        self.vertex_marker.hide()
        self.snap_indicator.setVisible(False)
        
        # Reiniciar el estado de entrada numérica para la siguiente línea
        self.is_numeric_input_started = False
        
        # Ocultar y eliminar el widget flotante si existe
        if self.floating_input:
            self.floating_input.hide()
            self.floating_input.deleteLater()
            self.floating_input = None
        
        # Si estamos en modo continuo y tenemos un punto final válido,
        # establecerlo como primer punto para la siguiente línea
        if self.continuous_mode and last_point:
            # Añadir el último punto como primer punto de la nueva línea
            self.points.append(last_point)
            
            # Mostrar marcador en ese punto
            map_point = self.toMapCoordinates(last_point) if self.need_transform else last_point
            self.vertex_marker.setCenter(map_point)
            self.vertex_marker.show()
            
            # Configurar el rubber band para mostrar el punto
            self.rubber_band.reset(QgsWkbTypes.LineGeometry)
            self.rubber_band.addPoint(map_point)
            
            # Crear widget flotante para la longitud
            self.floating_input = FloatingLengthInput(self.canvas, self.target_length)
            self.floating_input.valueChanged.connect(self.update_length)
            
            # Convertir coordenadas de mapa a coordenadas de pantalla de manera correcta
            pixel_point = self.canvas.mapSettings().mapToPixel().transform(map_point)
            screen_point = QPoint(int(pixel_point.x()), int(pixel_point.y()))
            
            # Posicionar el widget flotante
            self.floating_input.position_at(screen_point)
            self.floating_input.show()
            
    def emit_geometry(self, geometry):
        """Emite la señal con la geometría capturada y guarda el último punto"""
        # Calculamos la longitud real de la geometría
        real_length = self.distance_area.measureLength(geometry)
        
        # Guardar el último punto (punto final de la línea)
        # Asumimos que la geometría es una línea con dos puntos
        if geometry.type() == QgsWkbTypes.LineGeometry:
            line = geometry.asPolyline()
            if len(line) >= 2:
                self.last_end_point = line[-1]  # Guardar el último punto en coordenadas de la capa
        
        # Emitir la señal
        self.lineCaptured.emit(geometry, real_length)

    def canvasPressEvent(self, event):
        """Maneja los eventos de clic en el canvas"""
        # Guardar la posición del evento para referencia
        self.last_mouse_pos = event
        
        # Intentar hacer snap al punto
        snapping_result = self.snapping_utils.snapToMap(event.pos())
        
        # Obtener el punto (con o sin snap)
        if snapping_result.isValid():
            map_point = snapping_result.point()
        else:
            map_point = self.toMapCoordinates(event.pos())
            
        layer_point = self.toLayerCoordinates(map_point)
        
        if event.button() == Qt.LeftButton:
            # Ocultar indicador de snap
            self.snap_indicator.setVisible(False)
            
            # Si existe un widget flotante, tomar su valor y luego cerrarlo
            if self.floating_input and len(self.points) == 1:
                try:
                    self.target_length = float(self.floating_input.edit.text())
                except ValueError:
                    pass
                self.floating_input.hide()
                self.floating_input.deleteLater()
                self.floating_input = None
            
            # Añadir el punto actual a la lista (en coordenadas de la capa)
            self.points.append(layer_point)
            
            # Mostrar marcador en el punto (en coordenadas del mapa)
            self.vertex_marker.setCenter(map_point)
            self.vertex_marker.show()
            
            # Si tenemos un solo punto, solo lo mostramos
            if len(self.points) == 1:
                self.rubber_band.reset(QgsWkbTypes.LineGeometry)
                self.rubber_band.addPoint(map_point)
                
                # Resetear el estado de entrada numérica para el nuevo punto
                self.is_numeric_input_started = False
                
                # Crear widget flotante para mostrar/modificar la longitud
                if self.floating_input:
                    self.floating_input.deleteLater()
                    
                self.floating_input = FloatingLengthInput(self.canvas, self.target_length)
                self.floating_input.valueChanged.connect(self.update_length)
                self.floating_input.position_at(event.pos())
                self.floating_input.show()
            
            # Si tenemos al menos dos puntos, dibujamos la línea
            elif len(self.points) >= 2:
                start_point = self.points[-2]  # Punto de inicio (en coords de la capa)
                direction_point = self.points[-1]  # Punto de dirección (en coords de la capa)
                
                # Calculamos la dirección normalizada
                dx = direction_point.x() - start_point.x()
                dy = direction_point.y() - start_point.y()
                current_length = math.sqrt(dx*dx + dy*dy)
                
                if current_length > 0:  # Evitar división por cero
                    # Normalizamos el vector dirección
                    dx /= current_length
                    dy /= current_length
                    
                    # Si estamos usando un CRS geográfico, ajustamos para distancias
                    if self.layer_crs.isGeographic():
                        # Para CRS geográfico, usamos el objeto QgsDistanceArea
                        # Creamos una línea temporal con la longitud estimada
                        temp_end_x = start_point.x() + dx * 0.001 * self.target_length  # Estimación inicial
                        temp_end_y = start_point.y() + dy * 0.001 * self.target_length
                        temp_end = QgsPointXY(temp_end_x, temp_end_y)
                        
                        # Calculamos la distancia real
                        line_geom = QgsGeometry.fromPolylineXY([start_point, temp_end])
                        actual_length = self.distance_area.measureLength(line_geom)
                        
                        # Ajustamos el factor de escala
                        scale_factor = self.target_length / actual_length if actual_length > 0 else 1
                        
                        # Calculamos el punto final correcto
                        end_x = start_point.x() + dx * 0.001 * self.target_length * scale_factor
                        end_y = start_point.y() + dy * 0.001 * self.target_length * scale_factor
                    else:
                        # Para CRS proyectado, podemos usar directamente los metros
                        end_x = start_point.x() + dx * self.target_length
                        end_y = start_point.y() + dy * self.target_length
                    
                    end_point = QgsPointXY(end_x, end_y)
                    
                    # Creamos la geometría de la línea
                    line_points = [start_point, end_point]
                    geometry = QgsGeometry.fromPolylineXY(line_points)
                    
                    # Emitimos la señal con la geometría creada
                    self.emit_geometry(geometry)
                    
                    # Reiniciamos para la siguiente línea
                    self.reset()
        
    def canvasMoveEvent(self, event):
        """Maneja el movimiento del ratón para mostrar una vista previa de la línea"""
        # Guardar la posición actual del ratón
        self.last_mouse_pos = event
        
        # Intentar hacer snap al punto y mostrar indicador
        snapping_result = self.snapping_utils.snapToMap(event.pos())
        if snapping_result.isValid():
            self.snap_indicator.setVisible(True)
            self.snap_indicator.setMatch(snapping_result)
            map_point = snapping_result.point()
        else:
            self.snap_indicator.setVisible(False)
            map_point = self.toMapCoordinates(event.pos())
            
        layer_point = self.toLayerCoordinates(map_point)
        
        if len(self.points) > 0:
            # Mostrar una línea temporal desde el último punto fijo hasta la posición actual del ratón
            self.temp_rubber_band.reset(QgsWkbTypes.LineGeometry)
            last_map_point = self.toMapCoordinates(self.points[-1]) if self.need_transform else self.points[-1]
            self.temp_rubber_band.addPoint(last_map_point)
            self.temp_rubber_band.addPoint(map_point)
            
            # Si tenemos un punto, calculamos y mostramos una vista previa de la línea con longitud específica
            if len(self.points) == 1:
                start_point = self.points[0]  # En coordenadas de la capa
                
                # Calculamos dirección y distancia actual
                dx = layer_point.x() - start_point.x()
                dy = layer_point.y() - start_point.y()
                current_length = math.sqrt(dx*dx + dy*dy)
                
                # Si la capa está en un CRS geográfico, calculamos la distancia correctamente
                if self.layer_crs.isGeographic():
                    # Usamos QgsDistanceArea para medir distancias geográficas
                    line_geom = QgsGeometry.fromPolylineXY([start_point, layer_point])
                    current_length = self.distance_area.measureLength(line_geom)
                
                # Actualizar el valor en el widget flotante
                if self.floating_input and len(self.points) == 1:
                    self.floating_input.position_at(event.pos())
                    self.floating_input.update_value(current_length)
                
                if current_length > 0:  # Evitar división por cero
                    # Normalizamos vector dirección
                    dx /= current_length
                    dy /= current_length
                    
                    # Si estamos usando un CRS geográfico, ajustamos para distancias
                    if self.layer_crs.isGeographic():
                        # Estimación para CRS geográfico
                        end_x = start_point.x() + dx * 0.001 * self.target_length
                        end_y = start_point.y() + dy * 0.001 * self.target_length
                    else:
                        # Para CRS proyectado
                        end_x = start_point.x() + dx * self.target_length
                        end_y = start_point.y() + dy * self.target_length
                    
                    end_point = QgsPointXY(end_x, end_y)
                    
                    # Mostrar línea con longitud exacta (convertir a coordenadas del mapa para visualización)
                    self.rubber_band.reset(QgsWkbTypes.LineGeometry)
                    
                    # Convertir puntos al CRS del proyecto para visualización si es necesario
                    map_start = self.toMapCoordinates(start_point) if self.need_transform else start_point
                    map_end = self.toMapCoordinates(end_point) if self.need_transform else end_point
                    
                    self.rubber_band.addPoint(map_start)
                    self.rubber_band.addPoint(map_end)
    
    def update_length(self, value):
        """Actualiza el valor de la longitud objetivo"""
        self.target_length = value
        # Forzar actualización de la vista previa
        self.canvas.refreshAllLayers()
        
    def keyPressEvent(self, event):
        """Maneja eventos de teclado para permitir entrada directa de números"""
        # Primero, comprobamos si estamos en modo de dibujo (primer punto colocado)
        if len(self.points) == 1:
            # Tecla Escape para cancelar la línea actual o desactivar el modo continuo
            if event.key() == Qt.Key_Escape:
                if len(self.points) > 0:
                    # Si hay puntos, limpiar todo y desactivar modo continuo temporalmente
                    self.continuous_mode = False
                    self.last_end_point = None
                    self.reset()
                    # Reactivar el modo continuo para la próxima línea
                    self.continuous_mode = True
                else:
                    # Si no hay puntos activos, simplemente resetear
                    self.reset()
                event.accept()
                return
                
            # Tecla Enter/Return para confirmar
            elif event.key() == Qt.Key_Return or event.key() == Qt.Key_Enter:
                # Obtener la longitud desde el widget flotante
                if self.floating_input:
                    try:
                        self.target_length = float(self.floating_input.edit.text())
                    except ValueError:
                        pass
                    
                # Obtener la posición actual del cursor del mouse
                cursor_pos = self.canvas.mouseLastXY()
                
                # Si tenemos una longitud válida, crear la línea en dirección al cursor
                if self.target_length > 0:
                    # Convertir posición del cursor a coordenadas del mapa
                    mouse_point = self.canvas.getCoordinateTransform().toMapCoordinates(cursor_pos.x(), cursor_pos.y())
                    
                    # Intentar snap si está habilitado
                    snapping_result = self.snapping_utils.snapToMap(QPoint(cursor_pos.x(), cursor_pos.y()))
                    if snapping_result.isValid():
                        mouse_point = snapping_result.point()
                    
                    # Convertir a coordenadas de la capa
                    layer_mouse_point = self.toLayerCoordinates(mouse_point)
                    start_point = self.points[0]  # Punto inicial
                    
                    # Calcular la dirección
                    dx = layer_mouse_point.x() - start_point.x()
                    dy = layer_mouse_point.y() - start_point.y()
                    current_length = math.sqrt(dx*dx + dy*dy)
                    
                    if current_length > 0:  # Evitar división por cero
                        # Normalizar vector dirección
                        dx /= current_length
                        dy /= current_length
                        
                        # Calcular punto final según la longitud especificada
                        if self.layer_crs.isGeographic():
                            # Para CRS geográfico
                            temp_end_x = start_point.x() + dx * 0.001 * self.target_length
                            temp_end_y = start_point.y() + dy * 0.001 * self.target_length
                            temp_end = QgsPointXY(temp_end_x, temp_end_y)
                            
                            # Ajustar para longitud exacta
                            line_geom = QgsGeometry.fromPolylineXY([start_point, temp_end])
                            actual_length = self.distance_area.measureLength(line_geom)
                            scale_factor = self.target_length / actual_length if actual_length > 0 else 1
                            
                            end_x = start_point.x() + dx * 0.001 * self.target_length * scale_factor
                            end_y = start_point.y() + dy * 0.001 * self.target_length * scale_factor
                        else:
                            # Para CRS proyectado
                            end_x = start_point.x() + dx * self.target_length
                            end_y = start_point.y() + dy * self.target_length
                            
                        end_point = QgsPointXY(end_x, end_y)
                        
                        # Crear geometría y emitir señal
                        line_points = [start_point, end_point]
                        geometry = QgsGeometry.fromPolylineXY(line_points)
                        self.emit_geometry(geometry)
                        
                        # Reiniciar para la siguiente línea
                        self.reset()
                
                event.accept()
                return
                
            # Dígitos (0-9) y punto decimal
            elif (event.key() >= Qt.Key_0 and event.key() <= Qt.Key_9) or event.key() == Qt.Key_Period:
                # Asegurarse de que tenemos un widget flotante
                if self.floating_input:
                    # Obtener el carácter tecleado
                    key_text = event.text()
                    
                    # Si es el primer carácter numérico después de colocar un punto o
                    # si la caja muestra un valor dinámico (no ha sido editado manualmente aún),
                    # limpiar el contenido actual
                    if not self.is_numeric_input_started:
                        self.floating_input.edit.clear()
                        self.is_numeric_input_started = True
                    
                    # Añadir el dígito al texto actual
                    current_text = self.floating_input.edit.text()
                    new_text = current_text + key_text
                    
                    # Intentar convertir a número para validar
                    try:
                        value = float(new_text)
                        # Actualizar texto y longitud objetivo
                        self.floating_input.edit.setText(new_text)
                        self.target_length = value
                        # Forzar actualización visual
                        self.canvas.refresh()
                    except ValueError:
                        # No es un número válido, ignorar
                        pass
                    
                    event.accept()
                    return
            
            # Tecla de retroceso
            elif event.key() == Qt.Key_Backspace:
                if self.floating_input and hasattr(self, 'is_numeric_input_started') and self.is_numeric_input_started:
                    current_text = self.floating_input.edit.text()
                    if current_text:
                        # Eliminar el último carácter
                        new_text = current_text[:-1]
                        if new_text:
                            # Si queda texto, actualizar valor
                            try:
                                value = float(new_text)
                                self.floating_input.edit.setText(new_text)
                                self.target_length = value
                            except ValueError:
                                # No es número válido, dejar como está
                                pass
                        else:
                            # Si se borró todo, poner 0
                            self.floating_input.edit.setText("0")
                            self.target_length = 0.0
                        
                        # Actualizar visualización
                        self.canvas.refresh()
                    
                    event.accept()
                    return
        
        # Para cualquier otro evento, dejar que el sistema lo maneje
        event.ignore()
class PanelRedRiego(QDockWidget):
    def __init__(self, iface):
        super().__init__("Red de Riego")  # Título del panel
        self.iface = iface
        self.canvas = self.iface.mapCanvas()
        self.drawing_tool = None
        self.initial_length = 100.0  # Longitud inicial para dibujo
        
        # Crear un widget contenedor para el contenido
        self.content_widget = QWidget()
        self.setWidget(self.content_widget)

        # Inicializar la interfaz en el widget contenedor
        self.init_ui()

        # Actualizar el resumen al inicio
        self.actualizar_resumen()

    def init_ui(self):
        # Usar GridLayout para mejor organización y comportamiento al redimensionar
        layout = QGridLayout(self.content_widget)  # Aplicar layout al widget contenedor
        
        # Añadir barra de herramientas en la parte superior con botones de selección
        toolbar_layout = QHBoxLayout()
        toolbar_layout.setContentsMargins(0, 0, 0, 0)
        toolbar_layout.setSpacing(2)
        
        # Crear contenedor para botones de selección
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
        
        # Botones para seleccionar todos y deseleccionar
        self.btn_select_all = QToolButton()
        self.btn_select_all.setText("✓")
        self.btn_select_all.setToolTip("Seleccionar todos los objetos espaciales")
        self.btn_select_all.clicked.connect(self.seleccionar_todos)
        
        self.btn_deselect_all = QToolButton()
        self.btn_deselect_all.setText("✗")
        self.btn_deselect_all.setToolTip("Deseleccionar todos los objetos espaciales")
        self.btn_deselect_all.clicked.connect(self.deseleccionar_todos)
        
        # Añadir botones al layout de selección
        selection_layout.addWidget(self.btn_select)
        selection_layout.addWidget(self.btn_select_polygon)
        selection_layout.addWidget(self.btn_select_freehand)
        selection_layout.addWidget(self.btn_select_radius)
        selection_layout.addWidget(self.btn_select_all)
        selection_layout.addWidget(self.btn_deselect_all)
        
        # Añadir botón de identificar objetos espaciales
        self.btn_identificar = QToolButton()
        self.btn_identificar.setIcon(iface.actionIdentify().icon())
        self.btn_identificar.setToolTip("Identificar objetos espaciales")
        self.btn_identificar.clicked.connect(self.activar_identificar)

        # Añadir botón "Dibujar red" con el icono de añadir línea
        self.btn_dibujar_red = QToolButton()
        self.btn_dibujar_red.setIcon(iface.actionAddFeature().icon())
        self.btn_dibujar_red.setToolTip("Dibujar red")
        self.btn_dibujar_red.clicked.connect(self.dibujar_red)
        
        # Configurar el layout principal de la barra de herramientas
        toolbar_layout.addLayout(selection_layout)  # Botones de selección a la izquierda
        toolbar_layout.addStretch()                 # Espacio en medio
        toolbar_layout.addWidget(self.btn_identificar)  # Botón de identificar
        toolbar_layout.addWidget(self.btn_dibujar_red)  # Botón de dibujar red a la derecha
        
        # Añadir la barra de herramientas al layout principal (row 0)
        layout.addLayout(toolbar_layout, 0, 0)
        
        # Incrementamos row para que los siguientes elementos vayan después de la barra
        row = 1
            
        # Tipo de tubería
        layout.addWidget(QLabel("Tipo de tubería:"), row, 0)
        row += 1
        self.tipo_combo = QComboBox()
        self.tipo_combo.addItems(["Matriz", "Terciarias", "Laterales"])
        self.tipo_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layout.addWidget(self.tipo_combo, row, 0)
        row += 1
        
        layout.addWidget(QLabel("Diámetro nominal (mm):"), row, 0)
        row += 1
        self.diam_combo = QComboBox()
        self.diam_combo.addItems(["16", "17", "20", "25", "32", "40", "50", "63", "75", "90", "110", "125", "140", "160", "200", "250", "280", "315"])
        self.diam_combo.setCurrentText("50")  # Valor por defecto
        self.diam_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layout.addWidget(self.diam_combo, row, 0)
        row += 1

        # Material
        layout.addWidget(QLabel("Material:"), row, 0)
        row += 1
        self.material_combo = QComboBox()
        self.material_combo.addItems(["PE", "PVC"])
        self.material_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layout.addWidget(self.material_combo, row, 0)
        row += 1

        # Sector
        layout.addWidget(QLabel("Sector (1-20):"), row, 0)
        row += 1
        self.sector_input = QLineEdit("1")
        self.sector_input.setValidator(QIntValidator(1, 20))
        self.sector_input.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layout.addWidget(self.sector_input, row, 0)
        row += 1

        # Tipo de riego
        layout.addWidget(QLabel("Tipo de riego:"), row, 0)
        row += 1
        self.tipo_riego_combo = QComboBox()
        self.tipo_riego_combo.addItems(["Aspersion", "Goteo", "Cintas", "Subterraneo"])
        self.tipo_riego_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layout.addWidget(self.tipo_riego_combo, row, 0)
        row += 1
        
        # Checkbox para operar solo en elementos seleccionados
        self.sel_check = QCheckBox("Solo elementos seleccionados")
        layout.addWidget(self.sel_check, row, 0)
        row += 1
        
        self.asignar_btn = QPushButton("Asignar atributos")
        self.asignar_btn.clicked.connect(self.asignar_atributos)
        self.asignar_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layout.addWidget(self.asignar_btn, row, 0)
        row += 1
        
        # AÑADIR NUEVO GROUPBOX PARA RESUMEN DE RED
        self.red_summary_group = QGroupBox("Análisis de Red de Riego")
        red_summary_layout = QVBoxLayout()

        # Añadir ComboBox para filtrar la capa
        filtro_layout = QHBoxLayout()
        filtro_layout.addWidget(QLabel("Filtrar:"))
        self.filtro_combo = QComboBox()
        self.filtro_combo.addItems(["Toda la red", "Matriz", "Terciarias", "Laterales"])
        self.filtro_combo.currentIndexChanged.connect(self.actualizar_resumen)
        filtro_layout.addWidget(self.filtro_combo)
        red_summary_layout.addLayout(filtro_layout)

        # Añadir área de texto para mostrar el resumen
        self.resumen_texto = QTextEdit()
        self.resumen_texto.setReadOnly(True)
        self.resumen_texto.setMinimumHeight(100)
        red_summary_layout.addWidget(QLabel("Resumen de la red:"))
        red_summary_layout.addWidget(self.resumen_texto)

        # Botón para actualizar resumen
        self.btn_actualizar_resumen = QPushButton("Actualizar resumen")
        self.btn_actualizar_resumen.clicked.connect(self.actualizar_resumen)
        red_summary_layout.addWidget(self.btn_actualizar_resumen)

        self.red_summary_group.setLayout(red_summary_layout)
        layout.addWidget(self.red_summary_group, row, 0)
        row += 1

        # Añadir un espaciador para ocupar el espacio restante
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(spacer, row, 0)

    def activar_herramienta_seleccion(self, action):
        # Usar la capa activa para la selección
        active_layer = self.iface.activeLayer()
        
        # Si no hay capa activa o no es una capa de líneas, buscar capa de Red de riego
        if not active_layer or active_layer.type() != active_layer.VectorLayer or active_layer.geometryType() != QgsWkbTypes.LineGeometry:
            for layer in QgsProject.instance().mapLayers().values():
                if layer.name() == "Red de riego":
                    active_layer = layer
                    self.iface.setActiveLayer(active_layer)
                    break
        
        # Activar la herramienta de selección
        if active_layer:
            action.trigger()
            # Marcar el checkbox de selección automáticamente
            if hasattr(self, 'sel_check'):
                self.sel_check.setChecked(True)
            
            # Mostrar mensaje en la barra de estado
            self.iface.messageBar().pushMessage(
                "Selección", 
                f"Seleccionando objetos espaciales en la capa {active_layer.name()}", 
                Qgis.Info, 
                3  # Duración en segundos
            )

    def seleccionar_todos(self):
        # Seleccionar todos los objetos de la capa activa
        active_layer = self.iface.activeLayer()
        
        # Si no hay capa activa o no es una capa de líneas, buscar capa de Red de riego
        if not active_layer or active_layer.type() != active_layer.VectorLayer or active_layer.geometryType() != QgsWkbTypes.LineGeometry:
            for layer in QgsProject.instance().mapLayers().values():
                if layer.name() == "Red de riego":
                    active_layer = layer
                    self.iface.setActiveLayer(active_layer)
                    break
        
        if active_layer:
            active_layer.selectAll()
            # Marcar el checkbox de selección automáticamente
            if hasattr(self, 'sel_check'):
                self.sel_check.setChecked(True)
            
            # Mostrar mensaje en la barra de estado
            self.iface.messageBar().pushMessage(
                "Selección", 
                f"Se han seleccionado {active_layer.selectedFeatureCount()} objetos en la capa {active_layer.name()}", 
                Qgis.Success, 
                3  # Duración en segundos
            )
            
            # Forzar la actualización del canvas
            self.iface.mapCanvas().refresh()

    def deseleccionar_todos(self):
        # Deseleccionar todos los objetos de la capa activa
        active_layer = self.iface.activeLayer()
        
        # Si no hay capa activa o no es una capa de líneas, buscar capa de Red de riego
        if not active_layer or active_layer.type() != active_layer.VectorLayer or active_layer.geometryType() != QgsWkbTypes.LineGeometry:
            for layer in QgsProject.instance().mapLayers().values():
                if layer.name() == "Red de riego":
                    active_layer = layer
                    self.iface.setActiveLayer(active_layer)
                    break
        
        if active_layer:
            # Guardar el número de objetos que estaban seleccionados
            num_selected = active_layer.selectedFeatureCount()
            
            # Deseleccionar
            active_layer.removeSelection()
            
            # Opcional: desmarcar el checkbox de usar selección
            if hasattr(self, 'sel_check'):
                self.sel_check.setChecked(False)
            
            # Mostrar mensaje en la barra de estado
            self.iface.messageBar().pushMessage(
                "Deselección", 
                f"Se han deseleccionado {num_selected} objetos en la capa {active_layer.name()}", 
                Qgis.Success, 
                3  # Duración en segundos
            )
            
            # Forzar la actualización del canvas
            self.iface.mapCanvas().refresh()

    def activar_identificar(self):
        """Activa la herramienta de identificación de QGIS"""
        self.iface.actionIdentify().trigger()
        
        # Mostrar mensaje en la barra de estado
        self.iface.messageBar().pushMessage(
            "Identificación", 
            "Herramienta de identificación activada. Haga clic sobre un objeto para identificarlo.", 
            Qgis.Info, 
            3  # Duración en segundos
        )

    def asignar_atributos(self):
        layer = self.iface.activeLayer()
        if not layer or layer.geometryType() != QgsWkbTypes.LineGeometry:
            return

        try:
            diam = int(self.diam_combo.currentText())
        except ValueError:
            return

        # Determinar si trabajamos con elementos seleccionados o todos
        use_selected = self.sel_check.isChecked()
        
        layer.startEditing()
        
        if use_selected:
            # Trabajar solo con los elementos seleccionados
            selected_features = layer.selectedFeatures()
            if not selected_features:
                # Informar al usuario que no hay elementos seleccionados
                self.iface.messageBar().pushWarning(
                    "Red de Riego",
                    "No hay elementos seleccionados. Seleccione al menos un elemento o desactive la opción."
                )
                layer.rollBack()
                return
                
            for feat in selected_features:
                geom = feat.geometry()
                length = geom.length()
                feat["Tipo"] = self.tipo_combo.currentText()
                feat["Material"] = self.material_combo.currentText()
                feat["L"] = round(length, 2)
                feat["DN"] = diam
                feat["Sector"] = int(self.sector_input.text())
                feat["Tipo_riego"] = self.tipo_riego_combo.currentText()
                layer.updateFeature(feat)
        else:
            # Trabajar con todos los elementos de la capa
            for feat in layer.getFeatures():
                geom = feat.geometry()
                length = geom.length()
                feat["Tipo"] = self.tipo_combo.currentText()
                feat["Material"] = self.material_combo.currentText()
                feat["L"] = round(length, 2)
                feat["DN"] = diam
                feat["Sector"] = int(self.sector_input.text())
                feat["Tipo_riego"] = self.tipo_riego_combo.currentText()
                layer.updateFeature(feat)
        
        layer.commitChanges()
        layer.triggerRepaint()

    def dibujar_red(self):
        """Activa la herramienta de dibujo con longitud específica"""
        layer = self.iface.activeLayer()
        if not layer or layer.geometryType() != QgsWkbTypes.LineGeometry:
            self.iface.messageBar().pushWarning(
                "Red de Riego",
                "Debe crear o seleccionar primero una capa de líneas."
            )
            return
            
        if not layer.isEditable():
            layer.startEditing()
            
        try:
            diam = int(self.diam_combo.currentText())
        except ValueError:
            self.iface.messageBar().pushWarning(
                "Red de Riego",
                "Por favor, seleccione un diámetro válido."
            )
            return
        
        # Activar el snapping en el proyecto
        snapping_config = QgsProject.instance().snappingConfig()
        original_enabled = snapping_config.enabled()
        if not original_enabled:
            snapping_config.setEnabled(True)
            QgsProject.instance().setSnappingConfig(snapping_config)
            
        # Creamos la herramienta de dibujo personalizada usando el CRS de la capa
        if self.drawing_tool:
            self.drawing_tool.deactivate()
            
        self.drawing_tool = LineDrawingTool(self.canvas, self.initial_length, layer.crs())
        self.drawing_tool.lineCaptured.connect(self.add_line_feature)
        self.canvas.setMapTool(self.drawing_tool)
        
        # Mostrar mensaje informativo
        self.iface.messageBar().pushInfo(
            "Red de Riego",
            "Herramienta de dibujo activada. Haga clic para definir el punto inicial. " +
            "La caja flotante mostrará la distancia actual y le permitirá ingresar una longitud específica."
        )
    
    def add_line_feature(self, geometry, length):
        """Añade una nueva característica de línea a la capa activa"""
        layer = self.iface.activeLayer()
        if not layer or not layer.isEditable():
            return
            
        # Crear la nueva característica
        feature = QgsFeature(layer.fields())
        feature.setGeometry(geometry)
                
        # Asignar atributos
        feature["Tipo"] = self.tipo_combo.currentText()
        feature["Material"] = self.material_combo.currentText() 
        feature["L"] = round(length, 2)  # Usar la longitud calculada
        
        try:
            feature["DN"] = int(self.diam_combo.currentText())
        except ValueError:
            feature["DN"] = 0
            
        try:
            feature["Sector"] = int(self.sector_input.text())
        except ValueError:
            feature["Sector"] = 1
            
        feature["Tipo_riego"] = self.tipo_riego_combo.currentText()
            
        # Añadir la característica a la capa
        layer.addFeature(feature)
        layer.triggerRepaint()
        
        # Guardar la última longitud utilizada para el próximo dibujo
        self.initial_length = length
        
        # Informar al usuario que se ha dibujado la línea
        self.iface.messageBar().pushInfo(
            "Red de Riego",
            f"Línea dibujada con éxito. Longitud: {round(length, 2)}m, Diámetro: {feature['DN']}mm"
        )

    def encontrar_capa_red_riego(self):
        """Busca y devuelve la capa 'Red de riego' o None si no existe"""
        for layer in QgsProject.instance().mapLayers().values():
            if layer.name() == "Red de riego" and layer.geometryType() == QgsWkbTypes.LineGeometry:
                return layer
        return None

    def actualizar_resumen(self):
        """Actualiza el resumen de la red de riego según el filtro seleccionado"""
        # Buscar la capa "Red de riego"
        red_layer = None
        for layer in QgsProject.instance().mapLayers().values():
            if layer.name() == "Red de riego" and layer.geometryType() == QgsWkbTypes.LineGeometry:
                red_layer = layer
                break
        
        if not red_layer:
            self.resumen_texto.setHtml("<p>No se encontró la capa 'Red de riego'. Por favor, verifique que existe una capa con este nombre.</p>")
            return
        
        # Determinar el filtro seleccionado
        filtro_seleccionado = self.filtro_combo.currentText()
        filtro_expr = ""
        
        if filtro_seleccionado != "Toda la red":
            # Construir expresión de filtro
            filtro_expr = f"\"Tipo\" = '{filtro_seleccionado}'"
        
        # Agrupar por diámetro y calcular longitudes
        diametros = defaultdict(float)
        longitud_total = 0
        
        # Usar un filtro si es necesario
        request = QgsFeatureRequest()
        if filtro_expr:
            request.setFilterExpression(filtro_expr)
        
        # Recorrer las características y agrupar por diámetro
        for feature in red_layer.getFeatures(request):
            try:
                # Obtener atributos
                diametro = feature["DN"]
                longitud = feature["L"]
                
                # Acumular longitud por diámetro
                if diametro and longitud:
                    diametros[diametro] += longitud
                    longitud_total += longitud
            except (KeyError, TypeError):
                # Ignorar características que no tienen los atributos requeridos
                continue
        
        # Construir el texto del resumen
        html_resumen = f"<h3>Resumen de {filtro_seleccionado}</h3>"
        
        if not diametros:
            html_resumen += "<p>No se encontraron tuberías que cumplan con el filtro seleccionado.</p>"
        else:
            # Ordenar diámetros para una presentación consistente (de mayor a menor)
            diametros_ordenados = sorted(diametros.keys(), reverse=True)
            
            # Generar secciones por tipo de tubería
            if filtro_seleccionado == "Toda la red":
                # Agrupar por tipo de tubería
                tipos = {"Matriz": {}, "Terciarias": {}, "Laterales": {}}
                tipo_longitud_total = defaultdict(float)
                
                # Recorrer nuevamente para agrupar por tipo
                for feature in red_layer.getFeatures():
                    try:
                        tipo = feature["Tipo"]
                        diametro = feature["DN"]
                        longitud = feature["L"]
                        
                        if tipo and diametro and longitud:
                            if diametro not in tipos[tipo]:
                                tipos[tipo][diametro] = 0
                            tipos[tipo][diametro] += longitud
                            tipo_longitud_total[tipo] += longitud
                    except (KeyError, TypeError):
                        continue
                
                # Generar resumen por tipo
                for tipo in ["Matriz", "Terciarias", "Laterales"]:
                    if tipos[tipo]:
                        diametros_tipo = sorted(tipos[tipo].keys(), reverse=True)
                        html_resumen += f"<p><b>{tipo}:</b> "
                        detalles = []
                        for diam in diametros_tipo:
                            longitud = tipos[tipo][diam]
                            detalles.append(f"{round(longitud, 2)} m de {diam} mm")
                        html_resumen += ", ".join(detalles)
                        html_resumen += f", con un total de <b>{round(tipo_longitud_total[tipo], 2)} m</b> de tuberías.</p>"
            else:
                # Resumen para un solo tipo
                html_resumen += "<p>"
                detalles = []
                for diam in diametros_ordenados:
                    longitud = diametros[diam]
                    detalles.append(f"{round(longitud, 2)} m de {diam} mm")
                html_resumen += ", ".join(detalles)
                html_resumen += f", con un total de <b>{round(longitud_total, 2)} m</b> de tuberías.</p>"
        
        # Mostrar el resumen en el widget de texto
        self.resumen_texto.setHtml(html_resumen)

    def show_and_activate(self):
        """Muestra y activa el panel"""
        self.show()
        self.activateWindow()
        self.raise_()

        # Actualizar el resumen de la red cuando se muestra el panel
        self.actualizar_resumen()