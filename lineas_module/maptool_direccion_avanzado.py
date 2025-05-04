from qgis.gui import QgsMapTool, QgsRubberBand, QgsMapCanvasSnappingUtils
from qgis.core import (
    QgsGeometry, QgsWkbTypes, QgsPointXY, QgsProject, 
    QgsSnappingConfig, QgsTolerance, QgsPoint
)
from PyQt5.QtGui import QColor
from PyQt5.QtCore import Qt

class MapToolDireccionAvanzado(QgsMapTool):
    def __init__(self, iface, panel_ref):
        super().__init__(iface.mapCanvas())
        self.canvas = iface.mapCanvas()
        self.panel = panel_ref
        self.points = []
        self.iface = iface
        
        # Configurar banda de goma para la línea final
        self.rb = QgsRubberBand(self.canvas, QgsWkbTypes.LineGeometry)
        self.rb.setColor(QColor(255, 0, 0))
        self.rb.setWidth(2)
        
        # Configurar banda de goma para la línea temporal durante el dibujo
        self.temp_rb = QgsRubberBand(self.canvas, QgsWkbTypes.LineGeometry)
        self.temp_rb.setColor(QColor(255, 0, 0, 128))  # Semitransparente
        self.temp_rb.setWidth(1)
        self.temp_rb.setLineStyle(Qt.DashLine)
        
        # Marcador para mostrar punto potencial de snap durante el movimiento
        self.snap_marker = QgsRubberBand(self.canvas, QgsWkbTypes.PointGeometry)
        self.snap_marker.setColor(QColor(0, 255, 0))
        self.snap_marker.setWidth(3)
        self.snap_marker.setIcon(QgsRubberBand.ICON_CIRCLE)
        self.snap_marker.setIconSize(15)
        
        # Configurar snapping
        self.snapper = QgsMapCanvasSnappingUtils(self.canvas)
        self.snapper.setConfig(QgsProject.instance().snappingConfig())

    def activate(self):
        super().activate()
        self.reset()
        self.canvas.setToolTip("Haga clic para colocar el primer punto de la línea de dirección")
        
        # Activar el snapping al activar la herramienta
        snapping_config = QgsProject.instance().snappingConfig()
        snapping_config.setEnabled(True)
        QgsProject.instance().setSnappingConfig(snapping_config)

    def deactivate(self):
        self.reset()
        self.snap_marker.reset(QgsWkbTypes.PointGeometry)
        super().deactivate()

    def reset(self):
        """Limpia todos los elementos gráficos y reinicia el estado"""
        self.points = []
        if hasattr(self, 'rb') and self.rb:
            self.rb.reset(QgsWkbTypes.LineGeometry)
        if hasattr(self, 'temp_rb') and self.temp_rb:
            self.temp_rb.reset(QgsWkbTypes.LineGeometry)
        if hasattr(self, 'snap_marker') and self.snap_marker:
            self.snap_marker.reset(QgsWkbTypes.PointGeometry)

    def canvasMoveEvent(self, event):
        # Mostrar posible punto de snap
        snapped_point = self.snapPoint(event.pos())
        
        # Actualizar marcador de snap
        self.snap_marker.reset(QgsWkbTypes.PointGeometry)
        self.snap_marker.addPoint(snapped_point)
        
        # Si ya tenemos el primer punto, mostrar línea temporal
        if len(self.points) == 1:
            self.temp_rb.reset(QgsWkbTypes.LineGeometry)
            self.temp_rb.addPoint(self.points[0])
            self.temp_rb.addPoint(snapped_point)

    def canvasReleaseEvent(self, event):
        # Solo procesar clics con el botón izquierdo
        if event.button() != Qt.LeftButton:
            return
            
        # Obtener punto con snapping
        map_point = self.snapPoint(event.pos())
        
        # Añadir el punto a nuestra lista
        self.points.append(map_point)

        if len(self.points) == 1:
            # Primer punto capturado
            self.rb.addPoint(map_point)
            self.canvas.setToolTip("Haga clic para colocar el segundo punto y definir la dirección")
        elif len(self.points) == 2:
            # Segundo punto - completar la línea
            self.rb.addPoint(map_point)
            
            # Crear geometría de línea
            geom = QgsGeometry.fromPolylineXY([QgsPointXY(p) for p in self.points])
            
            # Verificar que la línea sea válida (longitud > 0)
            if geom.length() > 0:
                self.panel.set_linea_direccion(geom)
            else:
                # Informar al usuario si los puntos son idénticos
                self.panel.iface.messageBar().pushWarning(
                    "Error", "Los puntos seleccionados son idénticos. Inténtelo de nuevo."
                )
                self.reset()
                return
                
            # Limpiar
            self.temp_rb.reset(QgsWkbTypes.LineGeometry)
            self.rb.reset(QgsWkbTypes.LineGeometry)
            self.snap_marker.reset(QgsWkbTypes.PointGeometry)
            self.canvas.unsetMapTool(self)

    def snapPoint(self, point):
        """Aplica snapping a un punto y devuelve el punto ajustado"""
        # Actualizar la configuración del snapper con la configuración actual del proyecto
        self.snapper.setConfig(QgsProject.instance().snappingConfig())
        
        # Obtener resultados de snapping
        match = self.snapper.snapToMap(point)
        
        # Si hay un snap válido, usar ese punto
        if match.isValid():
            return match.point()
        else:
            # Si no hay snap, usar el punto original
            return self.toMapCoordinates(point)

    def keyPressEvent(self, event):
        # Cancelar operación con tecla Escape
        if event.key() == Qt.Key_Escape:
            self.reset()
            self.snap_marker.reset(QgsWkbTypes.PointGeometry)
            self.canvas.unsetMapTool(self)
            event.accept()
        else:
            super().keyPressEvent(event)