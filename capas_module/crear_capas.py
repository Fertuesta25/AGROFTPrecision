"""
Plugin principal para la creación y filtrado de capas de riego
(Compatible con QGIS 3.x/Qt5 y QGIS 4.x/Qt6)
"""
import os
from qgis.PyQt.QtWidgets import QAction, QMessageBox, QFileDialog, QCheckBox, QDialog, QVBoxLayout, QPushButton
from qgis.PyQt.QtGui import QIcon
from qgis.core import (
    QgsProject,
    QgsVectorLayer,
    QgsField,
    QgsRectangle,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsRasterLayer,
    QgsLayerTreeGroup
)
from qgis.PyQt.QtCore import QVariant, QMetaType
from qgis.gui import QgsProjectionSelectionDialog
import processing
from qgis.core import QgsProcessingFeedback

class CrearCapasRiego:
    def __init__(self, iface):
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)  # Carpeta principal del plugin
        
    def unload(self):
        self.iface.removeToolBarIcon(self.action)
        self.iface.removePluginMenu('Crear Capas de Riego', self.action)
        
    def crear_capas(self):
        # Mostrar un diálogo para elegir el CRS y opción de GeoPackage
        dialog = QDialog(self.iface.mainWindow())
        dialog.setWindowTitle('Opciones de Creación de Capas')
        layout = QVBoxLayout()
        
        # Añadir CheckBox para guardar en GeoPackage
        save_gpkg_checkbox = QCheckBox("Guardar capas en GeoPackage")
        save_gpkg_checkbox.setChecked(False)
        layout.addWidget(save_gpkg_checkbox)
        
        # Botón para continuar
        btn_continue = QPushButton("Continuar")
        layout.addWidget(btn_continue)
        
        dialog.setLayout(layout)
        
        # Variable para guardar la elección del usuario
        save_to_gpkg = [False]  # Usando lista para poder modificar desde la función anidada
        
        # Conectar el botón para cerrar el diálogo
        def on_continue():
            save_to_gpkg[0] = save_gpkg_checkbox.isChecked()
            dialog.accept()
            
        btn_continue.clicked.connect(on_continue)
        
        # Mostrar el diálogo (Actualizado a exec() para Qt6)
        if not dialog.exec():
            return
            
        # Mostrar diálogo para elegir el CRS
        crs_dialog = QgsProjectionSelectionDialog()
        crs_dialog.setWindowTitle('Seleccionar CRS para las capas')
        
        # Actualizado a exec() para Qt6
        if crs_dialog.exec():
            crs = crs_dialog.crs().authid()
        else:
            QMessageBox.warning(self.iface.mainWindow(), "Crear Capas de Riego", "No se seleccionó un CRS.")
            return
        
        # Si el usuario eligió guardar en GeoPackage, solicitamos la ubicación
        gpkg_path = None
        if save_to_gpkg[0]:
            gpkg_path, _ = QFileDialog.getSaveFileName(self.iface.mainWindow(), 
                                                      "Guardar GeoPackage", 
                                                      "", 
                                                      "GeoPackage (*.gpkg)")
            if not gpkg_path:
                QMessageBox.warning(self.iface.mainWindow(), "Crear Capas de Riego", 
                                    "No se seleccionó una ubicación para el GeoPackage. Se crearán capas en memoria.")
                save_to_gpkg[0] = False
        
        # Crear capas en memoria
        layer_info = [
            {
                'name': 'Red de riego',
                'geom_type': 'LineString',
                'attributes': [
                    QgsField("id", QMetaType.Type.Int),
                    QgsField('Tipo', QMetaType.Type.QString),
                    QgsField('DN', QMetaType.Type.Int),
                    QgsField('Di', QMetaType.Type.Int),
                    QgsField('L', QMetaType.Type.Double),
                    QgsField('Sector', QMetaType.Type.Int),
                    QgsField('Material', QMetaType.Type.QString),
                    QgsField('Tipo_riego', QMetaType.Type.QString),
                    QgsField('D_emisor', QMetaType.Type.Double),
                    QgsField('Q_emisor', QMetaType.Type.Double),
                    QgsField('Q_total', QMetaType.Type.Double),
                ],
                'style': 'red_de_riego.qml'
            },
            {
                'name': 'Accesorios',
                'geom_type': 'Point',
                'attributes': [
                    QgsField('Nombre', QMetaType.Type.QString),
                    QgsField('Tipo', QMetaType.Type.QString),
                ],
                'style': 'accesorios.qml'
            },
            {
                'name': 'Sectores',
                'geom_type': 'Polygon',
                'attributes': [
                    QgsField('N', QMetaType.Type.Int),
                    QgsField('Area', QMetaType.Type.Double),
                    QgsField('Perimetro', QMetaType.Type.Double),
                    QgsField('L_lateral', QMetaType.Type.Double),
                    QgsField('Q_total', QMetaType.Type.Double),
                ],
                'style': 'sectores.qml'
            },
            {
                'name': 'Cotas',
                'geom_type': 'LineString',
                'attributes': [
                    QgsField('Lado', QMetaType.Type.QString, '', 20),
                ],
                'style': 'cotas.qml'
            }
        ]
        
        # Crear el grupo "Proyecto de Riego"
        root = QgsProject.instance().layerTreeRoot()
        proyecto_riego_group = root.addGroup("Proyecto de Riego")
        
        # Crear las capas en memoria
        memory_layers = []
        
        for info in layer_info:
            # Crear capa
            layer = QgsVectorLayer(
                f"{info['geom_type']}?crs={crs}", 
                info['name'], 
                'memory'
            )
            
            # Añadir atributos
            provider = layer.dataProvider()
            provider.addAttributes(info['attributes'])
            layer.updateFields()
            
            # Aplicar estilo
            style_path = os.path.join(self.plugin_dir, 'styles', info['style'])
            if os.path.exists(style_path):
                layer.loadNamedStyle(style_path)
                layer.triggerRepaint()
            
            # Añadir al proyecto dentro del grupo
            QgsProject.instance().addMapLayer(layer, False)  # False para no añadirlo a la raíz
            proyecto_riego_group.addLayer(layer)  # Añadir al grupo
            memory_layers.append(layer)
        
        # Si se eligió guardar en GeoPackage
        if save_to_gpkg[0]:
            try:
                # En QGIS 3.42 podemos usar directamente el algoritmo package
                parameters = {
                    'LAYERS': memory_layers,
                    'OUTPUT': gpkg_path,
                    'OVERWRITE': True,
                    'SAVE_STYLES': True
                }
                
                feedback = QgsProcessingFeedback()
                
                # Ejecutar el algoritmo Package Layers
                result = processing.run("native:package", parameters, feedback=feedback)
                
                if result:
                    # Quitar las capas de memoria
                    for layer in memory_layers:
                        QgsProject.instance().removeMapLayer(layer.id())
                    
                    # Crear el grupo nuevamente (ya que se eliminaron las capas anteriores)
                    root = QgsProject.instance().layerTreeRoot()
                    # Verificar si el grupo ya existe (en caso de que no se haya eliminado)
                    if not root.findGroup("Proyecto de Riego"):
                        proyecto_riego_group = root.addGroup("Proyecto de Riego")
                    else:
                        proyecto_riego_group = root.findGroup("Proyecto de Riego")
                    
                    # Cargar las capas desde el GeoPackage
                    for info in layer_info:
                        layer_name = info['name']
                        uri = f"{gpkg_path}|layername={layer_name}"
                        new_layer = QgsVectorLayer(uri, layer_name, 'ogr')
                        
                        if new_layer.isValid():
                            # Añadir al proyecto dentro del grupo
                            QgsProject.instance().addMapLayer(new_layer, False)
                            proyecto_riego_group.addLayer(new_layer)
                        else:
                            QMessageBox.warning(self.iface.mainWindow(), "Error", 
                                               f"No se pudo cargar la capa {layer_name} desde el GeoPackage.")
                else:
                    QMessageBox.warning(self.iface.mainWindow(), "Error", 
                                       "No se pudo guardar en GeoPackage. Se usarán las capas en memoria.")
            except Exception as e:
                QMessageBox.warning(self.iface.mainWindow(), "Error", 
                                   f"Error al guardar en GeoPackage: {str(e)}")
        
        # Hacer zoom a la extensión de Perú
        self.zoom_a_peru()
        
    
    def zoom_a_peru(self):
        """Hace zoom a la extensión del Perú"""
        # Coordenadas aproximadas de Perú en lat/lon (EPSG:4326)
        peru_extent = QgsRectangle(-79.2, -9.6, -74.1, -4.9)
        

        # Obtener el sistema de referencia de coordenadas del lienzo
        canvas = self.iface.mapCanvas()
        canvas_crs = canvas.mapSettings().destinationCrs()
        
        # Crear el sistema de referencia WGS84
        wgs84 = QgsCoordinateReferenceSystem('EPSG:4326')
        
        # Crear transformación de coordenadas
        transform = QgsCoordinateTransform(wgs84, canvas_crs, QgsProject.instance())
        
        # Transformar el extent de Perú al CRS del lienzo
        try:
            peru_extent_transformed = transform.transformBoundingBox(peru_extent)
            # Hacer zoom a la extensión transformada
            canvas.setExtent(peru_extent_transformed)
            canvas.refresh()
        except Exception as e:
            QMessageBox.warning(self.iface.mainWindow(), "Error de Zoom", 
                                f"No se pudo hacer zoom a Perú: {str(e)}")