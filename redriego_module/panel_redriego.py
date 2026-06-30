# Archivo: ui/panel_redriego.py
from qgis.PyQt.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QLabel, QComboBox, QLineEdit,
    QCheckBox, QGridLayout, QSizePolicy, QDialog, QToolTip, QDockWidget, QSlider, QHBoxLayout, QToolButton, QSpacerItem,
    QGroupBox, QTextEdit  # Añade estas dos clases
)
from qgis.PyQt.QtGui import QColor, QPainter, QFontMetrics, QRegularExpressionValidator, QIntValidator, QCursor
from qgis.PyQt.QtCore import (
    Qt, pyqtSignal, QPoint, QRect, QRegularExpression, QVariant, QMetaType
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
    QgsFeatureRequest,  # Añade esta clase
    QgsPointLocator,
    QgsTolerance
)

from qgis.PyQt.QtGui import QIcon
from qgis.utils import iface
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
        self.setFixedSize(96, 48)
        
        # Crear campo de texto
        self.edit = QLineEdit(self)
        self.edit.setGeometry(0, 0, 96, 28)
        self.edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.edit.setValidator(QRegularExpressionValidator(QRegularExpression("\\d+(\\.\\d+)?")))
        self.edit.setText(str(initial_value))
        self.edit.returnPressed.connect(self.on_value_entered)
        
        # Estilo para hacer el campo más limpio
        self.edit.setStyleSheet("""
            QLineEdit {
                background-color: rgba(255, 255, 255, 150);
                border: 1px solid rgba(100, 100, 100, 150);
                border-radius: 5px;
                padding: 2px;
                font-weight: bold;
                color: black;
                font-size: 9pt;
            }
        """)

        # Etiqueta de azimut/ángulo (debajo del campo)
        self.angle_label = QLabel("", self)
        self.angle_label.setGeometry(0, 29, 96, 17)
        self.angle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.angle_label.setStyleSheet("""
            QLabel {
                background-color: rgba(40, 40, 40, 160);
                border-radius: 4px;
                color: white;
                font-size: 8pt;
            }
        """)
        
        # Asegurarnos de que el widget sea visible por encima de otros elementos
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)  # No queremos que el widget principal tome el foco
        
    def update_value(self, value):
        """Actualiza el valor mostrado sin emitir señal"""
        if not self.edit.hasFocus():
            self.edit.setText(f"{value:.1f}")

    def set_angle(self, deg, ortho=False):
        """Muestra el azimut actual; añade un aviso cuando el ángulo está bloqueado."""
        txt = f"∠ {deg:.0f}°"
        if ortho:
            txt += "  ⊾ orto"
        self.angle_label.setText(txt)
    
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
    """Herramienta para dibujar líneas de longitud específica.

    Mejoras:
      - Geodesia correcta en CRS geográfico (computeSpheroidProject); la previa
        y la línea final coinciden siempre.
      - Transformación capa<->mapa correcta cuando el CRS de capa != proyecto.
      - Bloqueo de ángulo: mantener Shift fija el azimut a múltiplos de 45°
        (ortogonal/diagonal), ideal para rejillas de riego.
      - Clic derecho termina la cadena continua; Ctrl+Z deshace el último tramo.
      - Previa ligera (sin refrescar todas las capas).
      - Un único cálculo del punto final reutilizado por previa, clic y Enter.
    """
    lineCaptured = pyqtSignal(object, float)   # Geometría, longitud
    undoLastRequested = pyqtSignal()           # Deshacer último tramo

    ANGLE_STEP = math.radians(45)              # paso del bloqueo de ángulo

    def __init__(self, canvas, initial_length, layer_crs):
        super().__init__(canvas)
        self.canvas = canvas
        self.target_length = initial_length
        self.layer_crs = layer_crs
        self.project_crs = canvas.mapSettings().destinationCrs()

        self.is_numeric_input_started = False
        self.last_end_point = None          # último punto final (coords de capa)
        self.continuous_mode = True
        self.last_mouse_pos = None
        self.last_map_point = None          # último punto del ratón (coords de mapa)
        self.constrain_angle = False        # Shift -> ortogonal/45°
        self.floating_input = None

        # Snapping
        self.snapping_utils = QgsMapCanvasSnappingUtils(canvas)
        self.snapping_utils.setConfig(QgsProject.instance().snappingConfig())
        self.snap_indicator = QgsSnapIndicator(canvas)

        # Transformaciones proyecto<->capa (en ambos sentidos)
        self.need_transform = (self.layer_crs.srsid() != self.project_crs.srsid())
        if self.need_transform:
            self.transform = QgsCoordinateTransform(
                self.project_crs, self.layer_crs, QgsProject.instance())
            self.transform_to_map = QgsCoordinateTransform(
                self.layer_crs, self.project_crs, QgsProject.instance())

        # Bandas de goma
        self.rubber_band = QgsRubberBand(canvas, QgsWkbTypes.LineGeometry)
        self.rubber_band.setColor(QColor(0, 0, 255, 100))
        self.rubber_band.setWidth(2)

        self.temp_rubber_band = QgsRubberBand(canvas, QgsWkbTypes.LineGeometry)
        self.temp_rubber_band.setColor(QColor(255, 0, 0, 100))
        self.temp_rubber_band.setWidth(2)

        # Marcador de vértice
        self.vertex_marker = QgsVertexMarker(canvas)
        self.vertex_marker.setColor(QColor(255, 0, 0))
        self.vertex_marker.setPenWidth(2)
        self.vertex_marker.setIconSize(5)
        self.vertex_marker.setIconType(QgsVertexMarker.ICON_CIRCLE)
        self.vertex_marker.hide()

        # Cálculo de distancias (elipsoidal)
        self.distance_area = QgsDistanceArea()
        self.distance_area.setSourceCrs(self.layer_crs, QgsProject.instance().transformContext())
        self.distance_area.setEllipsoid(QgsProject.instance().ellipsoid())

        self.points = []
        self.chain = []          # vértices de la cadena continua actual
        self.current_length = 0.0

    # ── Conversión de coordenadas ─────────────────────────────────────────
    def activate(self):
        super().activate()
        # Limpiar cualquier tooltip heredado de otra herramienta sobre el lienzo
        self.canvas.setToolTip("")

    def deactivate(self):
        self.canvas.setToolTip("")
        self.rubber_band.reset(QgsWkbTypes.LineGeometry)
        self.temp_rubber_band.reset(QgsWkbTypes.LineGeometry)
        self.vertex_marker.hide()
        self.snap_indicator.setVisible(False)
        if self.floating_input:
            self.floating_input.hide()
            self.floating_input.deleteLater()
            self.floating_input = None
        super().deactivate()

    def toLayerCoordinates(self, point):
        """Mapa -> CRS de la capa."""
        if self.need_transform:
            try:
                return self.transform.transform(point)
            except Exception:
                return point
        return point

    def layerToMap(self, layer_point):
        """CRS de la capa -> mapa (para mostrar en el lienzo)."""
        if self.need_transform:
            try:
                return self.transform_to_map.transform(layer_point)
            except Exception:
                return layer_point
        return layer_point

    # ── Geometría: un único cálculo del punto final ───────────────────────
    def _shift_held(self):
        """True si Shift está pulsado AHORA (estado global, no depende del foco)."""
        from qgis.PyQt.QtWidgets import QApplication
        return bool(QApplication.keyboardModifiers() & Qt.KeyboardModifier.ShiftModifier)

    def _azimuth(self, start, target):
        """Azimut (rad, horario desde el norte) de start->target, con bloqueo opcional."""
        dx = target.x() - start.x()
        dy = target.y() - start.y()
        if dx == 0 and dy == 0:
            return 0.0
        az = math.atan2(dx, dy)
        if self.constrain_angle:
            az = round(az / self.ANGLE_STEP) * self.ANGLE_STEP
        return az

    def endpoint_for(self, start, target, length):
        """Punto final (coords de capa) a 'length' metros en la dirección start->target.

        Usa proyección geodésica en CRS geográfico y trigonometría directa en
        CRS proyectado; ambos con el mismo convenio de azimut, así que la previa
        y el resultado final son idénticos.
        """
        az = self._azimuth(start, target)
        if self.layer_crs.isGeographic():
            return self.distance_area.computeSpheroidProject(start, length, az)
        return QgsPointXY(start.x() + length * math.sin(az),
                          start.y() + length * math.cos(az))

    # ── Previa ligera ─────────────────────────────────────────────────────
    def _update_preview(self):
        """Redibuja la línea de longitud exacta sin refrescar las capas."""
        if len(self.points) != 1 or self.last_map_point is None:
            return
        self.constrain_angle = self._shift_held()
        start = self.points[0]
        target = self.toLayerCoordinates(self.last_map_point)
        az = self._azimuth(start, target)
        end = self.endpoint_for(start, target, self.target_length)
        self.rubber_band.reset(QgsWkbTypes.LineGeometry)
        self.rubber_band.addPoint(self.layerToMap(start))
        self.rubber_band.addPoint(self.layerToMap(end))
        if self.floating_input:
            self.floating_input.set_angle(math.degrees(az) % 360, self.constrain_angle)

    def reset(self):
        """Reinicia el dibujo conservando el último punto en modo continuo."""
        last_point = self.last_end_point

        self.points = []
        self.rubber_band.reset(QgsWkbTypes.LineGeometry)
        self.temp_rubber_band.reset(QgsWkbTypes.LineGeometry)
        self.vertex_marker.hide()
        self.snap_indicator.setVisible(False)
        self.is_numeric_input_started = False

        if self.floating_input:
            self.floating_input.hide()
            self.floating_input.deleteLater()
            self.floating_input = None

        if self.continuous_mode and last_point:
            # Encadenar: el final anterior es el inicio del siguiente tramo
            self.points.append(last_point)
            map_point = self.layerToMap(last_point)
            self.vertex_marker.setCenter(map_point)
            self.vertex_marker.show()
            self.rubber_band.reset(QgsWkbTypes.LineGeometry)
            self.rubber_band.addPoint(map_point)

            self.floating_input = FloatingLengthInput(self.canvas, self.target_length)
            self.floating_input.valueChanged.connect(self.update_length)
            pixel_point = self.canvas.mapSettings().mapToPixel().transform(map_point)
            self.floating_input.position_at(QPoint(int(pixel_point.x()), int(pixel_point.y())))
            self.floating_input.show()

    def emit_geometry(self, geometry):
        """Emite la línea capturada y guarda su punto final (coords de capa)."""
        real_length = self.distance_area.measureLength(geometry)
        if geometry.type() == QgsWkbTypes.LineGeometry:
            line = geometry.asPolyline()
            if len(line) >= 2:
                self.last_end_point = line[-1]
                self.chain.append(line[-1])
        self.lineCaptured.emit(geometry, real_length)

    def undo_segment(self):
        """Retrocede la cadena un vértice tras deshacer el último tramo en la capa.

        Devuelve True si había un tramo confirmado. Si quedan vértices, el dibujo
        continúa desde el vértice anterior (la red sigue conectada); si no, empieza
        de cero.
        """
        if len(self.chain) >= 2:
            self.chain.pop()
            self.last_end_point = self.chain[-1]
            self.continuous_mode = True
            self.reset()
            return True
        self.chain = []
        self.last_end_point = None
        self.continuous_mode = True
        self.reset()
        return False

    # ── Eventos del lienzo ────────────────────────────────────────────────
    def canvasPressEvent(self, event):
        self.last_mouse_pos = event
        self.constrain_angle = self._shift_held()

        # Clic derecho: terminar la cadena continua
        if event.button() == Qt.MouseButton.RightButton:
            self.continuous_mode = False
            self.last_end_point = None
            self.chain = []
            self.reset()
            self.continuous_mode = True
            return

        if event.button() != Qt.MouseButton.LeftButton:
            return

        snapping_result = self.snapping_utils.snapToMap(event.pos())
        if snapping_result.isValid():
            map_point = snapping_result.point()
        else:
            map_point = self.toMapCoordinates(event.pos())
        layer_point = self.toLayerCoordinates(map_point)

        self.snap_indicator.setVisible(False)

        if self.floating_input and len(self.points) == 1:
            try:
                self.target_length = float(self.floating_input.edit.text())
            except ValueError:
                pass
            self.floating_input.hide()
            self.floating_input.deleteLater()
            self.floating_input = None

        self.points.append(layer_point)
        self.vertex_marker.setCenter(map_point)
        self.vertex_marker.show()

        if len(self.points) == 1:
            if self.last_end_point is None:
                self.chain = [self.points[0]]
            self.rubber_band.reset(QgsWkbTypes.LineGeometry)
            self.rubber_band.addPoint(map_point)
            self.is_numeric_input_started = False
            if self.floating_input:
                self.floating_input.deleteLater()
            self.floating_input = FloatingLengthInput(self.canvas, self.target_length)
            self.floating_input.valueChanged.connect(self.update_length)
            self.floating_input.position_at(event.pos())
            self.floating_input.show()

        elif len(self.points) >= 2:
            start = self.points[-2]
            target = self.points[-1]
            geometry = QgsGeometry.fromPolylineXY(
                [start, self.endpoint_for(start, target, self.target_length)])
            self.emit_geometry(geometry)
            self.reset()

    def canvasMoveEvent(self, event):
        self.last_mouse_pos = event
        self.constrain_angle = self._shift_held()

        snapping_result = self.snapping_utils.snapToMap(event.pos())
        if snapping_result.isValid():
            self.snap_indicator.setVisible(True)
            self.snap_indicator.setMatch(snapping_result)
            map_point = snapping_result.point()
        else:
            self.snap_indicator.setVisible(False)
            map_point = self.toMapCoordinates(event.pos())
        self.last_map_point = map_point

        if len(self.points) > 0:
            # Rastro temporal hasta el ratón
            self.temp_rubber_band.reset(QgsWkbTypes.LineGeometry)
            self.temp_rubber_band.addPoint(self.layerToMap(self.points[-1]))
            self.temp_rubber_band.addPoint(map_point)

            if len(self.points) == 1:
                start = self.points[0]
                target = self.toLayerCoordinates(map_point)
                current_length = self.distance_area.measureLength(
                    QgsGeometry.fromPolylineXY([start, target]))
                if self.floating_input:
                    self.floating_input.position_at(event.pos())
                    self.floating_input.update_value(current_length)
                self._update_preview()

    def update_length(self, value):
        """Nuevo valor de longitud objetivo -> refresca solo la previa."""
        self.target_length = value
        self._update_preview()

    def keyPressEvent(self, event):
        # Deshacer último tramo (Supr/Delete): lo gestiona el panel sobre la capa.
        # Se usa Supr en vez de Ctrl+Z porque QGIS captura Ctrl+Z globalmente (la
        # acción Deshacer siempre está activa) y el evento no llega a la herramienta,
        # con lo que el inicio de la cadena quedaba desincronizado.
        if event.key() == Qt.Key.Key_Delete:
            self.undoLastRequested.emit()
            event.accept()
            return

        # Shift: activar el bloqueo de ángulo al instante (sin esperar a mover el ratón)
        if event.key() == Qt.Key.Key_Shift:
            self.constrain_angle = True
            self._update_preview()
            event.ignore()
            return

        if len(self.points) == 1:
            # Escape: cancelar la línea actual
            if event.key() == Qt.Key.Key_Escape:
                self.continuous_mode = False
                self.last_end_point = None
                self.chain = []
                self.reset()
                self.continuous_mode = True
                event.accept()
                return

            # Enter: confirmar con la longitud actual en dirección al ratón
            elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                if self.floating_input:
                    try:
                        self.target_length = float(self.floating_input.edit.text())
                    except ValueError:
                        pass
                if self.target_length > 0:
                    cursor_pos = self.canvas.mouseLastXY()
                    mouse_point = self.canvas.getCoordinateTransform().toMapCoordinates(
                        cursor_pos.x(), cursor_pos.y())
                    snapping_result = self.snapping_utils.snapToMap(
                        QPoint(cursor_pos.x(), cursor_pos.y()))
                    if snapping_result.isValid():
                        mouse_point = snapping_result.point()
                    self.constrain_angle = self._shift_held()
                    target = self.toLayerCoordinates(mouse_point)
                    start = self.points[0]
                    geometry = QgsGeometry.fromPolylineXY(
                        [start, self.endpoint_for(start, target, self.target_length)])
                    self.emit_geometry(geometry)
                    self.reset()
                event.accept()
                return

            # Dígitos y punto decimal: entrada numérica directa
            elif (Qt.Key.Key_0 <= event.key() <= Qt.Key.Key_9) or event.key() == Qt.Key.Key_Period:
                if self.floating_input:
                    if not self.is_numeric_input_started:
                        self.floating_input.edit.clear()
                        self.is_numeric_input_started = True
                    new_text = self.floating_input.edit.text() + event.text()
                    try:
                        value = float(new_text)
                        self.floating_input.edit.setText(new_text)
                        self.target_length = value
                        self._update_preview()
                    except ValueError:
                        pass
                    event.accept()
                    return

            # Retroceso
            elif event.key() == Qt.Key.Key_Backspace:
                if self.floating_input and self.is_numeric_input_started:
                    current_text = self.floating_input.edit.text()
                    if current_text:
                        new_text = current_text[:-1]
                        if new_text:
                            try:
                                value = float(new_text)
                                self.floating_input.edit.setText(new_text)
                                self.target_length = value
                            except ValueError:
                                pass
                        else:
                            self.floating_input.edit.setText("0")
                            self.target_length = 0.0
                        self._update_preview()
                    event.accept()
                    return

        event.ignore()

    def keyReleaseEvent(self, event):
        # Al soltar Shift se desactiva el bloqueo de ángulo
        if event.key() == Qt.Key.Key_Shift:
            self.constrain_angle = False
            self._update_preview()
        event.ignore()

