# balsas_module/panel_balsas.py
"""
Panel principal para el cálculo de volúmenes de balsas de riego
(Compatible con QGIS 3.x/Qt5 y QGIS 4.x/Qt6)
"""
import os
from qgis.PyQt.QtWidgets import (
    QDockWidget, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QDoubleSpinBox, QPushButton, QComboBox, QTextEdit,
    QGroupBox, QCheckBox, QProgressBar, QMessageBox, QApplication
)
from qgis.PyQt.QtCore import Qt, QThread, pyqtSignal, QTimer
from qgis.core import (
    QgsProject, QgsVectorLayer, QgsProcessingUtils,
    QgsProcessingContext, QgsProcessingFeedback, QgsWkbTypes,
    QgsFeature, QgsProcessing
)

try:
    from .calcular_volumen_balsa_v3 import CalcularVolumenBalsaV3
except ImportError:
    class CalcularVolumenBalsaV3:
        def processAlgorithm(self, parameters, context, feedback):
            raise Exception("Algoritmo no disponible")

class PanelBalsas(QDockWidget):
    """Panel principal para el cálculo de volúmenes de balsas de riego"""
    
    def __init__(self, iface):
        super().__init__("Balsas de Riego", iface.mainWindow())
        self.iface = iface
        self.setObjectName("PanelBalsas")
        self.setMinimumWidth(350)
        
        self.setup_ui()
        self.connect_signals()
        
    def setup_ui(self):
        """Configura la interfaz de usuario"""
        main_widget = QWidget()
        self.setWidget(main_widget)
        
        layout = QVBoxLayout(main_widget)
        layout.setSpacing(8)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # 1. Selección de capa
        self.setup_layer_selection(layout)
        
        # 2. Parámetros principales
        self.setup_parameters(layout)
        
        # 3. Opciones de salida
        self.setup_output_options(layout)
        
        # 4. Botones
        self.setup_buttons(layout)
        
        # 5. Panel de resumen
        self.setup_summary_panel(layout)
        
        # Espaciador al final
        layout.addStretch()
        
    def setup_layer_selection(self, layout):
        """Configura la selección de capas"""
        group = QGroupBox("Selección de Capa")
        group_layout = QVBoxLayout(group)
        
        group_layout.addWidget(QLabel("Capa de polígonos:"))
        self.layer_combo = QComboBox()
        group_layout.addWidget(self.layer_combo)
        
        refresh_btn = QPushButton("Actualizar capas")
        refresh_btn.clicked.connect(self.update_layer_combo)
        group_layout.addWidget(refresh_btn)
        
        layout.addWidget(group)
        
    def setup_parameters(self, layout):
        """Configura los parámetros"""
        group = QGroupBox("Parámetros")
        group_layout = QGridLayout(group)
        
        # Profundidad
        group_layout.addWidget(QLabel("Profundidad (m):"), 0, 0)
        self.profundidad_spin = QDoubleSpinBox()
        self.profundidad_spin.setRange(0.1, 50.0)
        self.profundidad_spin.setValue(2.0)
        self.profundidad_spin.setDecimals(2)
        group_layout.addWidget(self.profundidad_spin, 0, 1)
        
        # Talud horizontal
        group_layout.addWidget(QLabel("Talud H (m):"), 1, 0)
        self.talud_h_spin = QDoubleSpinBox()
        self.talud_h_spin.setRange(0.1, 10.0)
        self.talud_h_spin.setValue(1.0)
        self.talud_h_spin.setDecimals(2)
        group_layout.addWidget(self.talud_h_spin, 1, 1)
        
        # Talud vertical
        group_layout.addWidget(QLabel("Talud V (m):"), 2, 0)
        self.talud_v_spin = QDoubleSpinBox()
        self.talud_v_spin.setRange(0.1, 10.0)
        self.talud_v_spin.setValue(1.0)
        self.talud_v_spin.setDecimals(2)
        group_layout.addWidget(self.talud_v_spin, 2, 1)
        
        # Altura seguridad
        group_layout.addWidget(QLabel("Altura seguridad (m):"), 3, 0)
        self.altura_seg_spin = QDoubleSpinBox()
        self.altura_seg_spin.setRange(0.0, 5.0)
        self.altura_seg_spin.setValue(0.2)
        self.altura_seg_spin.setDecimals(2)
        group_layout.addWidget(self.altura_seg_spin, 3, 1)
        
        # Piso muerto
        group_layout.addWidget(QLabel("Piso muerto (m):"), 4, 0)
        self.piso_muerto_spin = QDoubleSpinBox()
        self.piso_muerto_spin.setRange(0.0, 2.0)
        self.piso_muerto_spin.setValue(0.2)
        self.piso_muerto_spin.setDecimals(2)
        group_layout.addWidget(self.piso_muerto_spin, 4, 1)
        
        # Agarre lateral
        group_layout.addWidget(QLabel("Agarre lateral (m):"), 5, 0)
        self.agarre_spin = QDoubleSpinBox()
        self.agarre_spin.setRange(0.5, 10.0)
        self.agarre_spin.setValue(3.0)
        self.agarre_spin.setDecimals(1)
        group_layout.addWidget(self.agarre_spin, 5, 1)
        
        # Pérdidas
        group_layout.addWidget(QLabel("Pérdidas (%):"), 6, 0)
        self.perdidas_spin = QDoubleSpinBox()
        self.perdidas_spin.setRange(0.0, 20.0)
        self.perdidas_spin.setValue(5.0)
        self.perdidas_spin.setDecimals(1)
        group_layout.addWidget(self.perdidas_spin, 6, 1)
        
        layout.addWidget(group)
        
    def setup_output_options(self, layout):
        """Configura las opciones de salida"""
        group = QGroupBox("Salidas")
        group_layout = QVBoxLayout(group)
        
        self.generar_combinado_check = QCheckBox("Generar capa con 4 niveles")
        self.generar_combinado_check.setChecked(True)
        group_layout.addWidget(self.generar_combinado_check)
        
        self.generar_3d_check = QCheckBox("Generar capa 3D")
        self.generar_3d_check.setChecked(False)
        group_layout.addWidget(self.generar_3d_check)
        
        layout.addWidget(group)
        
    def setup_buttons(self, layout):
        """Configura los botones"""
        button_layout = QHBoxLayout()
        
        self.calculate_btn = QPushButton("Calcular Volúmenes")
        self.calculate_btn.setStyleSheet("""
            QPushButton {
                background-color: #2E8B57;
                color: white;
                border: none;
                padding: 10px;
                border-radius: 4px;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover { background-color: #3CB371; }
            QPushButton:disabled { background-color: #cccccc; }
        """)
        button_layout.addWidget(self.calculate_btn)
        
        self.help_btn = QPushButton("?")
        self.help_btn.setFixedWidth(30)
        self.help_btn.setToolTip("Ayuda y documentación")
        button_layout.addWidget(self.help_btn)
        
        layout.addLayout(button_layout)
        
    def setup_summary_panel(self, layout):
        """Configura el panel de resumen de resultados"""
        group = QGroupBox("Resumen de Resultados")
        group_layout = QVBoxLayout(group)
        
        # Crear etiquetas para mostrar resultados
        self.label_volumen_total = QLabel("Volumen total: --")
        self.label_volumen_total.setStyleSheet("font-weight: bold; color: #2E8B57;")
        group_layout.addWidget(self.label_volumen_total)
        
        self.label_volumen_util = QLabel("Volumen útil: --")
        self.label_volumen_util.setStyleSheet("font-weight: bold; color: #1E6091;")
        group_layout.addWidget(self.label_volumen_util)
        
        self.label_geomembrana_neta = QLabel("Geomembrana neta: --")
        self.label_geomembrana_neta.setStyleSheet("color: #8B4513;")
        group_layout.addWidget(self.label_geomembrana_neta)
        
        self.label_geomembrana_comercial = QLabel("Geomembrana comercial: --")
        self.label_geomembrana_comercial.setStyleSheet("font-weight: bold; color: #B8860B;")
        group_layout.addWidget(self.label_geomembrana_comercial)
        
        # Botón para copiar el resumen al portapapeles
        self.copiar_btn = QPushButton("Copiar resumen")
        self.copiar_btn.setToolTip("Copiar parámetros y resultados al portapapeles")
        self.copiar_btn.setStyleSheet(
            "QPushButton { background: transparent; color: #2E8B57; "
            "border: 1px solid #2E8B57; padding: 5px 10px; border-radius: 4px; font-size: 10px; }"
            "QPushButton:hover { background: rgba(46,139,87,0.12); }"
        )
        group_layout.addWidget(self.copiar_btn)
        self._last_results = {}
        
        # Inicialmente oculto
        group.setVisible(False)
        self.summary_group = group
        
        layout.addWidget(group)
        
    def connect_signals(self):
        """Conecta las señales"""
        self.calculate_btn.clicked.connect(self.start_calculation)
        self.help_btn.clicked.connect(self.show_help)
        self.copiar_btn.clicked.connect(self.copiar_resumen)
        self.update_layer_combo()
        
    def update_layer_combo(self):
        """Actualiza el combo de capas"""
        self.layer_combo.clear()
        self.layer_combo.addItem("-- Selecciona una capa --", None)
        
        for layer in QgsProject.instance().mapLayers().values():
            if (isinstance(layer, QgsVectorLayer) and 
                layer.geometryType() == QgsWkbTypes.PolygonGeometry):
                self.layer_combo.addItem(f"{layer.name()}", layer)
                
    def validate_inputs(self):
        """Valida los datos de entrada"""
        if self.layer_combo.currentData() is None:
            self.update_layer_combo()
            if self.layer_combo.currentData() is None:
                raise ValueError("Debe seleccionar una capa de polígonos válida")
            
        layer = self.layer_combo.currentData()
        if not isinstance(layer, QgsVectorLayer):
            raise ValueError("La capa seleccionada no es válida")
            
        if layer.featureCount() == 0:
            raise ValueError("La capa seleccionada no tiene elementos")
            
        profundidad = self.profundidad_spin.value()
        altura_seg = self.altura_seg_spin.value()
        piso_muerto = self.piso_muerto_spin.value()
        
        if profundidad <= 0:
            raise ValueError("La profundidad debe ser mayor a 0")
            
        if (altura_seg + piso_muerto) >= profundidad:
            raise ValueError("La suma de altura de seguridad y piso muerto no puede ser mayor o igual a la profundidad total")
            
        return True
        
    def start_calculation(self):
        """Inicia el cálculo"""
        try:
            self.validate_inputs()
            
            layer = self.layer_combo.currentData()
            
            # Obtener valores
            profundidad = max(0.1, self.profundidad_spin.value())
            talud_h = max(0.1, self.talud_h_spin.value())
            talud_v = max(0.1, self.talud_v_spin.value())
            altura_seg = max(0.0, self.altura_seg_spin.value())
            piso_muerto = max(0.0, self.piso_muerto_spin.value())
            agarre = max(0.1, self.agarre_spin.value())
            perdidas = max(0.0, self.perdidas_spin.value())
            
            # Parámetros
            parameters = {
                'INPUT_POLYGON': layer,
                'PROFUNDIDAD': profundidad,
                'TALUD_HORIZONTAL': talud_h,
                'TALUD_VERTICAL': talud_v,
                'ALTURA_SEGURIDAD': altura_seg,
                'ALTURA_PISO_MUERTO': piso_muerto,
                'AGARRE_LATERAL': agarre,
                'PORCENTAJE_PERDIDAS': perdidas,
                'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            }
            
            # Salidas opcionales
            if self.generar_combinado_check.isChecked():
                parameters['OUTPUT_COMBINADO'] = QgsProcessing.TEMPORARY_OUTPUT
            else:
                parameters['OUTPUT_COMBINADO'] = None
                
            if self.generar_3d_check.isChecked():
                parameters['OUTPUT_3D'] = QgsProcessing.TEMPORARY_OUTPUT
            else:
                parameters['OUTPUT_3D'] = None
            
            # Ejecutar algoritmo
            try:
                algorithm = CalcularVolumenBalsaV3()
                algorithm.initAlgorithm()
                
                context = QgsProcessingContext()
                context.setProject(QgsProject.instance())
                
                # Feedback silencioso
                class SilentFeedback(QgsProcessingFeedback):
                    def setProgress(self, progress):
                        pass
                    def pushInfo(self, info):
                        pass
                
                feedback = SilentFeedback()
                
                # Deshabilitar botón
                self.calculate_btn.setEnabled(False)
                
                # Ejecutar
                result = algorithm.processAlgorithm(parameters, context, feedback)
                
                # Procesar resultados
                self.procesar_capas_inmediatamente(result, context)
                
            except Exception as algo_error:
                QMessageBox.critical(self, "Error", f"Error en algoritmo: {str(algo_error)}")
                self.calculate_btn.setEnabled(True)
            
        except ValueError as e:
            QMessageBox.warning(self, "Error de validación", str(e))
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error inesperado: {str(e)}")
            
    def procesar_capas_inmediatamente(self, results, context):
        """Procesa las capas inmediatamente después del cálculo"""
        try:
            project = QgsProject.instance()
            capas_agregadas = 0
            resultados_calculo = {}
            
            for output_key, output_id in results.items():
                if not output_id:
                    continue
                
                try:
                    # Obtener capa temporal
                    temp_layer = QgsProcessingUtils.mapLayerFromString(output_id, context)
                    
                    if not temp_layer:
                        # Método alternativo
                        for layer_id, layer in context.temporaryLayerStore().mapLayers().items():
                            if layer_id == output_id or output_id in layer_id:
                                temp_layer = layer
                                break
                    
                    if not temp_layer or not temp_layer.isValid():
                        continue
                    
                    # Determinar nombre y tipo
                    if output_key == 'OUTPUT':
                        nombre_capa = "Balsas_Volumenes"
                        tipo_geom = "Polygon"
                    elif output_key == 'OUTPUT_COMBINADO':
                        nombre_capa = "Balsas_4_Niveles"
                        tipo_geom = "Polygon"
                    elif output_key == 'OUTPUT_3D':
                        nombre_capa = "Balsas_3D"
                        tipo_geom = "PolygonZ"
                    else:
                        continue
                    
                    # Crear capa nueva
                    crs_string = temp_layer.crs().authid() if temp_layer.crs().isValid() else "EPSG:4326"
                    nueva_capa = QgsVectorLayer(
                        f"{tipo_geom}?crs={crs_string}", 
                        nombre_capa, 
                        "memory"
                    )
                    
                    if not nueva_capa.isValid():
                        continue
                    
                    # Copiar estructura y datos
                    nueva_capa.dataProvider().addAttributes(temp_layer.fields())
                    nueva_capa.updateFields()
                    
                    features = []
                    for feature in temp_layer.getFeatures():
                        features.append(QgsFeature(feature))
                    
                    if features:
                        nueva_capa.dataProvider().addFeatures(features)
                        nueva_capa.updateExtents()
                        nueva_capa.triggerRepaint()
                        
                        project.addMapLayer(nueva_capa)
                        capas_agregadas += 1
                        
                        # Extraer datos para el resumen (solo de la capa principal)
                        if output_key == 'OUTPUT' and features:
                            feature = features[0]  # Primer feature
                            attrs = feature.attributes()
                            fields = nueva_capa.fields()
                            
                            # Buscar los índices de los campos que necesitamos
                            for i, field in enumerate(fields):
                                field_name = field.name().lower()
                                if 'vol_total_m3' in field_name:
                                    resultados_calculo['volumen_total'] = attrs[i] if i < len(attrs) else 0
                                elif 'vol_util_m3' in field_name:
                                    resultados_calculo['volumen_util'] = attrs[i] if i < len(attrs) else 0
                                elif field_name == 'area_revestimiento_m2':
                                    resultados_calculo['geomembrana_neta'] = attrs[i] if i < len(attrs) else 0
                                elif field_name == 'area_revestimiento_comercial_m2':
                                    resultados_calculo['geomembrana_comercial'] = attrs[i] if i < len(attrs) else 0
                        
                except Exception:
                    continue
            
            # Actualizar panel de resumen
            if resultados_calculo:
                self.actualizar_resumen(resultados_calculo)
            
            # No mostrar MessageBox, solo usar el resumen
            if capas_agregadas == 0:
                QMessageBox.warning(
                    self,
                    "Atención",
                    "El cálculo se completó pero no se pudieron crear las capas."
                )
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error procesando capas: {str(e)}")
        finally:
            self.calculate_btn.setEnabled(True)
            
    def actualizar_resumen(self, datos):
        """Actualiza el panel de resumen con los resultados"""
        try:
            # Formatear y mostrar resultados
            vol_total = datos.get('volumen_total', 0)
            vol_util = datos.get('volumen_util', 0)
            geom_neta = datos.get('geomembrana_neta', 0)
            geom_comercial = datos.get('geomembrana_comercial', 0)
            self._last_results = {
                'volumen_total': vol_total, 'volumen_util': vol_util,
                'geomembrana_neta': geom_neta, 'geomembrana_comercial': geom_comercial,
            }
            
            # Actualizar etiquetas
            self.label_volumen_total.setText(f"Volumen total: {vol_total:,.2f} m³ ({vol_total * 1000:,.0f} L)")
            self.label_volumen_util.setText(f"Volumen útil: {vol_util:,.2f} m³ ({vol_util * 1000:,.0f} L)")
            self.label_geomembrana_neta.setText(f"Geomembrana neta: {geom_neta:,.2f} m²")
            self.label_geomembrana_comercial.setText(f"Geomembrana comercial: {geom_comercial:,.2f} m² (con pérdidas)")
            
            # Mostrar el panel de resumen
            self.summary_group.setVisible(True)
            
        except Exception:
            pass

    def copiar_resumen(self):
        """Copia parámetros y resultados al portapapeles."""
        r = getattr(self, '_last_results', {})
        if not r:
            return
        vt = r.get('volumen_total', 0.0)
        vu = r.get('volumen_util', 0.0)
        gn = r.get('geomembrana_neta', 0.0)
        gc = r.get('geomembrana_comercial', 0.0)
        txt = (
            "=== RESUMEN BALSA DE RIEGO ===\n\n"
            "PARÁMETROS\n"
            f"  Profundidad:       {self.profundidad_spin.value():.2f} m\n"
            f"  Talud H / V:       {self.talud_h_spin.value():.2f} / {self.talud_v_spin.value():.2f}\n"
            f"  Altura seguridad:  {self.altura_seg_spin.value():.2f} m\n"
            f"  Piso muerto:       {self.piso_muerto_spin.value():.2f} m\n"
            f"  Agarre lateral:    {self.agarre_spin.value():.2f} m\n"
            f"  Pérdidas:          {self.perdidas_spin.value():.1f} %\n\n"
            "VOLÚMENES\n"
            f"  Volumen total:     {vt:,.2f} m³  ({vt*1000:,.0f} L)\n"
            f"  Volumen útil:      {vu:,.2f} m³  ({vu*1000:,.0f} L)\n"
            f"  Volumen muerto:    {vt - vu:,.2f} m³\n\n"
            "GEOMEMBRANA\n"
            f"  Área neta:         {gn:,.2f} m²\n"
            f"  Área comercial:    {gc:,.2f} m²\n"
        )
        QApplication.clipboard().setText(txt)
        self.copiar_btn.setText("¡Copiado!")
        QTimer.singleShot(2000, lambda: self.copiar_btn.setText("Copiar resumen"))

    def show_help(self):
        """Muestra ayuda"""
        help_text = """
        Calculadora de Balsas de Riego
        
        Calcula volúmenes, áreas y materiales para balsas de riego.
        
        Parámetros:
        - Profundidad: Profundidad total de excavación
        - Talud H/V: Relación horizontal/vertical del talud
        - Altura seguridad: Margen superior anti-desbordamiento
        - Piso muerto: Altura no bombeable en el fondo
        - Agarre lateral: Ancho de anclaje de geomembrana
        
        Salidas:
        - Capa principal: Datos completos
        - 4 niveles: Cada nivel por separado
        - Capa 3D: Para visualización tridimensional
        """
        QMessageBox.information(self, "Ayuda", help_text)
        
    def show_and_activate(self):
        """Muestra y activa el panel"""
        self.show()
        self.raise_()
        self.activateWindow()