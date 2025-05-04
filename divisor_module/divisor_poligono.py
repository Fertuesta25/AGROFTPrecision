from qgis.PyQt.QtCore import Qt, QEventLoop, QVariant
from qgis.PyQt.QtWidgets import QAction, QMessageBox, QInputDialog
from qgis.PyQt.QtGui import QIcon
from qgis.core import (
    QgsProject, QgsVectorLayer, QgsGeometry, QgsWkbTypes,
    QgsField, QgsFeature, QgsUnitTypes, QgsDistanceArea,
    QgsVectorLayerSimpleLabeling, QgsPalLayerSettings,
    QgsTextFormat, QgsRectangle, QgsPointXY, QgsSnappingConfig,
    QgsTolerance, QgsMapLayer, QgsCoordinateTransform
)
from qgis.gui import QgsMapToolEmitPoint, QgsRubberBand, QgsSnapIndicator
from qgis.utils import iface
import math
import os

class HerramientaDibujoLinea(QgsMapToolEmitPoint):
    def __init__(self, lienzo, callback):
        super().__init__(lienzo)
        self.lienzo = lienzo
        self.callback = callback
        self.puntos = []
        self.banda_elastica = QgsRubberBand(lienzo, QgsWkbTypes.LineGeometry)
        self.banda_elastica.setColor(Qt.red)
        self.banda_elastica.setWidth(2)
        
        self.utilidades_ajuste = lienzo.snappingUtils()
        self.config_ajuste = QgsSnappingConfig()
        self.config_ajuste.setMode(QgsSnappingConfig.AdvancedConfiguration)
        self.config_ajuste.setEnabled(True)
        
        raiz = QgsProject.instance().layerTreeRoot()
        capas_visibles = []
        for capa_arbol in raiz.findLayers():
            if capa_arbol.isVisible():
                capa = capa_arbol.layer()
                if capa is not None and capa.type() == QgsMapLayer.VectorLayer:
                    capas_visibles.append(capa)
        
        for capa in capas_visibles:
            configuracion = QgsSnappingConfig.IndividualLayerSettings(
                True, QgsSnappingConfig.Vertex, 10, QgsTolerance.Pixels
            )
            self.config_ajuste.setIndividualLayerSettings(capa, configuracion)
        
        self.utilidades_ajuste.setConfig(self.config_ajuste)
        self.indicador_ajuste = QgsSnapIndicator(lienzo)
        iface.messageBar().pushInfo("Acción Requerida", "Haga clic en dos puntos para dibujar la línea de dirección (se ajusta a los puntos de las capas visibles)")

    def canvasMoveEvent(self, evento):
        pos_mapa = self.toMapCoordinates(evento.pos())
        coincidencia = self.utilidades_ajuste.snapToMap(pos_mapa)
        self.indicador_ajuste.setMatch(coincidencia)
        if len(self.puntos) == 1:
            self.banda_elastica.reset(QgsWkbTypes.LineGeometry)
            self.banda_elastica.addPoint(self.puntos[0])
            if coincidencia.isValid():
                self.banda_elastica.addPoint(coincidencia.point())
            else:
                self.banda_elastica.addPoint(pos_mapa)

    def canvasReleaseEvent(self, evento):
        pos_mapa = self.toMapCoordinates(evento.pos())
        coincidencia = self.utilidades_ajuste.snapToMap(pos_mapa)
        punto = coincidencia.point() if coincidencia.isValid() else pos_mapa
        self.puntos.append(punto)
        if len(self.puntos) == 1:
            self.banda_elastica.addPoint(punto)
            iface.messageBar().pushInfo("Acción Requerida", "Haga clic en el segundo punto para la línea de dirección")
        elif len(self.puntos) == 2:
            self.banda_elastica.reset()
            self.lienzo.unsetMapTool(self)
            self.callback(self.puntos)

class HerramientaSeleccionPunto(QgsMapToolEmitPoint):
    def __init__(self, lienzo, callback):
        super().__init__(lienzo)
        self.lienzo = lienzo
        self.callback = callback
        iface.messageBar().pushInfo("Acción Requerida", "Haga clic en el polígono para elegir el lado inicial")

    def canvasReleaseEvent(self, evento):
        punto = self.toMapCoordinates(evento.pos())
        self.lienzo.unsetMapTool(self)
        self.callback(punto)

