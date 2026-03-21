"""
Diálogo para la herramienta de extracción de alturas con carga automática
"""
import os
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QLineEdit, QTextEdit, QProgressBar, QGroupBox,
    QFileDialog, QCheckBox, QMessageBox, QFormLayout, QRadioButton,
    QButtonGroup
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from qgis.core import QgsProject, QgsVectorLayer, QgsRasterLayer, QgsWkbTypes
from qgis.gui import QgsFileWidget


class ProcesamientoThread(QThread):
    """Thread para procesar las alturas sin bloquear la interfaz"""
    progreso = pyqtSignal(int)
    terminado = pyqtSignal(object)
    error = pyqtSignal(str)
    
    def __init__(self, extractor, modificar_original):
        super().__init__()
        self.extractor = extractor
        self.modificar_original = modificar_original
    
    def run(self):
        try:
            resultado = self.extractor.procesar_alturas(self.progreso.emit, self.modificar_original)
            self.terminado.emit(resultado)
        except Exception as e:
            self.error.emit(str(e))


class AlturaDialog(QDialog):
    """Diálogo principal para la extracción de alturas"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        # Importar aquí para evitar dependencias circulares
        from .altura_extractor import AlturaExtractor
        self.extractor = AlturaExtractor()
        self.resultado_layer = None
        self.thread_procesamiento = None
        
        self.init_ui()
        self.cargar_capas_disponibles()
        self.cargar_automatico()  # Nueva función para carga automática
    
    def init_ui(self):
        """Inicializa la interfaz de usuario"""
        self.setWindowTitle("Extractor de Alturas - Red de Riego")
        self.setFixedSize(600, 650)  # Aumentado para nuevas opciones
        
        layout_principal = QVBoxLayout()
        
        # Grupo de entrada de datos
        grupo_entrada = QGroupBox("Datos de Entrada")
        layout_entrada = QFormLayout()
        
        # Selector de capa de líneas
        self.combo_lineas = QComboBox()
        self.combo_lineas.setMinimumWidth(300)
        self.combo_lineas.currentTextChanged.connect(self.verificar_datos)
        layout_entrada.addRow("Capa de Red de Riego:", self.combo_lineas)
        
        # Selector de DEM
        layout_dem = QHBoxLayout()
        self.combo_dem = QComboBox()
        self.combo_dem.setMinimumWidth(250)
        self.combo_dem.currentTextChanged.connect(self.verificar_datos)
        self.btn_cargar_dem = QPushButton("Cargar DEM...")
        self.btn_cargar_dem.clicked.connect(self.cargar_dem_archivo)
        layout_dem.addWidget(self.combo_dem)
        layout_dem.addWidget(self.btn_cargar_dem)
        layout_entrada.addRow("DEM:", layout_dem)
        
        grupo_entrada.setLayout(layout_entrada)
        layout_principal.addWidget(grupo_entrada)
        
        # NUEVO: Grupo de opciones de procesamiento
        grupo_procesamiento = QGroupBox("Opciones de Procesamiento")
        layout_procesamiento = QVBoxLayout()
        
        # Radio buttons para elegir método
        self.radio_nueva_capa = QRadioButton("Crear nueva capa con campos de altura")
        self.radio_modificar_original = QRadioButton("Agregar campos de altura a la capa original")
        self.radio_nueva_capa.setChecked(True)  # Por defecto
        
        # Grupo de botones de radio
        self.grupo_radio = QButtonGroup()
        self.grupo_radio.addButton(self.radio_nueva_capa)
        self.grupo_radio.addButton(self.radio_modificar_original)
        self.grupo_radio.buttonClicked.connect(self.cambio_metodo_procesamiento)
        
        layout_procesamiento.addWidget(self.radio_nueva_capa)
        layout_procesamiento.addWidget(self.radio_modificar_original)
        
        grupo_procesamiento.setLayout(layout_procesamiento)
        layout_principal.addWidget(grupo_procesamiento)
        
        # Grupo de información de compatibilidad
        grupo_info = QGroupBox("Información de Compatibilidad")
        self.txt_compatibilidad = QTextEdit()
        self.txt_compatibilidad.setMaximumHeight(80)
        self.txt_compatibilidad.setReadOnly(True)
        self.txt_compatibilidad.setText("Seleccione las capas para verificar compatibilidad...")
        layout_info = QVBoxLayout()
        layout_info.addWidget(self.txt_compatibilidad)
        grupo_info.setLayout(layout_info)
        layout_principal.addWidget(grupo_info)
        
        # Grupo de opciones de salida (solo para nueva capa)
        self.grupo_salida = QGroupBox("Opciones de Salida")
        layout_salida = QFormLayout()
        
        # Nombre de la capa resultado
        self.txt_nombre_salida = QLineEdit("Red_Riego_Alturas")
        layout_salida.addRow("Nombre de Capa:", self.txt_nombre_salida)
        
        # Checkbox para guardar en disco
        self.chk_guardar_archivo = QCheckBox("Guardar como archivo")
        self.chk_guardar_archivo.stateChanged.connect(self.toggle_archivo_salida)
        layout_salida.addRow("", self.chk_guardar_archivo)
        
        # Selector de archivo de salida
        self.widget_archivo_salida = QgsFileWidget()
        self.widget_archivo_salida.setDialogTitle("Guardar Resultado")
        self.widget_archivo_salida.setFilter("Shapefiles (*.shp);;GeoPackage (*.gpkg)")
        self.widget_archivo_salida.setStorageMode(QgsFileWidget.SaveFile)
        self.widget_archivo_salida.setEnabled(False)
        layout_salida.addRow("Archivo de Salida:", self.widget_archivo_salida)
        
        self.grupo_salida.setLayout(layout_salida)
        layout_principal.addWidget(self.grupo_salida)
        
        # Barra de progreso
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout_principal.addWidget(self.progress_bar)
        
        # Área de resultados/estadísticas
        self.txt_resultados = QTextEdit()
        self.txt_resultados.setMaximumHeight(120)
        self.txt_resultados.setReadOnly(True)
        layout_principal.addWidget(QLabel("Resultados y Diagnóstico:"))
        layout_principal.addWidget(self.txt_resultados)
        
        # Botones
        layout_botones = QHBoxLayout()
        
        self.btn_diagnostico = QPushButton("Diagnóstico")
        self.btn_diagnostico.clicked.connect(self.ejecutar_diagnostico)
        
        self.btn_procesar = QPushButton("Procesar Alturas")
        self.btn_procesar.clicked.connect(self.procesar_alturas)
        
        self.btn_agregar_capa = QPushButton("Agregar a Mapa")
        self.btn_agregar_capa.clicked.connect(self.agregar_capa_mapa)
        self.btn_agregar_capa.setEnabled(False)
        
        self.btn_cerrar = QPushButton("Cerrar")
        self.btn_cerrar.clicked.connect(self.close)
        
        layout_botones.addWidget(self.btn_diagnostico)
        layout_botones.addWidget(self.btn_procesar)
        layout_botones.addWidget(self.btn_agregar_capa)
        layout_botones.addStretch()
        layout_botones.addWidget(self.btn_cerrar)
        
        layout_principal.addLayout(layout_botones)
        self.setLayout(layout_principal)
    
    def cambio_metodo_procesamiento(self):
        """Maneja el cambio entre crear nueva capa o modificar original"""
        if self.radio_modificar_original.isChecked():
            self.grupo_salida.setEnabled(False)
            self.btn_agregar_capa.setText("Refrescar Mapa")
            self.verificar_datos()  # Actualizar información de compatibilidad
        else:
            self.grupo_salida.setEnabled(True)
            self.btn_agregar_capa.setText("Agregar a Mapa")
            self.verificar_datos()  # Actualizar información de compatibilidad
    
    def cargar_capas_disponibles(self):
        """Carga las capas disponibles en los combobox"""
        # Limpiar combos
        self.combo_lineas.clear()
        self.combo_dem.clear()
        
        # Agregar opción por defecto
        self.combo_lineas.addItem("-- Seleccionar capa de líneas --", None)
        self.combo_dem.addItem("-- Seleccionar DEM --", None)
        
        # Cargar capas del proyecto
        for nombre, capa in QgsProject.instance().mapLayers().items():
            if isinstance(capa, QgsVectorLayer):
                if capa.geometryType() == QgsWkbTypes.LineGeometry:
                    self.combo_lineas.addItem(capa.name(), capa)
            elif isinstance(capa, QgsRasterLayer):
                self.combo_dem.addItem(capa.name(), capa)
        
        # Agregar opción para cargar DEM externo si no hay ninguno
        if self.combo_dem.count() <= 1:  # Solo la opción por defecto
            self.combo_dem.addItem("-- Cargar DEM desde archivo --", "cargar_archivo")
    
    def cargar_automatico(self):
        """Carga automáticamente capas con nombres específicos"""
        try:
            red_riego_cargada = False
            dem_cargado = False
            mensajes_carga = []
            
            # Buscar capa "Red de riego" (insensible a mayúsculas/minúsculas)
            for i in range(self.combo_lineas.count()):
                nombre_capa = self.combo_lineas.itemText(i).lower()
                if any(palabra in nombre_capa for palabra in ["red de riego", "red_de_riego", "redriego", "red riego"]):
                    self.combo_lineas.setCurrentIndex(i)
                    red_riego_cargada = True
                    mensajes_carga.append(f"✅ Red de riego: '{self.combo_lineas.itemText(i)}'")
                    break
            
            # Buscar DEM (cualquier capa raster)
            if self.combo_dem.count() > 1:  # Hay DEMs disponibles
                # Buscar uno que contenga palabras clave
                dem_encontrado = False
                for i in range(1, self.combo_dem.count()):  # Empezar desde 1 para saltar "Seleccionar DEM"
                    nombre_dem = self.combo_dem.itemText(i).lower()
                    if any(palabra in nombre_dem for palabra in ["dem", "elevation", "altura", "elevacion", "srtm", "dtm", "mde"]):
                        self.combo_dem.setCurrentIndex(i)
                        dem_cargado = True
                        dem_encontrado = True
                        mensajes_carga.append(f"✅ DEM: '{self.combo_dem.itemText(i)}'")
                        break
                
                # Si no encuentra uno específico, usar el primero disponible
                if not dem_encontrado and self.combo_dem.count() > 2:  # Más de "Seleccionar" y "Cargar archivo"
                    self.combo_dem.setCurrentIndex(1)  # El primero después de "Seleccionar DEM"
                    dem_cargado = True
                    mensajes_carga.append(f"✅ DEM (auto): '{self.combo_dem.itemText(1)}'")
            
            # Mostrar mensaje informativo sobre la carga automática
            if red_riego_cargada or dem_cargado:
                self.txt_resultados.setText("🔄 CARGA AUTOMÁTICA REALIZADA:\n" + "\n".join(mensajes_carga))
                self.txt_resultados.append("\n📋 Verifique que las capas sean correctas antes de procesar.")
                
                # Verificar compatibilidad automáticamente
                self.verificar_datos()
            else:
                self.txt_resultados.setText("ℹ️ No se detectaron capas con nombres estándar.\n"
                                          "Seleccione manualmente:\n"
                                          "• Capa de líneas (ej: 'Red de riego')\n"
                                          "• DEM o modelo de elevación")
                
        except Exception as e:
            self.txt_resultados.append(f"❌ Error en carga automática: {str(e)}")
    
    def cargar_dem_archivo(self):
        """Carga un DEM desde archivo"""
        archivo, _ = QFileDialog.getOpenFileName(
            self, "Seleccionar DEM",
            "", "Archivos Raster (*.tif *.tiff *.img *.asc);;Todos los archivos (*)"
        )
        
        if archivo:
            if self.extractor.cargar_dem(archivo):
                # Agregar al combo si no está ya
                nombre_archivo = os.path.basename(archivo)
                for i in range(self.combo_dem.count()):
                    if self.combo_dem.itemText(i) == nombre_archivo:
                        self.combo_dem.setCurrentIndex(i)
                        return
                
                # Si no está, agregarlo
                self.combo_dem.addItem(nombre_archivo, self.extractor.dem_layer)
                self.combo_dem.setCurrentIndex(self.combo_dem.count() - 1)
                self.verificar_datos()
    
    def toggle_archivo_salida(self, estado):
        """Habilita/deshabilita el selector de archivo de salida"""
        self.widget_archivo_salida.setEnabled(estado == Qt.Checked)
    
    def verificar_datos(self):
        """Verifica compatibilidad entre capas seleccionadas"""
        capa_lineas = self.combo_lineas.currentData()
        dem_seleccionado = self.combo_dem.currentData()
        
        if not capa_lineas or not dem_seleccionado or dem_seleccionado == "cargar_archivo":
            self.txt_compatibilidad.setText("Seleccione ambas capas para verificar compatibilidad...")
            return
        
        try:
            info_compatibilidad = []
            
            # Información básica de las capas
            info_compatibilidad.append(f"📋 LÍNEAS: {capa_lineas.name()}")
            info_compatibilidad.append(f"   CRS: {capa_lineas.crs().authid()}")
            info_compatibilidad.append(f"   Features: {capa_lineas.featureCount()}")
            
            info_compatibilidad.append(f"\n📋 DEM: {dem_seleccionado.name()}")
            info_compatibilidad.append(f"   CRS: {dem_seleccionado.crs().authid()}")
            
            # Verificar CRS
            if capa_lineas.crs().authid() == dem_seleccionado.crs().authid():
                info_compatibilidad.append("\n✅ CRS: Idénticos - Perfecto")
            else:
                info_compatibilidad.append(f"\n⚠️ CRS: Diferentes - Se aplicará transformación automática")
            
            # Verificar superposición de extents
            extent_lineas = capa_lineas.extent()
            extent_dem = dem_seleccionado.extent()
            
            if extent_dem.intersects(extent_lineas):
                info_compatibilidad.append("✅ SUPERPOSICIÓN: Las capas se superponen")
            else:
                info_compatibilidad.append("❌ SUPERPOSICIÓN: Las capas NO se superponen - Problema crítico")
            
            # Verificar si los campos ya existen (para modo modificar original)
            if self.radio_modificar_original.isChecked():
                self.extractor.line_layer = capa_lineas
                campos_faltantes = self.extractor.verificar_campos_existentes()
                if campos_faltantes:
                    info_compatibilidad.append(f"\n📝 Se agregarán campos: {', '.join(campos_faltantes)}")
                else:
                    info_compatibilidad.append(f"\n📝 Campos de altura ya existen - se actualizarán valores")
            
            self.txt_compatibilidad.setText("\n".join(info_compatibilidad))
            
        except Exception as e:
            self.txt_compatibilidad.setText(f"❌ Error verificando compatibilidad: {str(e)}")
    
    def ejecutar_diagnostico(self):
        """Ejecuta un diagnóstico detallado de las capas"""
        try:
            capa_lineas = self.combo_lineas.currentData()
            dem_seleccionado = self.combo_dem.currentData()
            
            if not capa_lineas:
                QMessageBox.warning(self, "Advertencia", "Seleccione una capa de líneas")
                return
            
            if not dem_seleccionado or dem_seleccionado == "cargar_archivo":
                QMessageBox.warning(self, "Advertencia", "Seleccione un DEM")
                return
            
            self.txt_resultados.clear()
            self.txt_resultados.append("🔍 === DIAGNÓSTICO DETALLADO ===\n")
            
            # Configurar el extractor para diagnóstico
            self.extractor.line_layer = capa_lineas
            self.extractor.dem_layer = dem_seleccionado
            self.extractor.configurar_transformacion()
            
            # Probar extracción en algunos puntos
            self.txt_resultados.append("🧪 Probando extracción de alturas en puntos de muestra...")
            
            puntos_probados = 0
            alturas_exitosas = 0
            
            for i, feature in enumerate(capa_lineas.getFeatures()):
                if i >= 3:  # Solo probar los primeros 3 features
                    break
                
                geometria = feature.geometry()
                if geometria and not geometria.isEmpty():
                    punto_inicial, punto_final = self.extractor.obtener_puntos_extremos(geometria)
                    
                    if punto_inicial and punto_final:
                        puntos_probados += 2
                        
                        altura_ini = self.extractor.extraer_altura_punto(punto_inicial)
                        altura_fin = self.extractor.extraer_altura_punto(punto_final)
                        
                        self.txt_resultados.append(f"📍 Feature {i+1}:")
                        self.txt_resultados.append(f"  Inicial: {altura_ini}m en {punto_inicial}")
                        self.txt_resultados.append(f"  Final: {altura_fin}m en {punto_final}")
                        
                        if altura_ini is not None:
                            alturas_exitosas += 1
                        if altura_fin is not None:
                            alturas_exitosas += 1
            
            self.txt_resultados.append(f"\n📊 RESULTADOS DEL DIAGNÓSTICO:")
            self.txt_resultados.append(f"• Puntos probados: {puntos_probados}")
            self.txt_resultados.append(f"• Alturas extraídas: {alturas_exitosas}")
            if puntos_probados > 0:
                tasa_exito = (alturas_exitosas/puntos_probados*100)
                if tasa_exito >= 90:
                    self.txt_resultados.append(f"• ✅ Tasa de éxito: {tasa_exito:.1f}% - Excelente")
                elif tasa_exito >= 70:
                    self.txt_resultados.append(f"• ⚠️ Tasa de éxito: {tasa_exito:.1f}% - Aceptable")
                else:
                    self.txt_resultados.append(f"• ❌ Tasa de éxito: {tasa_exito:.1f}% - Problemático")
            else:
                self.txt_resultados.append("• ❌ No se pudieron probar puntos")
            
        except Exception as e:
            self.txt_resultados.append(f"❌ Error en diagnóstico: {str(e)}")
    
    def procesar_alturas(self):
        """Inicia el procesamiento de alturas"""
        try:
            # Validar entradas
            if self.combo_lineas.count() <= 1:
                QMessageBox.warning(self, "Advertencia", "No hay capas de líneas disponibles")
                return
            
            if self.combo_dem.count() <= 1:
                QMessageBox.warning(self, "Advertencia", "No hay DEM seleccionado")
                return
            
            # Obtener capa de líneas seleccionada
            capa_lineas = self.combo_lineas.currentData()
            if not capa_lineas:
                QMessageBox.warning(self, "Advertencia", "Seleccione una capa de líneas válida")
                return
            
            # Obtener DEM seleccionado
            dem_seleccionado = self.combo_dem.currentData()
            if not dem_seleccionado or dem_seleccionado == "cargar_archivo":
                QMessageBox.warning(self, "Advertencia", "Seleccione un DEM válido")
                return
            
            # Verificar si se va a modificar la capa original y confirmar
            modificar_original = self.radio_modificar_original.isChecked()
            if modificar_original:
                respuesta = QMessageBox.question(
                    self, 
                    "Confirmar Modificación",
                    f"¿Está seguro de agregar los campos de altura a la capa '{capa_lineas.name()}'?\n\n"
                    "Esta acción modificará permanentemente la capa original.\n"
                    "Se recomienda hacer una copia de seguridad antes de continuar.",
                    QMessageBox.Yes | QMessageBox.No
                )
                if respuesta != QMessageBox.Yes:
                    return
            
            # Configurar extractor
            self.extractor.dem_layer = dem_seleccionado
            if not self.extractor.cargar_lineas_riego(capa_lineas):
                return
            
            # Configurar interfaz para procesamiento
            self.btn_procesar.setEnabled(False)
            self.btn_diagnostico.setEnabled(False)
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)
            self.txt_resultados.clear()
            
            if modificar_original:
                self.txt_resultados.append("🔄 Iniciando modificación de capa original...")
            else:
                self.txt_resultados.append("🔄 Iniciando creación de nueva capa...")
            
            # Crear y iniciar thread de procesamiento
            self.thread_procesamiento = ProcesamientoThread(self.extractor, modificar_original)
            self.thread_procesamiento.progreso.connect(self.actualizar_progreso)
            self.thread_procesamiento.terminado.connect(self.procesamiento_terminado)
            self.thread_procesamiento.error.connect(self.procesamiento_error)
            self.thread_procesamiento.start()
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error iniciando procesamiento: {str(e)}")
            self.restaurar_interfaz()
    
    def actualizar_progreso(self, valor):
        """Actualiza la barra de progreso"""
        self.progress_bar.setValue(valor)
    
    def procesamiento_terminado(self, resultado_layer):
        """Maneja la finalización del procesamiento"""
        try:
            self.resultado_layer = resultado_layer
            modificar_original = self.radio_modificar_original.isChecked()
            
            if self.resultado_layer:
                # Mostrar estadísticas
                estadisticas = self.extractor.obtener_estadisticas_alturas()
                if estadisticas:
                    self.mostrar_estadisticas(estadisticas)
                
                # Para nueva capa, habilitar agregar al mapa
                if not modificar_original:
                    # Guardar archivo si se solicitó
                    if self.chk_guardar_archivo.isChecked():
                        archivo_salida = self.widget_archivo_salida.filePath()
                        if archivo_salida:
                            ruta_guardada = self.extractor.guardar_resultado(archivo_salida)
                            if ruta_guardada:
                                self.txt_resultados.append(f"💾 Archivo guardado: {ruta_guardada}")
                    
                    self.btn_agregar_capa.setEnabled(True)
                    self.txt_resultados.append("✅ ¡Nueva capa creada exitosamente!")
                else:
                    # Para capa original modificada
                    self.btn_agregar_capa.setEnabled(True)
                    self.txt_resultados.append("✅ ¡Capa original modificada exitosamente!")
                    self.txt_resultados.append("📝 Los campos de altura se agregaron a la capa existente.")
                
                # Mostrar advertencia si no se extrajeron alturas
                if estadisticas and estadisticas['alturas_procesadas'] == 0:
                    QMessageBox.warning(
                        self, 
                        "Advertencia - Sin alturas extraídas",
                        "No se pudieron extraer alturas del DEM.\n\n"
                        "🔍 Ejecute 'Diagnóstico' para más información.\n\n"
                        "Posibles causas:\n"
                        "• Las líneas están fuera del área del DEM\n"
                        "• CRS incompatibles entre líneas y DEM\n"
                        "• DEM con valores NoData en las ubicaciones\n"
                        "• Problemas con la calidad del DEM"
                    )
            else:
                self.txt_resultados.append("❌ Error: No se pudo procesar las alturas")
            
        except Exception as e:
            self.txt_resultados.append(f"❌ Error en post-procesamiento: {str(e)}")
        
        finally:
            self.restaurar_interfaz()
    
    def procesamiento_error(self, mensaje_error):
        """Maneja errores durante el procesamiento"""
        self.txt_resultados.append(f"❌ Error: {mensaje_error}")
        QMessageBox.critical(self, "Error de Procesamiento", mensaje_error)
        self.restaurar_interfaz()
    
    def restaurar_interfaz(self):
        """Restaura la interfaz después del procesamiento"""
        self.btn_procesar.setEnabled(True)
        self.btn_diagnostico.setEnabled(True)
        self.progress_bar.setVisible(False)
        if self.thread_procesamiento:
            self.thread_procesamiento.quit()
            self.thread_procesamiento.wait()
    
    def mostrar_estadisticas(self, estadisticas):
        """Muestra las estadísticas del procesamiento"""
        try:
            modo = "modificación de capa original" if estadisticas.get('modificar_original', False) else "nueva capa"
            
            texto_stats = f"""