class LineSelectionTool(QgsMapToolEmitPoint):
    """Herramienta para seleccionar una línea como destino para extender otras líneas"""
    lineSelected = pyqtSignal(QgsFeature)
    
    def __init__(self, canvas, layer):
        super().__init__(canvas)
        self.canvas = canvas
        self.layer = layer
        self.cursor = QCursor(Qt.CursorShape.CrossCursor)
        
        # Configurar snapping
        self.snapping_utils = QgsMapCanvasSnappingUtils(canvas)
        self.snapping_utils.setConfig(QgsProject.instance().snappingConfig())
        self.snap_indicator = QgsSnapIndicator(canvas)
        
        # Configurar marcador temporal para el clic
        self.vertex_marker = QgsVertexMarker(canvas)
        self.vertex_marker.setColor(QColor(255, 0, 0))
        self.vertex_marker.setPenWidth(2)
        self.vertex_marker.setIconSize(5)
        self.vertex_marker.setIconType(QgsVertexMarker.ICON_CIRCLE)
        self.vertex_marker.hide()
        
        # Configurar banda de goma para destacar la línea
        self.rubber_band = QgsRubberBand(canvas, QgsWkbTypes.LineGeometry)
        self.rubber_band.setColor(QColor(0, 255, 0, 150))
        self.rubber_band.setWidth(3)
        
    def activate(self):
        """Se llama cuando se activa la herramienta"""
        super().activate()
        self.canvas.setCursor(self.cursor)
        
    def deactivate(self):
        """Se llama cuando se desactiva la herramienta"""
        self.snap_indicator.setVisible(False)
        self.vertex_marker.hide()
        self.rubber_band.reset(QgsWkbTypes.LineGeometry)
        super().deactivate()
        
    def canvasMoveEvent(self, event):
        """Maneja el movimiento del ratón en el canvas"""
        # Intentar hacer snap a una línea
        snapping_result = self.snapping_utils.snapToMap(event.pos())
        
        if snapping_result.isValid() and snapping_result.layer() and snapping_result.layer().id() == self.layer.id():
            # Mostrar indicador de snap
            self.snap_indicator.setVisible(True)
            self.snap_indicator.setMatch(snapping_result)
            
            # Destacar la línea a la que se hace snap
            feature_id = snapping_result.featureId()
            request = QgsFeatureRequest().setFilterFid(feature_id)
            features = list(self.layer.getFeatures(request))
            
            if features:
                # Mostrar la línea en el rubber band
                self.rubber_band.reset(QgsWkbTypes.LineGeometry)
                self.rubber_band.setToGeometry(features[0].geometry(), None)
        else:
            # Ocultar indicadores si no hay snap válido
            self.snap_indicator.setVisible(False)
            self.rubber_band.reset(QgsWkbTypes.LineGeometry)
    
    def canvasPressEvent(self, event):
        """Maneja el clic en el canvas"""
        if event.button() == Qt.MouseButton.LeftButton:
            # Intentar hacer snap a una línea
            snapping_result = self.snapping_utils.snapToMap(event.pos())
            
            if snapping_result.isValid() and snapping_result.layer() and snapping_result.layer().id() == self.layer.id():
                # Obtener el feature seleccionado
                feature_id = snapping_result.featureId()
                request = QgsFeatureRequest().setFilterFid(feature_id)
                features = list(self.layer.getFeatures(request))
                
                if features:
                    # Emitir señal con el feature seleccionado
                    self.lineSelected.emit(features[0])
                    
                    # Mostrar marcador en el punto de clic
                    self.vertex_marker.setCenter(snapping_result.point())
                    self.vertex_marker.show()
            else:
                # Si no hay snap, limpiar selección
                self.vertex_marker.hide()
                self.rubber_band.reset(QgsWkbTypes.LineGeometry)

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
        self.btn_identificar.setIcon(self.cargar_icono('identificar.svg'))
        self.btn_identificar.setToolTip("Identificar objetos espaciales")
        self.btn_identificar.clicked.connect(self.activar_identificar)

        # Añadir botón para extender líneas
        self.btn_extender = QToolButton()
        self.btn_extender.setIcon(self.cargar_icono('extender.svg'))  # Necesitarás crear este icono
        self.btn_extender.setToolTip("Extender líneas seleccionadas hasta otra línea")
        self.btn_extender.clicked.connect(self.extender_lineas)

        # Añadir botón para invertir líneas
        self.btn_invertir = QToolButton()
        self.btn_invertir.setIcon(self.cargar_icono('invertir.svg'))
        self.btn_invertir.setToolTip("Invertir líneas seleccionadas")
        self.btn_invertir.clicked.connect(self.invertir_lineas)

        # Añadir botón para redimensionar líneas
        self.btn_redimensionar = QToolButton()
        self.btn_redimensionar.setIcon(self.cargar_icono('redimensionar.svg'))
        self.btn_redimensionar.setToolTip("Redimensionar línea")
        self.btn_redimensionar.clicked.connect(self.redimensionar_linea)

        # Añadir botón "Dibujar red" con el icono de añadir línea
        self.btn_dibujar_red = QToolButton()
        self.btn_dibujar_red.setIcon(self.cargar_icono('dibujar.svg'))
        self.btn_dibujar_red.setToolTip("Dibujar red")
        self.btn_dibujar_red.clicked.connect(self.dibujar_red)
        
        # Configurar el layout principal de la barra de herramientas
        toolbar_layout.addLayout(selection_layout)  # Botones de selección a la izquierda
        toolbar_layout.addStretch()                 # Espacio en medio
        toolbar_layout.addWidget(self.btn_identificar)  # Botón de identificar
        toolbar_layout.addWidget(self.btn_extender)  # Botón de extender líneas
        toolbar_layout.addWidget(self.btn_invertir)  # Botón de invertir líneas
        toolbar_layout.addWidget(self.btn_redimensionar)  # Botón de redimensionar línea
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
        self.tipo_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout.addWidget(self.tipo_combo, row, 0)
        row += 1
        
        layout.addWidget(QLabel("Diámetro nominal (mm):"), row, 0)
        row += 1
        self.diam_combo = QComboBox()
        self.diam_combo.addItems(["16", "17", "20", "25", "32", "40", "50", "63", "75", "90", "110", "125", "140", "160", "200", "250", "280", "315"])
        self.diam_combo.setCurrentText("50")  # Valor por defecto
        self.diam_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout.addWidget(self.diam_combo, row, 0)
        row += 1

        # Material
        layout.addWidget(QLabel("Material:"), row, 0)
        row += 1
        self.material_combo = QComboBox()
        self.material_combo.addItems(["PE", "PVC", "HDPE"])
        self.material_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout.addWidget(self.material_combo, row, 0)
        row += 1

        # Sector
        layout.addWidget(QLabel("Sector (1-20):"), row, 0)
        row += 1
        self.sector_input = QLineEdit("1")
        self.sector_input.setValidator(QIntValidator(1, 20))
        self.sector_input.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout.addWidget(self.sector_input, row, 0)
        row += 1

        # Tipo de riego
        layout.addWidget(QLabel("Tipo de riego:"), row, 0)
        row += 1
        self.tipo_riego_combo = QComboBox()
        self.tipo_riego_combo.addItems(["Aspersion", "Goteo", "Cintas", "Subterraneo", "Microaspersion"])
        self.tipo_riego_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout.addWidget(self.tipo_riego_combo, row, 0)
        row += 1
        
        # Checkbox para operar solo en elementos seleccionados
        self.sel_check = QCheckBox("Solo elementos seleccionados")
        layout.addWidget(self.sel_check, row, 0)
        row += 1
        
        self.asignar_btn = QPushButton("Asignar atributos")
        self.asignar_btn.clicked.connect(self.asignar_atributos)
        self.asignar_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
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

        # Layout para botones de resumen
        resumen_buttons_layout = QHBoxLayout()

        # Botón para actualizar resumen
        self.btn_actualizar_resumen = QPushButton("Actualizar resumen")
        self.btn_actualizar_resumen.clicked.connect(self.actualizar_resumen)
        resumen_buttons_layout.addWidget(self.btn_actualizar_resumen)

        # Botón para crear tabla resumen
        self.btn_crear_tabla = QToolButton()
        self.btn_crear_tabla.setIcon(self.cargar_icono('tabla_resumen.svg'))
        self.btn_crear_tabla.setToolTip("Crear tabla resumen de longitudes")
        self.btn_crear_tabla.clicked.connect(self.crear_tabla_resumen)
        resumen_buttons_layout.addWidget(self.btn_crear_tabla)

        # Añadir layout de botones
        red_summary_layout.addLayout(resumen_buttons_layout)

        self.red_summary_group.setLayout(red_summary_layout)
        layout.addWidget(self.red_summary_group, row, 0)
        row += 1

        # Añadir un espaciador para ocupar el espacio restante
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
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
                Qgis.MessageLevel.Info, 
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
                Qgis.MessageLevel.Success, 
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
                Qgis.MessageLevel.Success, 
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
            Qgis.MessageLevel.Info, 
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
        self.drawing_tool.undoLastRequested.connect(self.undo_last_line)
        self.canvas.setMapTool(self.drawing_tool)
        
        # Mostrar mensaje informativo
        self.iface.messageBar().pushInfo(
            "Red de Riego",
            "Dibujo activado. Clic = punto inicial; teclee la longitud o muévase y haga clic. "
            "Shift = ángulo ortogonal/45°, clic derecho = terminar, Supr = deshacer tramo."
        )
    
    def undo_last_line(self):
        """Deshace SOLO el último tramo y continúa la cadena desde el vértice anterior.

        Quita la última entidad de la pila de edición de la capa y retrocede un
        vértice en la herramienta, de modo que el resto de la red se conserva y el
        dibujo sigue conectado (no se anula toda la red).
        """
        layer = self.iface.activeLayer()
        if not layer or not layer.isEditable() or not self.drawing_tool:
            return
        had_segment = len(self.drawing_tool.chain) >= 2
        if had_segment:
            undo_stack = layer.undoStack()
            if undo_stack is not None and undo_stack.canUndo():
                undo_stack.undo()
                layer.triggerRepaint()
        # Retroceder la cadena un vértice (o reiniciar si ya no quedan tramos)
        self.drawing_tool.undo_segment()
        if had_segment:
            try:
                self.iface.mainWindow().statusBar().showMessage(
                    "Red de Riego — se deshizo el último tramo.", 2500)
            except Exception:
                pass

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
        
        # Mostrar la longitud en la barra de estado (se auto-reemplaza, no satura)
        try:
            self.iface.mainWindow().statusBar().showMessage(
                f"Red de Riego — tramo: {round(length, 2)} m, Ø{feature['DN']} mm", 3000
            )
        except Exception:
            pass

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

    def redimensionar_linea(self):
        """Activa la herramienta para redimensionar líneas existentes"""
        layer = self.iface.activeLayer()
        if not layer or layer.geometryType() != QgsWkbTypes.LineGeometry:
            self.iface.messageBar().pushWarning(
                "Red de Riego",
                "Debe seleccionar primero una capa de líneas."
            )
            return
        
        if not layer.isEditable():
            layer.startEditing()
        
        # Verificar si hay elementos seleccionados
        if layer.selectedFeatureCount() == 0:
            self.iface.messageBar().pushInfo(
                "Red de Riego",
                "Primero seleccione una línea usando la herramienta de selección."
            )
            return
        
        # Obtener la entidad seleccionada
        selected_features = layer.selectedFeatures()
        if len(selected_features) > 1:
            self.iface.messageBar().pushInfo(
                "Red de Riego",
                "Por favor, seleccione solo una línea a la vez."
            )
            return
        
        # Obtener la única entidad seleccionada
        feature = selected_features[0]
        geometry = feature.geometry()
        
        # Verificar que sea una línea
        if geometry.type() != QgsWkbTypes.LineGeometry:
            return
        
        # Calcular longitud actual
        distance_area = QgsDistanceArea()
        distance_area.setSourceCrs(layer.crs(), QgsProject.instance().transformContext())
        distance_area.setEllipsoid(QgsProject.instance().ellipsoid())
        current_length = distance_area.measureLength(geometry)
        
        # Crear diálogo para introducir nueva longitud
        from qgis.PyQt.QtWidgets import QDialog, QVBoxLayout, QLabel, QLineEdit, QPushButton, QHBoxLayout
        
        dialog = QDialog(self.iface.mainWindow())
        dialog.setWindowTitle("Redimensionar línea")
        dialog.setFixedWidth(300)
        
        layout = QVBoxLayout()
        
        # Etiqueta informativa
        info_label = QLabel(f"Longitud actual: {round(current_length, 2)} m")
        layout.addWidget(info_label)
        
        # Campo para introducir nueva longitud
        input_layout = QHBoxLayout()
        input_layout.addWidget(QLabel("Nueva longitud (m):"))
        length_input = QLineEdit()
        length_input.setText(str(round(current_length, 2)))
        length_input.setValidator(QRegularExpressionValidator(QRegularExpression("\\d+(\\.\\d+)?")))
        input_layout.addWidget(length_input)
        layout.addLayout(input_layout)
        
        # Botones
        button_layout = QHBoxLayout()
        cancel_button = QPushButton("Cancelar")
        cancel_button.clicked.connect(dialog.reject)
        apply_button = QPushButton("Aplicar")
        apply_button.clicked.connect(dialog.accept)
        button_layout.addWidget(cancel_button)
        button_layout.addWidget(apply_button)
        layout.addLayout(button_layout)
        
        dialog.setLayout(layout)
        
        # Mostrar diálogo
        if dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                new_length = float(length_input.text())
                if new_length <= 0:
                    self.iface.messageBar().pushWarning(
                        "Red de Riego",
                        "La longitud debe ser mayor que cero."
                    )
                    return
                    
                # Calcular factor de escala
                scale_factor = new_length / current_length if current_length > 0 else 1.0
                
                # Obtener vértices
                line = geometry.asPolyline()
                
                # Crear nueva geometría redimensionada
                new_line = []
                
                # Mantener el primer punto fijo y escalar el resto
                fixed_point = line[0]
                new_line.append(QgsPointXY(fixed_point))
                
                for i in range(1, len(line)):
                    # Vector desde el punto fijo
                    dx = line[i].x() - fixed_point.x()
                    dy = line[i].y() - fixed_point.y()
                    
                    # Aplicar factor de escala
                    new_x = fixed_point.x() + dx * scale_factor
                    new_y = fixed_point.y() + dy * scale_factor
                    
                    new_line.append(QgsPointXY(new_x, new_y))
                
                # Crear nueva geometría
                new_geometry = QgsGeometry.fromPolylineXY(new_line)
                
                # Actualizar geometría
                layer.changeGeometry(feature.id(), new_geometry)
                
                # Actualizar atributo de longitud si existe
                if "L" in feature.fields().names():
                    field_idx = feature.fieldNameIndex("L")
                    layer.changeAttributeValue(feature.id(), field_idx, round(new_length, 2))
                
                # Forzar actualización visual
                layer.triggerRepaint()
                
                # Informar al usuario
                self.iface.messageBar().pushInfo(
                    "Red de Riego",
                    f"Línea redimensionada con éxito. Nueva longitud: {round(new_length, 2)}m"
                )
                
            except ValueError:
                self.iface.messageBar().pushWarning(
                    "Red de Riego",
                    "Por favor, introduzca una longitud válida."
                )

    def update_line_geometry(self, geometry, new_length, feature_id):
        """Actualiza la geometría de una línea existente"""
        layer = self.iface.activeLayer()
        if not layer or not layer.isEditable():
            return
        
        # Actualizar geometría
        layer.changeGeometry(feature_id, geometry)
        
        # Actualizar atributo de longitud
        for field_idx, field in enumerate(layer.fields()):
            if field.name() == "L":
                layer.changeAttributeValue(feature_id, field_idx, round(new_length, 2))
                break
        
        # Forzar actualización visual
        layer.triggerRepaint()
        
        # Informar al usuario
        self.iface.messageBar().pushInfo(
            "Red de Riego",
            f"Línea redimensionada con éxito. Nueva longitud: {round(new_length, 2)}m"
        )

    def invertir_lineas(self):
        """Invierte la dirección de las líneas seleccionadas"""
        layer = self.iface.activeLayer()
        if not layer or layer.geometryType() != QgsWkbTypes.LineGeometry:
            self.iface.messageBar().pushWarning(
                "Red de Riego",
                "Debe seleccionar primero una capa de líneas."
            )
            return
        
        # Verificar si hay elementos seleccionados
        if layer.selectedFeatureCount() == 0:
            self.iface.messageBar().pushInfo(
                "Red de Riego",
                "Seleccione una o más líneas para invertir su dirección."
            )
            return
        
        # Verificar si la capa está en modo edición
        if not layer.isEditable():
            layer.startEditing()
        
        # Invertir cada línea seleccionada
        contador = 0
        for feature in layer.selectedFeatures():
            geometry = feature.geometry()
            
            # Verificar que sea una línea
            if geometry.type() != QgsWkbTypes.LineGeometry:
                continue
            
            # Obtener vértices y revertir el orden
            line = geometry.asPolyline()
            reversed_line = list(reversed(line))
            
            # Crear nueva geometría con el orden invertido
            new_geometry = QgsGeometry.fromPolylineXY(reversed_line)
            
            # Actualizar geometría
            layer.changeGeometry(feature.id(), new_geometry)
            contador += 1
        
        # Forzar actualización visual
        layer.triggerRepaint()
        
        # Informar al usuario
        if contador > 0:
            self.iface.messageBar().pushInfo(
                "Red de Riego",
                f"Se invirtió la dirección de {contador} línea(s) seleccionada(s)."
            )
        else:
            self.iface.messageBar().pushInfo(
                "Red de Riego",
                "No se invirtió ninguna línea."
            )

    def cargar_icono(self, nombre_archivo):
        """Carga un icono desde la carpeta de iconos del plugin"""
        import os
        plugin_dir = os.path.dirname(os.path.abspath(__file__))
        icons_dir = os.path.join(plugin_dir, 'icons')
        icon_path = os.path.join(icons_dir, nombre_archivo)
        
        if os.path.exists(icon_path):
            return QIcon(icon_path)
        else:
            # Retornar un icono por defecto o None
            return QIcon(":/images/themes/default/mActionUnknown.svg")

    def extender_lineas(self):
        """Extiende las líneas seleccionadas hasta intersectar con otra línea que se selecciona en el canvas"""
        layer = self.iface.activeLayer()
        if not layer or layer.geometryType() != QgsWkbTypes.LineGeometry:
            self.iface.messageBar().pushWarning(
                "Red de Riego",
                "Debe seleccionar primero una capa de líneas."
            )
            return
        
        # Verificar si hay elementos seleccionados
        if layer.selectedFeatureCount() == 0:
            self.iface.messageBar().pushInfo(
                "Red de Riego",
                "Primero seleccione una o más líneas que desea extender."
            )
            return
        
        # Verificar si la capa está en modo edición
        if not layer.isEditable():
            layer.startEditing()
        
        # Guardar las líneas seleccionadas para extender
        lineas_a_extender = []
        for feat in layer.selectedFeatures():
            lineas_a_extender.append(QgsFeature(feat))
        
        # Informar al usuario que debe seleccionar la línea destino
        self.iface.messageBar().pushInfo(
            "Red de Riego",
            "Ahora seleccione la línea destino hasta la que extender las líneas."
        )
        
        # Crear y activar la herramienta de selección de línea destino
        self.line_selection_tool = LineSelectionTool(self.iface.mapCanvas(), layer)
        self.line_selection_tool.lineSelected.connect(lambda feat: self.procesar_extension_lineas(lineas_a_extender, feat))
        self.iface.mapCanvas().setMapTool(self.line_selection_tool)

    def procesar_extension_lineas(self, lineas_a_extender, linea_destino_feat):
        """Procesa la extensión de las líneas seleccionadas hasta la línea destino"""
        # Desactivar la herramienta de selección de línea
        self.iface.mapCanvas().unsetMapTool(self.line_selection_tool)
        del self.line_selection_tool
        
        layer = self.iface.activeLayer()
        if not layer or not layer.isEditable():
            return
        
        # Obtener la geometría de la línea destino
        linea_destino = linea_destino_feat.geometry()
        if not linea_destino or linea_destino.type() != QgsWkbTypes.LineGeometry:
            self.iface.messageBar().pushWarning(
                "Red de Riego",
                "La línea destino seleccionada no es válida."
            )
            return
        
        # Informar al usuario qué línea se ha seleccionado como destino
        self.iface.messageBar().pushInfo(
            "Red de Riego",
            f"Extendiendo líneas hasta la línea con ID: {linea_destino_feat.id()}"
        )
        
        # Procesar cada línea a extender
        contador = 0
        for feat in lineas_a_extender:
            # Saltamos si la línea a extender es la misma que la línea destino
            if feat.id() == linea_destino_feat.id():
                continue
            
            # Obtener la geometría de la línea a extender
            geom = feat.geometry()
            if geom.type() != QgsWkbTypes.LineGeometry:
                continue
            
            # Obtener los puntos de la línea
            line_points = geom.asPolyline()
            if len(line_points) < 2:
                continue
            
            # Determinar el punto final (que vamos a extender)
            start_point = QgsPointXY(line_points[0])
            end_point = QgsPointXY(line_points[-1])
            
            # Calcular el vector de dirección de la línea
            dx = end_point.x() - start_point.x()
            dy = end_point.y() - start_point.y()
            
            # Normalizar el vector
            length = (dx**2 + dy**2)**0.5
            if length > 0:
                dx /= length
                dy /= length
            else:
                continue  # Línea demasiado corta
            
            # Extender la línea en la dirección calculada
            extension_factor = 10000  # Una distancia muy grande
            extended_end_x = end_point.x() + dx * extension_factor
            extended_end_y = end_point.y() + dy * extension_factor
            extended_end_point = QgsPointXY(extended_end_x, extended_end_y)
            
            # Crear una línea temporal extendida
            extended_line_points = list(line_points)
            extended_line_points[-1] = extended_end_point
            extended_geometry = QgsGeometry.fromPolylineXY(extended_line_points)
            
            # Calcular la intersección con la línea destino
            intersection = extended_geometry.intersection(linea_destino)
            
            # Si hay intersección y es un punto
            if not intersection.isEmpty() and intersection.type() == QgsWkbTypes.PointGeometry:
                # Si hay múltiples intersecciones, tomar el más cercano al punto final original
                if intersection.isMultipart():
                    intersection_points = intersection.asMultiPoint()
                    
                    # Encontrar el punto más cercano
                    min_distance = float('inf')
                    closest_point = None
                    for point in intersection_points:
                        distance = ((point.x() - end_point.x())**2 + (point.y() - end_point.y())**2)**0.5
                        if distance < min_distance:
                            min_distance = distance
                            closest_point = point
                    
                    if closest_point:
                        intersection_point = closest_point
                    else:
                        continue
                else:
                    intersection_point = intersection.asPoint()
                
                # Crear la nueva geometría extendida
                new_line_points = list(line_points)
                new_line_points[-1] = intersection_point
                new_geometry = QgsGeometry.fromPolylineXY(new_line_points)
                
                # Actualizar la geometría
                layer.changeGeometry(feat.id(), new_geometry)
                
                # Actualizar atributo de longitud si existe
                if "L" in feat.fields().names():
                    field_idx = feat.fieldNameIndex("L")
                    new_length = new_geometry.length()
                    layer.changeAttributeValue(feat.id(), field_idx, round(new_length, 2))
                
                contador += 1
        
        # Forzar actualización visual
        layer.triggerRepaint()
        
        # Informar al usuario
        if contador > 0:
            self.iface.messageBar().pushInfo(
                "Red de Riego",
                f"Se extendieron {contador} línea(s) hasta la línea destino."
            )
        else:
            self.iface.messageBar().pushInfo(
                "Red de Riego",
                "No se pudo extender ninguna línea. Verifique que las líneas sean extendibles hasta la línea destino."
            )

    def crear_tabla_resumen(self):
        """Crea una tabla resumen de longitudes por tipo y diámetro nominal"""
        # Buscar la capa "Red de riego"
        red_layer = None
        for layer in QgsProject.instance().mapLayers().values():
            if layer.name() == "Red de riego" and layer.geometryType() == QgsWkbTypes.LineGeometry:
                red_layer = layer
                break
        
        if not red_layer:
            self.iface.messageBar().pushWarning(
                "Red de Riego",
                "No se encontró la capa 'Red de riego'. Por favor, verifique que existe una capa con este nombre."
            )
            return
        
        # Obtener o crear el grupo "Tablas"
        root = QgsProject.instance().layerTreeRoot()
        tablas_group = root.findGroup("Tablas")
        
        if not tablas_group:
            tablas_group = root.addGroup("Tablas")
        
        # Estructura para almacenar los resultados agrupados
        resultados = {}  # Clave: (Tipo, DN), Valor: Longitud total
        
        # Recorrer las características de la capa y agrupar por Tipo y DN
        for feature in red_layer.getFeatures():
            try:
                tipo = feature["Tipo"]
                dn = feature["DN"]
                longitud = feature["L"]
                
                # Asegurarse de que los valores son válidos
                if tipo and dn is not None and longitud:
                    clave = (tipo, dn)
                    if clave not in resultados:
                        resultados[clave] = 0
                    resultados[clave] += longitud
            except (KeyError, TypeError):
                # Ignorar características que no tienen los atributos requeridos
                continue
        
        # Verificar si hay resultados para procesar
        if not resultados:
            self.iface.messageBar().pushWarning(
                "Red de Riego",
                "No se encontraron datos válidos para generar la tabla resumen."
            )
            return
        
        # Crear una capa de memoria para la tabla resumen
        vl = QgsVectorLayer("NoGeometry", "resumen_longitud", "memory")
        pr = vl.dataProvider()
        
        # Agregar campos a la capa
        pr.addAttributes([
            QgsField("Tipo", QMetaType.Type.QString),
            QgsField("DN", QMetaType.Type.Int),
            QgsField("L", QMetaType.Type.Double)
        ])
        vl.updateFields()
        
        # Añadir características a la capa
        features = []
        for (tipo, dn), longitud in resultados.items():
            f = QgsFeature()
            f.setAttributes([tipo, dn, round(longitud, 2)])
            features.append(f)
        
        pr.addFeatures(features)
        vl.updateExtents()
        
        # Configurar estilo de la tabla para una mejor visualización
        # (Los campos numéricos se alinean a la derecha, el texto a la izquierda)
        
        # Buscar si ya existe una capa con el mismo nombre y eliminarla
        for child in tablas_group.children():
            if child.name() == "resumen_longitud":
                # Eliminar la capa existente
                QgsProject.instance().removeMapLayer(child.layerId())
                break
        
        # Añadir la capa al proyecto dentro del grupo "Tablas"
        QgsProject.instance().addMapLayer(vl, False)
        tablas_group.addLayer(vl)
        
        # Configurar el estilo de la tabla
        vl.setCustomProperty("QFieldSync/checked", "Qt::Checked")  # Para compatibilidad con QField
        vl.setCustomProperty("QFieldSync/action", "copy")
        
        # Informar al usuario
        self.iface.messageBar().pushSuccess(
            "Red de Riego",
            "Se ha creado correctamente la tabla resumen de longitudes por tipo y diámetro."
        )
        
        # Abrir la tabla para mostrarla al usuario
        self.iface.showAttributeTable(vl)