class DivisorPoligono:
    def __init__(self, iface):
        self.iface = iface
        self.lienzo = iface.mapCanvas()
        self.acciones = []
        self.menu = "&Equalizador"
        self.barra_herramientas = None
        self.puntos_actuales = None
        self.punto_clic = None

    def initGui(self, crear_barra=True):
        """
        Inicializa la interfaz gráfica del plugin
        
        :param crear_barra: Si es True, crea una barra de herramientas propia con sus propias acciones
        """
        # Solo si queremos que funcione como plugin independiente
        if crear_barra:
            self.barra_herramientas = self.iface.addToolBar("Equalizador")
            
            # Crear acciones para el plugin independiente
            dir_script = os.path.dirname(__file__)
            
            # Acción para dividir en áreas iguales
            ruta_icono = os.path.join(dir_script, 'icon_area.png')
            self.accion_area_igual = QAction(
                QIcon(ruta_icono),
                "Dividir en Áreas Iguales",
                self.iface.mainWindow()
            )
            self.accion_area_igual.triggered.connect(lambda: self.iniciar_division('area'))
            
            # Acción para dividir en partes iguales
            ruta_icono = os.path.join(dir_script, 'icon_count.png')
            self.accion_partes_iguales = QAction(
                QIcon(ruta_icono),
                "Dividir en Partes Iguales",
                self.iface.mainWindow()
            )
            self.accion_partes_iguales.triggered.connect(lambda: self.iniciar_division('conteo'))
            
            # Añadir acciones a la barra y al menú
            self.iface.addPluginToMenu(self.menu, self.accion_area_igual)
            self.iface.addPluginToMenu(self.menu, self.accion_partes_iguales)
            self.barra_herramientas.addAction(self.accion_area_igual)
            self.barra_herramientas.addAction(self.accion_partes_iguales)
            
            # Guardar referencia a las acciones
            self.acciones.append(self.accion_area_igual)
            self.acciones.append(self.accion_partes_iguales)

    def unload(self):
        for accion in self.acciones:
            self.iface.removePluginMenu(self.menu, accion)
            self.iface.removeToolBarIcon(accion)
        del self.barra_herramientas

    def iniciar_division(self, modo):
        try:
            self.modo = modo
            self.dividir_poligono()
        except Exception as e:
            QMessageBox.critical(None, "Error", str(e))

    def descomponer_multipartes(self, geoms):
        descompuestos = []
        for geom in geoms:
            if geom.isMultipart():
                for parte in geom.asMultiPolygon():
                    descompuestos.append(QgsGeometry.fromPolygonXY(parte))
            elif geom.wkbType() == QgsWkbTypes.GeometryCollection:
                for subgeom in geom.constGet():
                    g = QgsGeometry(subgeom)
                    if g.type() == QgsWkbTypes.PolygonGeometry:
                        descompuestos.append(g)
            else:
                descompuestos.append(geom)
        return descompuestos

    def limpiar_geometria(self, geom):
        """
        Si una geometría es una GeometryCollection, intenta limpiarla para que sea un multipolígono válido.
        Usa un truco de buffer cero primero, luego descompone y recombina las partes del polígono.
        """
        if geom.isEmpty():
            return geom
        if geom.wkbType() == QgsWkbTypes.GeometryCollection:
            limpiado = geom.buffer(0, 0)
            if limpiado and limpiado.wkbType() != QgsWkbTypes.GeometryCollection:
                return limpiado
            partes = []
            for subgeom in geom.constGet():
                g = QgsGeometry(subgeom)
                if g.type() == QgsWkbTypes.PolygonGeometry:
                    partes.append(g)
            if partes:
                union_geom = partes[0]
                for parte in partes[1:]:
                    union_geom = union_geom.combine(parte)
                return union_geom
        return geom

    def obtener_puntos_linea(self):
        bucle = QEventLoop()
        def callback(puntos):
            self.puntos_actuales = puntos
            bucle.quit()
        herramienta = HerramientaDibujoLinea(self.lienzo, callback)
        self.lienzo.setMapTool(herramienta)
        herramienta.deactivated.connect(bucle.quit)
        bucle.exec_()

    def obtener_punto_clic(self):
        bucle = QEventLoop()
        def callback(punto):
            self.punto_clic = punto
            bucle.quit()
        herramienta = HerramientaSeleccionPunto(self.lienzo, callback)
        self.lienzo.setMapTool(herramienta)
        herramienta.deactivated.connect(bucle.quit)
        bucle.exec_()

    def dividir_poligono(self):
        capa = self.iface.activeLayer()
        if not capa or capa.type() != QgsMapLayer.VectorLayer:
            raise Exception("Por favor seleccione una capa vectorial.")

        if capa.selectedFeatureCount() == 0:
            if capa.featureCount() == 1:
                entidad = next(capa.getFeatures())
                if entidad.geometry().type() == QgsWkbTypes.PolygonGeometry:
                    capa.select(entidad.id())
                    self.iface.messageBar().pushInfo("Aviso", "Se seleccionó automáticamente el único polígono en la capa")
                else:
                    raise Exception("La capa contiene una sola entidad, pero no es un polígono.")
            else:
                raise Exception("Por favor seleccione exactamente un polígono.")

        if capa.selectedFeatureCount() != 1:
            raise Exception("Por favor seleccione exactamente un polígono.")

        entidad_seleccionada = capa.selectedFeatures()[0]
        geom_original = entidad_seleccionada.geometry().makeValid()
        if geom_original.isEmpty() or not geom_original.isGeosValid():
            raise Exception("Geometría seleccionada no válida.")

        # Inicializar el área de distancia para una medición precisa del área
        da = QgsDistanceArea()
        da.setEllipsoid(QgsProject.instance().ellipsoid())
        da.setSourceCrs(capa.crs(), QgsProject.instance().transformContext())

        area_original_medida = da.measureArea(geom_original)
        unidad_area_proyecto = QgsProject.instance().areaUnits()
        if da.willUseEllipsoid():
            area_original = QgsUnitTypes.fromUnitToUnitFactor(QgsUnitTypes.AreaSquareMeters, unidad_area_proyecto) * area_original_medida
        else:
            unidad_distancia_crs = capa.crs().mapUnits()
            if unidad_distancia_crs == QgsUnitTypes.DistanceMeters:
                unidad_area_crs = QgsUnitTypes.AreaSquareMeters
            elif unidad_distancia_crs == QgsUnitTypes.DistanceFeet:
                unidad_area_crs = QgsUnitTypes.AreaSquareFeet
            else:
                unidad_area_crs = QgsUnitTypes.AreaSquareMeters
            area_original = QgsUnitTypes.fromUnitToUnitFactor(unidad_area_crs, unidad_area_proyecto) * area_original_medida

        if self.modo == "area":
            unidad_proyecto = QgsProject.instance().areaUnits()
            abrev_unidad = QgsUnitTypes.toAbbreviatedString(unidad_proyecto)
            indicacion = (
                f"Área total: {area_original:.2f} {abrev_unidad}\n"
                f"Ingrese el área objetivo por parte ({abrev_unidad}):"
            )
            entrada_area_esperada, ok = QInputDialog.getDouble(
                None, 
                "Área Igual", 
                indicacion,
                value=1000.0, 
                min=0.1, 
                max=area_original, 
                decimals=1
            )
            if not ok or entrada_area_esperada <= 0:
                return
            partes_estimadas = math.ceil(area_original / entrada_area_esperada)
            if partes_estimadas > 1000:
                msg = QMessageBox(
                    QMessageBox.Warning,
                    "Alto Número de Particiones",
                    f"Estimadas {partes_estimadas} partes. Esto puede causar problemas de rendimiento.\n¿Continuar?",
                    QMessageBox.Yes | QMessageBox.No
                )
                if msg.exec_() == QMessageBox.No:
                    self.iface.messageBar().pushInfo("Cancelado", "Operación abortada por el usuario")
                    return
            if da.willUseEllipsoid():
                area_esperada = QgsUnitTypes.fromUnitToUnitFactor(unidad_proyecto, QgsUnitTypes.AreaSquareMeters) * entrada_area_esperada
            else:
                area_esperada = QgsUnitTypes.fromUnitToUnitFactor(unidad_proyecto, unidad_area_crs) * entrada_area_esperada
            num_partes = None
        else:
            max_partes = max(2, min(1000, int(area_original / 0.1)))
            unidad_proyecto = QgsProject.instance().areaUnits()
            abrev_unidad = QgsUnitTypes.toAbbreviatedString(unidad_proyecto)
            indicacion = (
                f"Área total: {area_original:.2f} {abrev_unidad}\n"
                "Ingrese el número de partes:"
            )
            num_partes, ok = QInputDialog.getInt(
                None, 
                "Partes Iguales", 
                indicacion,
                value=2, 
                min=2, 
                max=max_partes
            )
            if not ok or num_partes < 1:
                return
            area_esperada = area_original_medida / num_partes

        # Obtener la línea de dirección y transformar al CRS de la capa si es necesario
        self.obtener_puntos_linea()
        if not self.puntos_actuales or len(self.puntos_actuales) != 2:
            raise Exception("¡La línea de dirección no se dibujó correctamente!")
        punto_a, punto_b = self.puntos_actuales
        if self.lienzo.mapSettings().destinationCrs() != capa.crs():
            transformacion = QgsCoordinateTransform(self.lienzo.mapSettings().destinationCrs(), capa.crs(), QgsProject.instance())
            punto_a = transformacion.transform(punto_a)
            punto_b = transformacion.transform(punto_b)
        
        # Modo área: ajustar basado en el punto cliqueado
        if self.modo == "area":
            self.obtener_punto_clic()
            if not self.punto_clic:
                raise Exception("¡No se seleccionó ningún punto!")
            punto_cliqueado = self.punto_clic
            if self.lienzo.mapSettings().destinationCrs() != capa.crs():
                punto_cliqueado = transformacion.transform(punto_cliqueado)
            if not geom_original.intersects(QgsGeometry.fromPointXY(punto_cliqueado)):
                raise Exception("¡El punto cliqueado no está en el polígono!")
            centro = QgsPointXY((punto_a.x() + punto_b.x())/2, (punto_a.y() + punto_b.y())/2)
            dx = punto_b.x() - punto_a.x()
            dy = punto_b.y() - punto_a.y()
            angulo_rad = math.atan2(dy, dx)
            angulo_deg = math.degrees(angulo_rad)
            geom_cliqueada = QgsGeometry.fromPointXY(punto_cliqueado)
            geom_cliqueada.rotate(angulo_deg, centro)
            cliqueado_rotado = geom_cliqueada.asPoint()
            original_rotado = QgsGeometry(geom_original)
            original_rotado.rotate(angulo_deg, centro)
            bbox = original_rotado.boundingBox()
            medio_y = (bbox.yMinimum() + bbox.yMaximum()) / 2
            if cliqueado_rotado.y() > medio_y:
                punto_a, punto_b = punto_b, punto_a

        centro = QgsPointXY((punto_a.x() + punto_b.x())/2, (punto_a.y() + punto_b.y())/2)
        dx = punto_b.x() - punto_a.x()
        dy = punto_b.y() - punto_a.y()
        angulo_rad = math.atan2(dy, dx)
        angulo_deg = -math.degrees(angulo_rad)

        def dividir_geometria(geom, angulo_deg, punto_central, area_objetivo):
            partes = []
            geom_restante = geom
            area_total = da.measureArea(geom_restante)
            while area_total >= area_objetivo * 0.99:
                geom_rotada = QgsGeometry(geom_restante)
                geom_rotada.rotate(-angulo_deg, punto_central)
                bbox = geom_rotada.boundingBox()
                bajo = bbox.yMinimum()
                alto = bbox.yMaximum()
                mejor_y = alto
                for _ in range(20):
                    medio = (bajo + alto) / 2
                    rect_recorte = QgsRectangle(bbox.xMinimum(), bbox.yMinimum(), bbox.xMaximum(), medio)
                    geom_recorte = QgsGeometry.fromRect(rect_recorte)
                    parte_temp = geom_rotada.intersection(geom_recorte)
                    parte_temp = self.limpiar_geometria(parte_temp)
                    area_temp = da.measureArea(parte_temp)
                    if area_temp < area_objetivo:
                        bajo = medio
                    else:
                        alto = medio
                        mejor_y = alto
                recorte_final = QgsGeometry.fromRect(QgsRectangle(bbox.xMinimum(), bbox.yMinimum(), bbox.xMaximum(), mejor_y))
                recorte_final.rotate(angulo_deg, punto_central)
                parte_inferior = geom_restante.intersection(recorte_final)
                parte_inferior = self.limpiar_geometria(parte_inferior)
                parte_superior = geom_restante.difference(recorte_final)
                parte_superior = self.limpiar_geometria(parte_superior)
                area_inferior = da.measureArea(parte_inferior)
                if parte_inferior.isEmpty() or area_inferior < area_objetivo * 0.95:
                    break
                partes.append(parte_inferior)
                geom_restante = parte_superior
                area_total = da.measureArea(geom_restante)
            if not geom_restante.isEmpty() and da.measureArea(geom_restante) > 0.01:
                area_restante = da.measureArea(geom_restante)
                if partes and area_restante < (area_objetivo * 0.05):
                    partes[-1] = partes[-1].combine(geom_restante)
                else:
                    partes.append(geom_restante)
            return partes

        try:
            partes_divididas = dividir_geometria(geom_original, angulo_deg, centro, area_esperada)
            partes_divididas = self.descomponer_multipartes(partes_divididas)
            # Filtrar las partes con área cercana a cero
            partes_divididas = [parte for parte in partes_divididas if da.measureArea(parte) > 0.01]
        except Exception as e:
            raise Exception(f"Error en la división: {str(e)}")

        crs = capa.crs().authid()
        capa_salida = QgsVectorLayer(f"Polygon?crs={crs}", "Partes Divididas", "memory")
        proveedor = capa_salida.dataProvider()
        proveedor.addAttributes(capa.fields())
        capa_salida.updateFields()

        unidad_proyecto = QgsProject.instance().areaUnits()
        abrev_unidad = QgsUnitTypes.toAbbreviatedString(unidad_proyecto)
        atributos_originales = entidad_seleccionada.attributes()

        for parte in partes_divididas:
            entidad = QgsFeature(capa_salida.fields())
            entidad.setGeometry(parte)
            area = da.measureArea(parte)
            if da.willUseEllipsoid():
                area_convertida = QgsUnitTypes.fromUnitToUnitFactor(QgsUnitTypes.AreaSquareMeters, unidad_proyecto) * area
            else:
                unidad_distancia_crs = capa_salida.crs().mapUnits()
                if unidad_distancia_crs == QgsUnitTypes.DistanceMeters:
                    unidad_area_crs = QgsUnitTypes.AreaSquareMeters
                elif unidad_distancia_crs == QgsUnitTypes.DistanceFeet:
                    unidad_area_crs = QgsUnitTypes.AreaSquareFeet
                else:
                    unidad_area_crs = QgsUnitTypes.AreaSquareMeters
                area_convertida = QgsUnitTypes.fromUnitToUnitFactor(unidad_area_crs, unidad_proyecto) * area
            
            nuevos_atributos = atributos_originales.copy()
            entidad.setAttributes(nuevos_atributos)
            proveedor.addFeature(entidad)

        capa_salida.updateExtents()
        QgsProject.instance().addMapLayer(capa_salida)

        configuracion_etiqueta = QgsPalLayerSettings()
        configuracion_etiqueta.enabled = True
        configuracion_etiqueta.isExpression = True
        configuracion_etiqueta.fieldName = f"concat(round($area, 2), ' {abrev_unidad}')"
        formato_texto = QgsTextFormat()
        formato_texto.setSize(15)
        formato_texto.setColor(Qt.red)
        configuracion_etiqueta.setFormat(formato_texto)
        capa_salida.setLabeling(QgsVectorLayerSimpleLabeling(configuracion_etiqueta))
        capa_salida.setLabelsEnabled(True)
        capa_salida.triggerRepaint()

        msg_resultado = f"Se crearon {len(partes_divididas)} polígonos\n"
        if self.modo == "area":
            msg_resultado += f"Área objetivo: {entrada_area_esperada:.1f} {abrev_unidad}\n"
            if len(partes_divididas) > 1:
                area_restante = QgsUnitTypes.fromUnitToUnitFactor(
                    QgsUnitTypes.AreaSquareMeters if da.willUseEllipsoid() else unidad_area_crs,
                    unidad_proyecto
                ) * da.measureArea(partes_divididas[-1])
                msg_resultado += f"Área restante: {area_restante:.1f} {abrev_unidad}"
        else:
            msg_resultado += f"Partes solicitadas: {num_partes}\n"
            area_promedio = area_original / num_partes
            msg_resultado += f"Área promedio: {area_promedio:.1f} {abrev_unidad}\n"
            if len(partes_divididas) != num_partes:
                msg_resultado += f"Nota: Se dividió en {len(partes_divididas)} partes debido a restricciones de geometría"

        QMessageBox.information(None, "Éxito", msg_resultado)