📊 === ESTADÍSTICAS DEL PROCESAMIENTO ({modo}) ===
• Total de tramos: {estadisticas['total_tramos']}
• Tramos con alturas: {estadisticas['alturas_procesadas']}
• Tasa de éxito: {(estadisticas['alturas_procesadas']/estadisticas['total_tramos']*100):.1f}%
            """.strip()
            
            if estadisticas['alturas_procesadas'] > 0:
                texto_stats += f"""
• Rango altura inicial: {estadisticas['altura_min_inicial']:.2f} - {estadisticas['altura_max_inicial']:.2f} m
• Rango altura final: {estadisticas['altura_min_final']:.2f} - {estadisticas['altura_max_final']:.2f} m
• Rango pendientes: {estadisticas['pendiente_min']:.4f}% - {estadisticas['pendiente_max']:.4f}%
                """.strip()
                
                # Análisis de pendientes
                if estadisticas['pendiente_max'] > 15:
                    texto_stats += "\n⚠️ Hay pendientes muy pronunciadas (>15%)"
                if estadisticas['pendiente_min'] < -15:
                    texto_stats += "\n⚠️ Hay contrapendientes muy pronunciadas (<-15%)"
            
            self.txt_resultados.append(texto_stats)
                    
        except Exception as e:
            self.txt_resultados.append(f"❌ Error mostrando estadísticas: {str(e)}")
    
    def agregar_capa_mapa(self):
        """Agrega la capa resultado al mapa o refresca la vista"""
        try:
            modificar_original = self.radio_modificar_original.isChecked()
            
            if modificar_original:
                # Refrescar la capa original
                if self.extractor.line_layer:
                    self.extractor.line_layer.triggerRepaint()
                    self.txt_resultados.append("🔄 Vista de mapa refrescada")
                    QMessageBox.information(self, "Éxito", 
                                          "La capa original ha sido actualizada.\n"
                                          "Los nuevos campos de altura ya están disponibles\n"
                                          "en la tabla de atributos.")
            else:
                # Agregar nueva capa al mapa
                if self.resultado_layer:
                    nombre_capa = self.txt_nombre_salida.text() or "Red_Riego_Alturas"
                    self.resultado_layer.setName(nombre_capa)
                    QgsProject.instance().addMapLayer(self.resultado_layer)
                    self.txt_resultados.append(f"📋 Capa '{nombre_capa}' agregada al mapa")
                    QMessageBox.information(self, "Éxito", 
                                          f"Capa '{nombre_capa}' agregada al mapa correctamente.\n"
                                          "Los campos de altura están disponibles en la tabla de atributos.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error agregando capa al mapa: {str(e)}")
    
    def closeEvent(self, event):
        """Maneja el cierre del diálogo"""
        if self.thread_procesamiento and self.thread_procesamiento.isRunning():
            respuesta = QMessageBox.question(
                self, "Procesamiento en curso",
                "¿Está seguro de cerrar? El procesamiento se cancelará.",
                QMessageBox.Yes | QMessageBox.No
            )
            if respuesta == QMessageBox.Yes:
                self.thread_procesamiento.terminate()
                self.thread_procesamiento.wait()
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()