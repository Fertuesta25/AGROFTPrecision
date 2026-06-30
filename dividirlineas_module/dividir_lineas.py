# dividirlineas_module/dividir_lineas.py

from qgis.PyQt.QtWidgets import QDialog, QVBoxLayout, QComboBox, QLabel, QPushButton, QMessageBox, QDoubleSpinBox, QHBoxLayout, QCheckBox
from qgis.PyQt.QtCore import Qt, QVariant, QTimer, QMetaType
from qgis.core import (QgsProject, QgsFeature, QgsGeometry, QgsField,
                     QgsVectorLayer, QgsFeatureRequest, QgsPointXY,
                     QgsProcessingFeatureSourceDefinition, QgsWkbTypes,
                     QgsEditError, QgsMapLayer)
import processing

class DividirLineasDialog(QDialog):
    def __init__(self, iface):
        super().__init__(iface.mainWindow())
        self.iface = iface
        self.setWindowTitle("Dividir Líneas con Puntos")
        self.resize(400, 250)
        self.setup_ui()
        
        # Conectar señales para actualizar capas
        self.registry = QgsProject.instance()
        self.registry.layersAdded.connect(self.cargar_capas)
        self.registry.layersRemoved.connect(self.cargar_capas)
        
        # Conectar la señal de cambio de selección
        try:
            self.iface.currentLayerChanged.connect(self.verificar_seleccion)
            self.iface.mapCanvas().selectionChanged.connect(self.verificar_seleccion)
        except:
            pass
        
    def closeEvent(self, event):
        """Evento que se ejecuta al cerrar el diálogo"""
        # Desconectar señales para evitar fugas de memoria
        try:
            if hasattr(self, 'registry'):
                try:
                    self.registry.layersAdded.disconnect(self.cargar_capas)
                except:
                    pass
                try:
                    self.registry.layersRemoved.disconnect(self.cargar_capas)
                except:
                    pass
        except:
            pass
        
        try:
            capa_actual = getattr(self, '_capa_actual', None)
            if capa_actual and hasattr(capa_actual, 'selectionChanged'):
                try:
                    capa_actual.selectionChanged.disconnect(self.verificar_seleccion)
                except:
                    pass
        except:
            pass
        
        try:
            if hasattr(self, 'iface'):
                try:
                    self.iface.currentLayerChanged.disconnect(self.verificar_seleccion)
                except:
                    pass
                try:
                    self.iface.mapCanvas().selectionChanged.disconnect(self.verificar_seleccion)
                except:
                    pass
        except:
            pass
        
        # No guardamos ninguna configuración al cerrar
        # Simplemente permitimos que el evento de cierre continúe
        try:
            super().closeEvent(event)
        except:
            pass
        
    def setup_ui(self):
        layout = QVBoxLayout()
        
        # Selector de capa de líneas
        layout.addWidget(QLabel("Seleccione la capa de líneas:"))
        self.lineas_combo = QComboBox()
        self.lineas_combo.currentIndexChanged.connect(self.verificar_editable)
        self.lineas_combo.currentIndexChanged.connect(self.cambio_capa_lineas)
        layout.addWidget(self.lineas_combo)
        
        # Opción para procesar solo las líneas seleccionadas
        self.solo_seleccionadas = QCheckBox("Procesar solo las líneas seleccionadas")
        self.solo_seleccionadas.setChecked(False)
        layout.addWidget(self.solo_seleccionadas)
        
        # Selector de capa de puntos
        layout.addWidget(QLabel("Seleccione la capa de puntos:"))
        self.puntos_combo = QComboBox()
        layout.addWidget(self.puntos_combo)
        
        # Tolerancia (cambiado a QDoubleSpinBox para aceptar decimales)
        tolerancia_layout = QHBoxLayout()
        tolerancia_layout.addWidget(QLabel("Tolerancia de búsqueda (metros):"))
        self.tolerancia_spin = QDoubleSpinBox()
        self.tolerancia_spin.setRange(0.1, 100.0)
        self.tolerancia_spin.setDecimals(2)
        self.tolerancia_spin.setSingleStep(0.1)
        self.tolerancia_spin.setValue(0.1)
        tolerancia_layout.addWidget(self.tolerancia_spin)
        layout.addLayout(tolerancia_layout)
        
        # Opción para dividir en vértices e intersecciones (siempre deschequeado al inicio)
        self.dividir_en_vertices = QCheckBox("Dividir también en vértices, intersecciones y extremos")
        self.dividir_en_vertices.setChecked(False)
        layout.addWidget(self.dividir_en_vertices)
        
        # Opción para modificar la capa actual (siempre deschequeado al inicio)
        self.modificar_capa_actual = QCheckBox("Modificar capa actual (en lugar de crear nueva capa)")
        self.modificar_capa_actual.setChecked(False)
        self.modificar_capa_actual.toggled.connect(self.verificar_editable)
        layout.addWidget(self.modificar_capa_actual)
        
        # Botones
        buttons_layout = QHBoxLayout()
        self.ejecutar_btn = QPushButton("Ejecutar División")
        self.ejecutar_btn.clicked.connect(self.dividir_lineas)
        self.cerrar_btn = QPushButton("Cerrar")
        self.cerrar_btn.clicked.connect(self.close)
        
        buttons_layout.addWidget(self.ejecutar_btn)
        buttons_layout.addWidget(self.cerrar_btn)
        layout.addLayout(buttons_layout)
        
        self.setLayout(layout)
        
    def showEvent(self, event):
        """Evento que se ejecuta cuando se muestra el diálogo"""
        # Asegurarse de que la UI está completamente inicializada antes de cargar
        # Usar QTimer para retrasar ligeramente la carga de capas
        from qgis.PyQt.QtCore import QTimer
        QTimer.singleShot(100, self.inicializar_contenido)
        super().showEvent(event)
        
    def verificar_seleccion(self):
        """Verifica si hay elementos seleccionados en la capa de líneas"""
        capa = self.lineas_combo.currentData()
        
        # Si no hay capa seleccionada o no es una capa vectorial, desactivar checkbox
        if not capa or not isinstance(capa, QgsVectorLayer):
            self.solo_seleccionadas.setEnabled(False)
            self.solo_seleccionadas.setChecked(False)
            self.solo_seleccionadas.setToolTip("No hay capa de líneas seleccionada")
            return
            
        # Verificar si hay elementos seleccionados
        seleccion_count = capa.selectedFeatureCount()
        
        # Actualizar estado del checkbox
        if seleccion_count == 0:
            # Cuando no hay elementos seleccionados
            self.solo_seleccionadas.setEnabled(False)
            self.solo_seleccionadas.setChecked(False)
            self.solo_seleccionadas.setToolTip("No hay líneas seleccionadas en la capa actual")
        else:
            # Cuando hay elementos seleccionados
            self.solo_seleccionadas.setEnabled(True)
            self.solo_seleccionadas.setChecked(True)  # Marcamos automáticamente
            self.solo_seleccionadas.setToolTip(f"Hay {seleccion_count} líneas seleccionadas")
        
    def verificar_editable(self):
        """Verifica si la capa seleccionada es editable y actualiza el estado del checkbox"""
        if self.modificar_capa_actual.isChecked():
            capa = self.lineas_combo.currentData()
            if capa and isinstance(capa, QgsVectorLayer):
                if not capa.isEditable():
                    # No mostrar diálogo, activar edición automáticamente
                    capa.startEditing()
        
        # Verificar si hay capas disponibles
        self.ejecutar_btn.setEnabled(self.lineas_combo.count() > 0 and self.puntos_combo.count() > 0)
            
        # Verificar también si hay selección
        self.verificar_seleccion()
        
    def cargar_capas(self):
        """Carga las capas disponibles en los combobox"""
        # Guardar selecciones actuales por ID
        linea_layer_id = None
        punto_layer_id = None
        
        # Verificar que los combos existen antes de usarlos
        if not hasattr(self, 'lineas_combo') or not hasattr(self, 'puntos_combo'):
            return
        
        try:
            if self.lineas_combo and self.lineas_combo.currentData():
                linea_layer_id = self.lineas_combo.currentData().id()
        except:
            linea_layer_id = None
            
        try:
            if self.puntos_combo and self.puntos_combo.currentData():
                punto_layer_id = self.puntos_combo.currentData().id()
        except:
            punto_layer_id = None
        
        # Limpiar combobox
        try:
            self.lineas_combo.blockSignals(True)
            self.puntos_combo.blockSignals(True)
            
            self.lineas_combo.clear()
            self.puntos_combo.clear()
        except:
            return  # Si no podemos hacer esto, mejor salir
        
        # Índices para restaurar selección
        idx_linea = -1
        idx_punto = -1
        
        # Contador de capas
        i_lineas = 0
        i_puntos = 0
        
        try:
            # Cargar las capas disponibles
            for layer in QgsProject.instance().mapLayers().values():
                if layer and layer.isValid() and layer.type() == QgsMapLayer.VectorLayer:
                    if layer.geometryType() == QgsWkbTypes.LineGeometry:
                        self.lineas_combo.addItem(layer.name(), layer)
                        # Si es la capa que estaba seleccionada, guardar el índice
                        if linea_layer_id and layer.id() == linea_layer_id:
                            idx_linea = i_lineas
                        i_lineas += 1
                    elif layer.geometryType() == QgsWkbTypes.PointGeometry:
                        self.puntos_combo.addItem(layer.name(), layer)
                        # Si es la capa que estaba seleccionada, guardar el índice
                        if punto_layer_id and layer.id() == punto_layer_id:
                            idx_punto = i_puntos
                        i_puntos += 1
        except:
            pass
        
        try:
            # Restaurar selecciones previas si es posible
            if idx_linea >= 0 and idx_linea < self.lineas_combo.count():
                self.lineas_combo.setCurrentIndex(idx_linea)
            if idx_punto >= 0 and idx_punto < self.puntos_combo.count():
                self.puntos_combo.setCurrentIndex(idx_punto)
            
            self.lineas_combo.blockSignals(False)
            self.puntos_combo.blockSignals(False)
                
            # Verificar si la capa es editable y si hay selección
            self.verificar_editable()
            self.verificar_seleccion()
        except:
            pass
    
    def dividir_lineas(self):
        # Obtener capas seleccionadas
        linea_layer = self.lineas_combo.currentData()
        punto_layer = self.puntos_combo.currentData()
        
        if not linea_layer or not punto_layer:
            QMessageBox.warning(self, "Error", "Debe seleccionar una capa de líneas y una de puntos.")
            return
            
        # Obtener tolerancia
        tolerancia = self.tolerancia_spin.value()
        
        # Verificar si se modificará la capa actual
        modificar_capa_actual = self.modificar_capa_actual.isChecked()
        
        # Verificar si solo se procesarán las líneas seleccionadas
        solo_seleccionadas = self.solo_seleccionadas.isChecked()
        
        # Verificar si se debe dividir en vértices e intersecciones
        dividir_en_vertices = self.dividir_en_vertices.isChecked()
        
        # Control de edición interno
        edicion_activada = False
        
        # Si se va a modificar la capa actual, verificar que esté en modo edición
        if modificar_capa_actual and not linea_layer.isEditable():
            # Activar la edición automáticamente sin preguntar
            exito = linea_layer.startEditing()
            if exito:
                edicion_activada = True
            else:
                QMessageBox.warning(self, "Error", "No se pudo activar la edición de la capa.")
                return
        
        try:
            # Crear capa de resultado si es necesario
            result_layer = linea_layer if modificar_capa_actual else self.crear_capa_resultado(linea_layer)
            
            # Contador de divisiones realizadas
            divisiones = 0
            
            # Lista para almacenar los IDs de las líneas originales que se eliminarán
            ids_a_eliminar = []
            
            # Lista para almacenar nuevas características si se modifica la capa actual
            nuevas_features = []
            
            # Obtener características a procesar (todas o solo seleccionadas)
            if solo_seleccionadas:
                features_a_procesar = list(linea_layer.selectedFeatures())
                if not features_a_procesar:
                    QMessageBox.warning(self, "Advertencia", "No hay líneas seleccionadas en la capa.")
                    return
            else:
                features_a_procesar = list(linea_layer.getFeatures())
            
            # Lista para almacenar todos los puntos (puntos de la capa, vértices, intersecciones)
            todos_los_puntos = []
            
            # 1. Recolectar puntos de la capa de puntos
            for punto_feature in punto_layer.getFeatures():
                todos_los_puntos.append(punto_feature.geometry())
            
            # 2. Si se solicita, añadir vértices, intersecciones y puntos de contacto
            if dividir_en_vertices:
                # Añadir vértices de todas las líneas (excepto los extremos)
                for feature in features_a_procesar:
                    geom = feature.geometry()
                    if geom.isMultipart():
                        partes = geom.asMultiPolyline()
                        for parte in partes:
                            # Añadir vértices intermedios (no extremos)
                            for i in range(1, len(parte) - 1):
                                punto = QgsGeometry.fromPointXY(parte[i])
                                todos_los_puntos.append(punto)
                    else:
                        linea = geom.asPolyline()
                        # Añadir vértices intermedios (no extremos)
                        for i in range(1, len(linea) - 1):
                            punto = QgsGeometry.fromPointXY(linea[i])
                            todos_los_puntos.append(punto)
                
                # Encontrar todas las intersecciones
                for i in range(len(features_a_procesar)):
                    for j in range(i + 1, len(features_a_procesar)):
                        geom1 = features_a_procesar[i].geometry()
                        geom2 = features_a_procesar[j].geometry()
                        
                        if geom1.intersects(geom2):
                            intersection = geom1.intersection(geom2)
                            if not intersection.isEmpty():
                                # Añadir punto(s) de intersección
                                if intersection.type() == QgsWkbTypes.PointGeometry:
                                    todos_los_puntos.append(intersection)
                                elif intersection.isMultipart():
                                    multi_point = intersection.asMultiPoint()
                                    for punto in multi_point:
                                        punto_geom = QgsGeometry.fromPointXY(punto)
                                        todos_los_puntos.append(punto_geom)
                
                # Encontrar puntos donde las líneas se tocan
                puntos_contacto = self.encontrar_puntos_contacto(features_a_procesar)
                for punto_geom in puntos_contacto:
                    todos_los_puntos.append(punto_geom)
            
            # Procesar cada línea
            for linea_feature in features_a_procesar:
                linea_geom = linea_feature.geometry()
                
                # Lista de puntos para dividir esta línea específica
                puntos_division = []
                
                # Verificar cada punto recolectado
                for punto_geom in todos_los_puntos:
                    # Encontrar el punto más cercano en la línea
                    nearest_point = linea_geom.nearestPoint(punto_geom)
                    distancia = punto_geom.distance(nearest_point)
                    
                    # Si está cerca de la línea, usarlo como punto de división
                    if distancia <= tolerancia:
                        # Para puntos que no están exactamente en la línea, usar el punto más cercano
                        punto_a_usar = nearest_point
                        
                        # Calcular distancia a lo largo de la línea
                        distancia_linea = linea_geom.lineLocatePoint(punto_a_usar)
                        
                        # Añadir a la lista de puntos de división
                        puntos_division.append({
                            'punto': punto_a_usar,
                            'distancia': distancia_linea
                        })
                
                # Eliminar duplicados
                puntos_unicos = []
                for p in puntos_division:
                    es_duplicado = False
                    for p_unico in puntos_unicos:
                        if p['punto'].distance(p_unico['punto']) < 0.0001:
                            es_duplicado = True
                            break
                    if not es_duplicado:
                        puntos_unicos.append(p)
                
                # Ordenar los puntos por distancia a lo largo de la línea
                puntos_unicos.sort(key=lambda x: x['distancia'])
                
                # Si no hay puntos de división y no estamos modificando la capa actual,
                # copiar la línea original
                if not puntos_unicos:
                    if not modificar_capa_actual:
                        nueva_feature = QgsFeature(result_layer.fields())
                        for i in range(linea_feature.fields().count()):
                            nueva_feature.setAttribute(i, linea_feature.attribute(i))
                        nueva_feature.setGeometry(linea_geom)
                        result_layer.addFeature(nueva_feature)
                    continue
                
                # Si estamos modificando la capa actual, añadir el ID para eliminar después
                if modificar_capa_actual:
                    ids_a_eliminar.append(linea_feature.id())
                
                # Dividir la línea usando los puntos
                if linea_geom.isMultipart():
                    partes = linea_geom.asMultiPolyline()
                    for parte in partes:
                        nuevos_segmentos = self.dividir_parte_linea(parte, puntos_unicos)
                        for segmento in nuevos_segmentos:
                            nueva_feature = QgsFeature(result_layer.fields())
                            for i in range(linea_feature.fields().count()):
                                nueva_feature.setAttribute(i, linea_feature.attribute(i))
                            nueva_feature.setGeometry(segmento)
                            
                            if modificar_capa_actual:
                                nuevas_features.append(nueva_feature)
                            else:
                                result_layer.addFeature(nueva_feature)
                            
                            divisiones += 1
                else:
                    linea = linea_geom.asPolyline()
                    nuevos_segmentos = self.dividir_parte_linea(linea, puntos_unicos)
                    for segmento in nuevos_segmentos:
                        nueva_feature = QgsFeature(result_layer.fields())
                        for i in range(linea_feature.fields().count()):
                            nueva_feature.setAttribute(i, linea_feature.attribute(i))
                        nueva_feature.setGeometry(segmento)
                        
                        if modificar_capa_actual:
                            nuevas_features.append(nueva_feature)
                        else:
                            result_layer.addFeature(nueva_feature)
                        
                        divisiones += 1
            
            # Si estamos modificando la capa actual, eliminar las líneas originales y añadir las nuevas
            if modificar_capa_actual and ids_a_eliminar:
                # Eliminar las líneas originales
                linea_layer.deleteFeatures(ids_a_eliminar)
                
                # Añadir las nuevas líneas
                linea_layer.addFeatures(nuevas_features)
                
                # Guardar cambios y desactivar edición SIEMPRE, independientemente de quién activó la edición
                linea_layer.commitChanges()
                
                # Mensaje de éxito
                if solo_seleccionadas:
                    QMessageBox.information(self, "Éxito", f"División completada. Se dividieron {len(ids_a_eliminar)} líneas seleccionadas en {divisiones} segmentos.")
                else:
                    QMessageBox.information(self, "Éxito", f"División completada. Se dividieron {len(ids_a_eliminar)} líneas en {divisiones} segmentos.")
            elif not modificar_capa_actual:
                # Confirmar los cambios y agregar la capa al mapa si es una nueva capa
                result_layer.commitChanges()
                QgsProject.instance().addMapLayer(result_layer)
                
                # Mensaje de éxito
                if solo_seleccionadas:
                    QMessageBox.information(self, "Éxito", f"División completada. Se crearon {divisiones} segmentos a partir de líneas seleccionadas en la nueva capa.")
                else: 
                    QMessageBox.information(self, "Éxito", f"División completada. Se crearon {divisiones} segmentos en la nueva capa.")
            else:
                QMessageBox.information(self, "Información", "No se encontraron líneas para dividir con los parámetros actuales.")
                
        except QgsEditError as e:
            QMessageBox.critical(self, "Error de Edición", f"No se pudo modificar la capa: {str(e)}")
            # Si activamos la edición y hubo un error, cancelar cambios
            if edicion_activada and linea_layer.isEditable():
                linea_layer.rollBack()
        except Exception as e:
            import traceback
            QMessageBox.critical(self, "Error", f"Ocurrió un error durante la división: {str(e)}\n\n{traceback.format_exc()}")
            # Si activamos la edición y hubo un error, cancelar cambios
            if edicion_activada and linea_layer.isEditable():
                linea_layer.rollBack()
    
    def crear_capa_resultado(self, capa_original):
        # Crear una nueva capa para los resultados
        nombre = f"{capa_original.name()}_dividida"
        crs = capa_original.crs().authid()
        
        # Crear la estructura de la capa
        uri = f"LineString?crs={crs}"
        result_layer = QgsVectorLayer(uri, nombre, "memory")
        
        # Configurar los campos
        result_layer.startEditing()
        
        # Copiar los campos de la capa original
        for field in capa_original.fields():
            result_layer.addAttribute(field)
        
        # Usar el método del proveedor para agregar el campo (forma más compatible)
        provider = result_layer.dataProvider()
        provider.addAttributes([QgsField("segment_id", QMetaType.Type.Int)])  # 2 corresponde a Int en QVariant
        result_layer.updateFields()
        
        return result_layer
    
    def dividir_geometria_linea(self, geometria, puntos):
        """Divide una geometría de línea en los puntos especificados"""
        segmentos = []
        
        # Verificar que la geometría sea válida
        if not geometria.isGeosValid():
            geometria = geometria.makeValid()
            if not geometria.isGeosValid():
                return segmentos
        
        # Si no hay puntos, devolver la geometría original
        if not puntos:
            return [geometria]
        
        # Depuración
        print(f"Dividiendo línea con {len(puntos)} puntos")
        for i, p in enumerate(puntos):
            print(f"Punto {i}: distancia={p['distancia']}")
        
        # Convertir a MultiLineString si es necesario
        if geometria.isMultipart():
            partes = geometria.asMultiPolyline()
            # Por simplificar, tomamos solo la primera parte
            linea = partes[0]
        else:
            linea = geometria.asPolyline()
        
        # Añadir los puntos de división
        linea_con_puntos = []
        for i in range(len(linea) - 1):
            linea_con_puntos.append(linea[i])
            
            # Verificar si algún punto está entre estos dos vértices
            segmento_actual = QgsGeometry.fromPolylineXY([linea[i], linea[i+1]])
            
            for punto_info in puntos:
                punto_geom = punto_info['punto']
                
                # Verificar si el punto está en el segmento actual
                if segmento_actual.distance(punto_geom) < 0.0001:  # Pequeña tolerancia
                    # Obtener el punto exacto
                    punto = punto_geom.asPoint()
                    
                    # Verificar que no esté demasiado cerca de un vértice existente
                    if QgsGeometry.fromPointXY(punto).distance(QgsGeometry.fromPointXY(linea[i])) > 0.001 and \
                       QgsGeometry.fromPointXY(punto).distance(QgsGeometry.fromPointXY(linea[i+1])) > 0.001:
                        linea_con_puntos.append(punto)
            
        # Añadir el último punto
        linea_con_puntos.append(linea[-1])
        
        # Depuración
        print(f"Línea original tiene {len(linea)} vértices, línea con puntos tiene {len(linea_con_puntos)} vértices")
        
        # Si no hay cambios, devolver la geometría original
        if len(linea_con_puntos) == len(linea):
            return [geometria]
        
        # Crear segmentos entre vértices consecutivos
        for i in range(len(linea_con_puntos) - 1):
            segmento = QgsGeometry.fromPolylineXY([linea_con_puntos[i], linea_con_puntos[i+1]])
            # Solo añadir si el segmento tiene longitud
            if segmento.length() > 0.0001:
                segmentos.append(segmento)
        
        return segmentos

    def cambio_capa_lineas(self):
        """Se ejecuta cuando cambia la capa de líneas seleccionada"""
        # Desconectar señal de selección de la capa anterior (si existe)
        try:
            capa_anterior = getattr(self, '_capa_actual', None)
            if capa_anterior:
                try:
                    capa_anterior.selectionChanged.disconnect(self.verificar_seleccion)
                except:
                    pass
        except:
            pass
        
        # Obtener la nueva capa seleccionada
        capa_actual = self.lineas_combo.currentData()
        if capa_actual and isinstance(capa_actual, QgsVectorLayer):  # Verificar que sea un QgsVectorLayer
            # Guardar referencia a la capa actual
            self._capa_actual = capa_actual
            
            # Conectar señal de selección de la capa actual
            try:
                capa_actual.selectionChanged.connect(self.verificar_seleccion)
            except:
                pass
        
        # Verificar selección actual
        self.verificar_seleccion()

    def encontrar_intersecciones(self, features):
        """Encuentra los puntos de intersección entre las líneas"""
        puntos_interseccion = []
        
        # Buscar intersecciones entre cada par de líneas
        for i in range(len(features)):
            for j in range(i + 1, len(features)):
                geom1 = features[i].geometry()
                geom2 = features[j].geometry()
                
                # Verificar si se intersectan
                if geom1.intersects(geom2):
                    # Obtener la geometría de la intersección
                    intersection = geom1.intersection(geom2)
                    
                    # Procesar la geometría según su tipo
                    if not intersection.isEmpty():
                        if intersection.type() == QgsWkbTypes.PointGeometry:
                            # Punto único
                            puntos_interseccion.append(intersection)
                        elif intersection.isMultipart():
                            # Múltiples puntos
                            multi_point = intersection.asMultiPoint()
                            for punto in multi_point:
                                punto_geom = QgsGeometry.fromPointXY(punto)
                                puntos_interseccion.append(punto_geom)
        
        return puntos_interseccion

    def encontrar_puntos_contacto(self, features):
        """Encuentra los puntos donde las líneas se tocan sin cruzarse"""
        puntos_contacto = []
        
        # Para cada par de líneas
        for i in range(len(features)):
            for j in range(len(features)):
                if i == j:
                    continue  # No comparar una línea consigo misma
                    
                geom1 = features[i].geometry()
                geom2 = features[j].geometry()
                
                # Extraer puntos extremos de la primera línea
                if geom1.isMultipart():
                    partes = geom1.asMultiPolyline()
                    for parte in partes:
                        # Verificar si los extremos tocan la segunda línea
                        inicio = QgsGeometry.fromPointXY(parte[0])
                        fin = QgsGeometry.fromPointXY(parte[-1])
                        
                        # Si el extremo está cerca de la segunda línea
                        if geom2.distance(inicio) < 0.001:
                            # Encontrar el punto exacto en la segunda línea
                            punto_cercano = geom2.nearestPoint(inicio)
                            puntos_contacto.append(punto_cercano)
                        
                        if geom2.distance(fin) < 0.001:
                            # Encontrar el punto exacto en la segunda línea
                            punto_cercano = geom2.nearestPoint(fin)
                            puntos_contacto.append(punto_cercano)
                else:
                    linea = geom1.asPolyline()
                    # Verificar si los extremos tocan la segunda línea
                    inicio = QgsGeometry.fromPointXY(linea[0])
                    fin = QgsGeometry.fromPointXY(linea[-1])
                    
                    # Si el extremo está cerca de la segunda línea
                    if geom2.distance(inicio) < 0.001:
                        # Encontrar el punto exacto en la segunda línea
                        punto_cercano = geom2.nearestPoint(inicio)
                        puntos_contacto.append(punto_cercano)
                    
                    if geom2.distance(fin) < 0.001:
                        # Encontrar el punto exacto en la segunda línea
                        punto_cercano = geom2.nearestPoint(fin)
                        puntos_contacto.append(punto_cercano)
        
        return puntos_contacto

    def dividir_parte_linea(self, linea, puntos_division):
        """
        Divide una parte de línea usando puntos de división
        
        Args:
            linea: Lista de QgsPointXY que forman la línea
            puntos_division: Lista de diccionarios con 'punto' y 'distancia'
            
        Returns:
            Lista de geometrías (segmentos de línea)
        """
        resultados = []
        
        # Si no hay puntos, devolver la línea original
        if not puntos_division:
            return [QgsGeometry.fromPolylineXY(linea)]
        
        # Crear una nueva línea con todos los puntos (originales + división)
        nueva_linea = []
        
        # Añadir el primer punto de la línea original
        nueva_linea.append(linea[0])
        
        # Para cada segmento de la línea original
        for i in range(len(linea) - 1):
            # Obtener los puntos que pertenecen a este segmento
            segmento_actual = QgsGeometry.fromPolylineXY([linea[i], linea[i+1]])
            puntos_en_segmento = []
            
            for punto_info in puntos_division:
                punto_geom = punto_info['punto']
                # Si el punto está en este segmento (con tolerancia)
                if segmento_actual.distance(punto_geom) < 0.0001:
                    puntos_en_segmento.append({
                        'punto': punto_geom.asPoint(),
                        'distancia': segmento_actual.lineLocatePoint(punto_geom) / segmento_actual.length()
                    })
            
            # Ordenar los puntos por distancia normalizada dentro del segmento
            puntos_en_segmento.sort(key=lambda x: x['distancia'])
            
            # Añadir los puntos al resultado
            for punto_info in puntos_en_segmento:
                nueva_linea.append(punto_info['punto'])
            
            # Añadir el punto final del segmento actual
            if i < len(linea) - 1:
                nueva_linea.append(linea[i+1])
        
        # Crear segmentos entre puntos consecutivos
        for i in range(len(nueva_linea) - 1):
            # Crear un segmento
            segmento = QgsGeometry.fromPolylineXY([nueva_linea[i], nueva_linea[i+1]])
            
            # Solo añadir segmentos con longitud
            if segmento.length() > 0.0001:
                resultados.append(segmento)
        
        return resultados

    def inicializar_contenido(self):
        """Inicializa el contenido del diálogo de forma segura"""
        try:
            # Asegurar que los checkboxes estén deschequeados por defecto
            if hasattr(self, 'dividir_en_vertices'):
                self.dividir_en_vertices.setChecked(False)
            
            if hasattr(self, 'modificar_capa_actual'):
                self.modificar_capa_actual.setChecked(False)
            
            # Cargar las capas disponibles
            self.cargar_capas()
        except:
            # Si hay algún error, manejarlo silenciosamente
            import traceback
            print("Error al inicializar contenido:", traceback.format_exc())

