"""
Módulo para extraer alturas desde DEM para líneas de red de riego - Versión mejorada v2
"""
import os
from qgis.core import (
    QgsRasterLayer, QgsVectorLayer, QgsProject, QgsFeature,
    QgsField, QgsFields, QgsPointXY, QgsGeometry, QgsWkbTypes,
    QgsProcessingException, QgsRasterBandStats, QgsCoordinateReferenceSystem,
    QgsCoordinateTransform, QgsRasterDataProvider
)
from qgis.PyQt.QtCore import QVariant
from PyQt5.QtWidgets import QMessageBox
import processing


class AlturaExtractor:
    """Clase para extraer alturas desde un DEM hacia líneas de riego"""
    
    def __init__(self):
        self.dem_layer = None
        self.line_layer = None
        self.resultado_layer = None
        self.transform = None
        self.debug_info = []
        self.modificar_capa_original = False  # Nueva opción
    
    def log_debug(self, mensaje):
        """Registra información de debug"""
        self.debug_info.append(mensaje)
        print(f"DEBUG: {mensaje}")
    
    def cargar_dem(self, ruta_dem):
        """Carga el DEM desde archivo"""
        try:
            self.dem_layer = QgsRasterLayer(ruta_dem, "DEM")
            if not self.dem_layer.isValid():
                raise QgsProcessingException(f"No se pudo cargar el DEM: {ruta_dem}")
            
            # Información de diagnóstico del DEM
            self.log_debug(f"DEM cargado: {self.dem_layer.name()}")
            self.log_debug(f"CRS del DEM: {self.dem_layer.crs().authid()}")
            self.log_debug(f"Extent del DEM: {self.dem_layer.extent()}")
            
            # Verificar estadísticas del DEM
            provider = self.dem_layer.dataProvider()
            stats = provider.bandStatistics(1, QgsRasterBandStats.All)
            self.log_debug(f"Estadísticas DEM - Min: {stats.minimumValue}, Max: {stats.maximumValue}")
            
            return True
        except Exception as e:
            self.log_debug(f"Error cargando DEM: {str(e)}")
            QMessageBox.critical(None, "Error", f"Error cargando DEM: {str(e)}")
            return False
    
    def cargar_lineas_riego(self, capa_lineas):
        """Carga la capa de líneas de riego"""
        try:
            if isinstance(capa_lineas, str):
                self.line_layer = QgsVectorLayer(capa_lineas, "Red de Riego", "ogr")
            else:
                self.line_layer = capa_lineas
            
            if not self.line_layer.isValid():
                raise QgsProcessingException("Capa de líneas no válida")
            
            # Verificar que sea una capa de líneas
            if self.line_layer.geometryType() != QgsWkbTypes.LineGeometry:
                raise QgsProcessingException("La capa seleccionada no contiene geometrías lineales")
            
            # Información de diagnóstico de las líneas
            self.log_debug(f"Líneas cargadas: {self.line_layer.name()}")
            self.log_debug(f"CRS de líneas: {self.line_layer.crs().authid()}")
            self.log_debug(f"Extent de líneas: {self.line_layer.extent()}")
            self.log_debug(f"Número de features: {self.line_layer.featureCount()}")
            
            # Configurar transformación de coordenadas si es necesaria
            self.configurar_transformacion()
            
            return True
        except Exception as e:
            self.log_debug(f"Error cargando líneas: {str(e)}")
            QMessageBox.critical(None, "Error", f"Error cargando líneas: {str(e)}")
            return False
    
    def configurar_transformacion(self):
        """Configura la transformación de coordenadas entre líneas y DEM"""
        try:
            if not self.dem_layer or not self.line_layer:
                return
            
            crs_lineas = self.line_layer.crs()
            crs_dem = self.dem_layer.crs()
            
            self.log_debug(f"CRS líneas: {crs_lineas.authid()}")
            self.log_debug(f"CRS DEM: {crs_dem.authid()}")
            
            if crs_lineas.authid() != crs_dem.authid():
                self.log_debug("CRS diferentes, configurando transformación")
                self.transform = QgsCoordinateTransform(crs_lineas, crs_dem, QgsProject.instance())
            else:
                self.log_debug("CRS idénticos, no se necesita transformación")
                self.transform = None
                
        except Exception as e:
            self.log_debug(f"Error configurando transformación: {str(e)}")
    
    def extraer_altura_punto(self, punto):
        """Extrae la altura de un punto específico desde el DEM"""
        try:
            if not self.dem_layer:
                self.log_debug("No hay DEM cargado")
                return None
            
            # Transformar punto si es necesario
            punto_transformado = punto
            if self.transform:
                try:
                    punto_transformado = self.transform.transform(punto)
                    self.log_debug(f"Punto transformado de {punto} a {punto_transformado}")
                except Exception as e:
                    self.log_debug(f"Error transformando punto: {str(e)}")
                    return None
            
            # Verificar que el punto esté dentro del extent del DEM
            extent = self.dem_layer.extent()
            if not extent.contains(punto_transformado):
                self.log_debug(f"Punto {punto_transformado} fuera del extent del DEM {extent}")
                return None
            
            # Obtener el proveedor de datos del DEM
            provider = self.dem_layer.dataProvider()
            if not provider:
                self.log_debug("No se pudo obtener el proveedor de datos del DEM")
                return None
            
            # Método 1: Usar identify
            try:
                from qgis.core import QgsRaster
                resultado = provider.identify(punto_transformado, QgsRaster.IdentifyFormatValue)
                if resultado.isValid() and 1 in resultado.results():
                    valor = resultado.results()[1]
                    self.log_debug(f"Altura extraída (método identify): {valor} en punto {punto_transformado}")
                    if valor is not None and valor != provider.sourceNoDataValue(1):
                        return float(valor)
            except Exception as e:
                self.log_debug(f"Error con método identify: {str(e)}")
            
            # Método 2: Usar sample (fallback)
            try:
                resultado = provider.sample(punto_transformado, 1)
                if resultado[0]:  # Si el muestreo fue exitoso
                    valor = resultado[1]
                    self.log_debug(f"Altura extraída (método sample): {valor} en punto {punto_transformado}")
                    if valor is not None and valor != provider.sourceNoDataValue(1):
                        return float(valor)
            except Exception as e:
                self.log_debug(f"Error con método sample: {str(e)}")
            
            self.log_debug(f"No se pudo extraer altura válida para punto {punto_transformado}")
            return None
            
        except Exception as e:
            self.log_debug(f"Error general extrayendo altura: {str(e)}")
            return None
    
    def obtener_puntos_extremos(self, geometria_linea):
        """Obtiene los puntos inicial y final de una línea"""
        try:
            if geometria_linea.isMultipart():
                # Si es multipart, tomar la primera parte
                linea = geometria_linea.asMultiPolyline()[0]
            else:
                linea = geometria_linea.asPolyline()
            
            if len(linea) < 2:
                self.log_debug("Línea con menos de 2 puntos")
                return None, None
            
            punto_inicial = linea[0]  # Primer punto
            punto_final = linea[-1]   # Último punto
            
            self.log_debug(f"Puntos extremos: inicial={punto_inicial}, final={punto_final}")
            
            return punto_inicial, punto_final
        except Exception as e:
            self.log_debug(f"Error obteniendo puntos extremos: {str(e)}")
            return None, None
    
    def verificar_campos_existentes(self):
        """Verifica si los campos de altura ya existen en la capa"""
        campos_altura = ["altura_inicial", "altura_final", "diferencia_altura", "pendiente_pct"]
        campos_existentes = [field.name() for field in self.line_layer.fields()]
        
        campos_faltantes = []
        for campo in campos_altura:
            if campo not in campos_existentes:
                campos_faltantes.append(campo)
        
        return campos_faltantes
    
    def agregar_campos_alturas(self):
        """Agrega los campos de altura a la capa existente si no existen"""
        try:
            campos_faltantes = self.verificar_campos_existentes()
            
            if not campos_faltantes:
                self.log_debug("Todos los campos de altura ya existen")
                return True
            
            self.log_debug(f"Agregando campos faltantes: {campos_faltantes}")
            
            # Crear los campos que faltan
            nuevos_campos = []
            for campo in campos_faltantes:
                if campo == "altura_inicial":
                    nuevos_campos.append(QgsField("altura_inicial", QVariant.Double, "double", 10, 2))
                elif campo == "altura_final":
                    nuevos_campos.append(QgsField("altura_final", QVariant.Double, "double", 10, 2))
                elif campo == "diferencia_altura":
                    nuevos_campos.append(QgsField("diferencia_altura", QVariant.Double, "double", 10, 2))
                elif campo == "pendiente_pct":
                    nuevos_campos.append(QgsField("pendiente_pct", QVariant.Double, "double", 10, 4))
            
            # Agregar campos a la capa
            provider = self.line_layer.dataProvider()
            provider.addAttributes(nuevos_campos)
            self.line_layer.updateFields()
            
            self.log_debug(f"Campos agregados exitosamente: {[campo.name() for campo in nuevos_campos]}")
            return True
            
        except Exception as e:
            self.log_debug(f"Error agregando campos: {str(e)}")
            QMessageBox.critical(None, "Error", f"Error agregando campos: {str(e)}")
            return False
    
    def crear_capa_resultado(self, nombre_salida="Red_Riego_Alturas"):
        """Crea una nueva capa con los campos de altura agregados"""
        try:
            # Copiar los campos existentes
            campos_originales = self.line_layer.fields()
            nuevos_campos = QgsFields(campos_originales)
            
            # Agregar nuevos campos para alturas (sin longitud_m)
            nuevos_campos.append(QgsField("altura_inicial", QVariant.Double, "double", 10, 2))
            nuevos_campos.append(QgsField("altura_final", QVariant.Double, "double", 10, 2))
            nuevos_campos.append(QgsField("diferencia_altura", QVariant.Double, "double", 10, 2))
            nuevos_campos.append(QgsField("pendiente_pct", QVariant.Double, "double", 10, 4))
            
            # Crear capa temporal en memoria
            crs = self.line_layer.crs().authid()
            uri = f"LineString?crs={crs}"
            self.resultado_layer = QgsVectorLayer(uri, nombre_salida, "memory")
            
            # Establecer los campos
            provider = self.resultado_layer.dataProvider()
            provider.addAttributes(nuevos_campos)
            self.resultado_layer.updateFields()
            
            self.log_debug(f"Capa resultado creada con {len(nuevos_campos)} campos")
            return True
        except Exception as e:
            self.log_debug(f"Error creando capa resultado: {str(e)}")
            QMessageBox.critical(None, "Error", f"Error creando capa resultado: {str(e)}")
            return False
    
    def procesar_alturas(self, progreso_callback=None, modificar_original=False):
        """Procesa todas las líneas extrayendo alturas y calculando diferencias"""
        try:
            if not self.dem_layer or not self.line_layer:
                raise QgsProcessingException("DEM o capa de líneas no cargados")
            
            self.debug_info.clear()
            self.log_debug("=== INICIANDO PROCESAMIENTO DE ALTURAS ===")
            self.modificar_capa_original = modificar_original
            
            if modificar_original:
                self.log_debug("Modo: Modificar capa original")
                # Agregar campos si no existen
                if not self.agregar_campos_alturas():
                    return None
                self.resultado_layer = self.line_layer
            else:
                self.log_debug("Modo: Crear nueva capa")
                # Crear capa de resultado
                if not self.crear_capa_resultado():
                    return None
            
            if modificar_original:
                # Modificar features existentes
                self.line_layer.startEditing()
                total_features = self.line_layer.featureCount()
                alturas_exitosas = 0
                
                self.log_debug(f"Modificando {total_features} features en capa original")
                
                for i, feature in enumerate(self.line_layer.getFeatures()):
                    if progreso_callback:
                        progreso_callback(int((i / total_features) * 100))
                    
                    geometria = feature.geometry()
                    if not geometria or geometria.isEmpty():
                        continue
                    
                    # Obtener puntos extremos
                    punto_inicial, punto_final = self.obtener_puntos_extremos(geometria)
                    if not punto_inicial or not punto_final:
                        continue
                    
                    # Extraer alturas
                    altura_inicial = self.extraer_altura_punto(punto_inicial)
                    altura_final = self.extraer_altura_punto(punto_final)
                    
                    if altura_inicial is not None and altura_final is not None:
                        alturas_exitosas += 1
                    
                    # Calcular diferencia y pendiente
                    diferencia_altura = None
                    pendiente_pct = None
                    longitud_m = geometria.length()
                    
                    if altura_inicial is not None and altura_final is not None:
                        diferencia_altura = altura_final - altura_inicial
                        if longitud_m > 0:
                            pendiente_pct = (diferencia_altura / longitud_m) * 100
                    
                    # Actualizar atributos del feature
                    feature_id = feature.id()
                    self.line_layer.changeAttributeValue(feature_id, self.line_layer.fields().indexFromName("altura_inicial"), altura_inicial)
                    self.line_layer.changeAttributeValue(feature_id, self.line_layer.fields().indexFromName("altura_final"), altura_final)
                    self.line_layer.changeAttributeValue(feature_id, self.line_layer.fields().indexFromName("diferencia_altura"), diferencia_altura)
                    self.line_layer.changeAttributeValue(feature_id, self.line_layer.fields().indexFromName("pendiente_pct"), pendiente_pct)
                
                # Confirmar cambios
                self.line_layer.commitChanges()
                
            else:
                # Crear features para nueva capa
                features_procesadas = []
                total_features = self.line_layer.featureCount()
                alturas_exitosas = 0
                
                self.log_debug(f"Procesando {total_features} features para nueva capa")
                
                for i, feature in enumerate(self.line_layer.getFeatures()):
                    if progreso_callback:
                        progreso_callback(int((i / total_features) * 100))
                    
                    geometria = feature.geometry()
                    if not geometria or geometria.isEmpty():
                        continue
                    
                    # Obtener puntos extremos
                    punto_inicial, punto_final = self.obtener_puntos_extremos(geometria)
                    if not punto_inicial or not punto_final:
                        continue
                    
                    # Extraer alturas
                    altura_inicial = self.extraer_altura_punto(punto_inicial)
                    altura_final = self.extraer_altura_punto(punto_final)
                    
                    if altura_inicial is not None and altura_final is not None:
                        alturas_exitosas += 1
                    
                    # Calcular diferencia y pendiente
                    diferencia_altura = None
                    pendiente_pct = None
                    longitud_m = geometria.length()
                    
                    if altura_inicial is not None and altura_final is not None:
                        diferencia_altura = altura_final - altura_inicial
                        if longitud_m > 0:
                            pendiente_pct = (diferencia_altura / longitud_m) * 100
                    
                    # Crear nueva feature
                    nueva_feature = QgsFeature(self.resultado_layer.fields())
                    
                    # Copiar atributos originales
                    for field in self.line_layer.fields():
                        if field.name() in [f.name() for f in nueva_feature.fields()]:
                            nueva_feature.setAttribute(field.name(), feature.attribute(field.name()))
                    
                    # Establecer geometría
                    nueva_feature.setGeometry(geometria)
                    
                    # Agregar nuevos atributos
                    nueva_feature.setAttribute("altura_inicial", altura_inicial)
                    nueva_feature.setAttribute("altura_final", altura_final)
                    nueva_feature.setAttribute("diferencia_altura", diferencia_altura)
                    nueva_feature.setAttribute("pendiente_pct", pendiente_pct)
                    
                    features_procesadas.append(nueva_feature)
                
                # Agregar features a la capa resultado
                provider = self.resultado_layer.dataProvider()
                provider.addFeatures(features_procesadas)
                self.resultado_layer.updateExtents()
            
            self.log_debug(f"=== PROCESAMIENTO COMPLETADO ===")
            self.log_debug(f"Alturas extraídas exitosamente: {alturas_exitosas}")
            
            if progreso_callback:
                progreso_callback(100)
            
            # Mostrar información de debug si no se extrajeron alturas
            if alturas_exitosas == 0:
                self.mostrar_diagnostico()
            
            return self.resultado_layer
            
        except Exception as e:
            self.log_debug(f"Error procesando alturas: {str(e)}")
            if modificar_original and self.line_layer.isEditable():
                self.line_layer.rollBack()
            QMessageBox.critical(None, "Error", f"Error procesando alturas: {str(e)}")
            return None
    
    def mostrar_diagnostico(self):
        """Muestra información de diagnóstico cuando no se extraen alturas"""
        diagnostico = "\n".join(self.debug_info[-20:])  # Últimas 20 líneas
        
        QMessageBox.warning(
            None, 
            "Diagnóstico - No se extrajeron alturas",
            f"No se pudieron extraer alturas del DEM. Información de diagnóstico:\n\n{diagnostico}\n\n"
            "Posibles causas:\n"
            "• Las líneas están fuera del área del DEM\n"
            "• CRS incompatibles entre líneas y DEM\n"
            "• DEM con valores NoData en las ubicaciones de las líneas\n"
            "• Problemas con el formato del DEM"
        )
    
    def guardar_resultado(self, ruta_salida, formato="ESRI Shapefile"):
        """Guarda la capa resultado en disco"""
        try:
            if not self.resultado_layer:
                raise QgsProcessingException("No hay capa resultado para guardar")
            
            # Si se modificó la capa original, no se puede "guardar" como nueva
            if self.modificar_capa_original:
                QMessageBox.information(None, "Información", "Los datos se guardaron directamente en la capa original")
                return "Capa original modificada"
            
            opciones = []
            if formato == "ESRI Shapefile":
                driver = "ESRI Shapefile"
                if not ruta_salida.endswith('.shp'):
                    ruta_salida += '.shp'
            elif formato == "GeoPackage":
                driver = "GPKG"
                if not ruta_salida.endswith('.gpkg'):
                    ruta_salida += '.gpkg'
            else:
                driver = formato
            
            # Usar processing para guardar
            resultado = processing.run("native:savefeatures", {
                'INPUT': self.resultado_layer,
                'OUTPUT': ruta_salida,
                'LAYER_NAME': os.path.splitext(os.path.basename(ruta_salida))[0],
                'DATASOURCE_OPTIONS': '',
                'LAYER_OPTIONS': ''
            })
            
            return resultado['OUTPUT']
            
        except Exception as e:
            self.log_debug(f"Error guardando resultado: {str(e)}")
            QMessageBox.critical(None, "Error", f"Error guardando resultado: {str(e)}")
            return None
    
    def obtener_estadisticas_alturas(self):
        """Obtiene estadísticas básicas de las alturas procesadas"""
        try:
            if not self.resultado_layer:
                return None
            
            estadisticas = {
                'total_tramos': self.resultado_layer.featureCount(),
                'alturas_procesadas': 0,
                'altura_min_inicial': float('inf'),
                'altura_max_inicial': float('-inf'),
                'altura_min_final': float('inf'),
                'altura_max_final': float('-inf'),
                'diferencia_max_positiva': float('-inf'),
                'diferencia_max_negativa': float('inf'),
                'pendiente_max': float('-inf'),
                'pendiente_min': float('inf'),
                'debug_info': self.debug_info.copy(),  # Incluir información de debug
                'modificar_original': self.modificar_capa_original
            }
            
            for feature in self.resultado_layer.getFeatures():
                altura_inicial = feature.attribute("altura_inicial")
                altura_final = feature.attribute("altura_final")
                diferencia = feature.attribute("diferencia_altura")
                pendiente = feature.attribute("pendiente_pct")
                
                if altura_inicial is not None and altura_final is not None:
                    estadisticas['alturas_procesadas'] += 1
                    estadisticas['altura_min_inicial'] = min(estadisticas['altura_min_inicial'], altura_inicial)
                    estadisticas['altura_max_inicial'] = max(estadisticas['altura_max_inicial'], altura_inicial)
                    estadisticas['altura_min_final'] = min(estadisticas['altura_min_final'], altura_final)
                    estadisticas['altura_max_final'] = max(estadisticas['altura_max_final'], altura_final)
                    
                    if diferencia is not None:
                        if diferencia > 0:
                            estadisticas['diferencia_max_positiva'] = max(estadisticas['diferencia_max_positiva'], diferencia)
                        else:
                            estadisticas['diferencia_max_negativa'] = min(estadisticas['diferencia_max_negativa'], diferencia)
                    
                    if pendiente is not None:
                        estadisticas['pendiente_max'] = max(estadisticas['pendiente_max'], pendiente)
                        estadisticas['pendiente_min'] = min(estadisticas['pendiente_min'], pendiente)
            
            return estadisticas
            
        except Exception as e:
            self.log_debug(f"Error obteniendo estadísticas: {str(e)}")
            return None