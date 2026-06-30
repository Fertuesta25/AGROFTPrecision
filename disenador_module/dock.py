# -*- coding: utf-8 -*-
"""
Dock widget: toda la interfaz (pestañas Parcelas / Carreteras / Plantas).

Responsabilidades: recoger valores de los widgets, validar (CRS, parámetros),
pedir confirmación en operaciones grandes, llamar a `algoritmos`, y presentar el
resultado (agregar capa, aplicar estilo/etiquetas, actualizar resúmenes, exportar).
La matemática y el procesamiento viven en algoritmos.py.
"""
import os
import traceback

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QColor
from qgis.PyQt.QtWidgets import (
    QDockWidget, QVBoxLayout, QGridLayout,
    QLabel, QLineEdit, QPushButton, QMessageBox,
    QRadioButton, QCheckBox, QWidget, QButtonGroup,
    QGroupBox, QScrollArea, QTabWidget,
    QProgressBar, QFileDialog, QApplication
)

from qgis.core import (
    QgsProject, QgsMapLayerProxyModel,
    QgsPalLayerSettings, QgsTextFormat, QgsVectorLayerSimpleLabeling,
    QgsTextBufferSettings, QgsVectorFileWriter,
    QgsLineSymbol, QgsCategorizedSymbolRenderer, QgsRendererCategory,
)
from qgis.gui import QgsMapLayerComboBox

from .utils import parse_float, parse_int, error_crs_metrico
from . import algoritmos


class GeneradorCuadriculaProDock(QDockWidget):
    def __init__(self, iface, plugin_dir):
        super().__init__()
        self.iface = iface
        self.plugin_dir = plugin_dir
        self._is_running = False
        self.point_tool = None
        self._ultima_capa_parcelas = None
        self._ultima_capa_cuadricula = None
        self._ultima_capa_ejes = None
        self._ultima_capa_vias = None
        self._ultima_capa_plantas = None

        self.setWindowTitle("Diseñador de Plantación PRO v3.0")
        self.setMinimumWidth(400)

        self.main_widget = QWidget()
        self.main_widget.setObjectName("ContenedorPrincipal")
        self.layout_principal = QVBoxLayout(self.main_widget)
        self.layout_principal.setContentsMargins(4, 4, 4, 4)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tab_parcelas = QWidget()
        self.tab_carreteras = QWidget()
        self.tab_plantas = QWidget()
        self.tabs.addTab(self.tab_parcelas, "PARCELAS")
        self.tabs.addTab(self.tab_carreteras, "CARRETERAS")
        self.tabs.addTab(self.tab_plantas, "PLANTAS")
        self.layout_principal.addWidget(self.tabs)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setRange(0, 100)
        self.layout_principal.addWidget(self.progress_bar)

        self.setWidget(self.main_widget)

        self.setup_tab_parcelas()
        self.setup_tab_carreteras()
        self.setup_tab_plantas()
        self.apply_native_style()

    # ------------------------------------------------------------------
    def apply_native_style(self):
        self.setStyleSheet("""
            QGroupBox { font-weight: bold; margin-top: 10px; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }
            QPushButton#btnGenerar { font-size: 13px; font-weight: bold; padding: 10px; margin-top: 8px; }
            QPushButton#btnSecundario { padding: 7px; font-weight: bold; }
            QPushButton#btnExportar { padding: 5px; }
            QLabel#valResumen { font-family: 'Consolas','Courier New',monospace; }
            QLabel#valResumenDestacado { font-family: 'Consolas','Courier New',monospace; font-size: 13px; font-weight: bold; }
        """)

    def cleanup(self):
        """Libera la herramienta de captura de punto al descargar el plugin."""
        if self.point_tool is not None:
            try:
                self.iface.mapCanvas().unsetMapTool(self.point_tool)
            except Exception:
                pass
            self.point_tool = None

    # ------------------------------------------------------------------
    #  Progreso / estado
    # ------------------------------------------------------------------
    def _set_busy(self, busy, button=None):
        self._is_running = busy
        if button:
            button.setEnabled(not busy)
        self.progress_bar.setVisible(busy)
        if busy:
            self.progress_bar.setValue(0)
        QApplication.processEvents()

    def _set_progress(self, value, text=None):
        self.progress_bar.setValue(int(value))
        if text:
            self.progress_bar.setFormat(text)
        QApplication.processEvents()

    # ==================================================================
    #  TAB PARCELAS
    # ==================================================================
    def setup_tab_parcelas(self):
        layout = QVBoxLayout(self.tab_parcelas)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        sl = QVBoxLayout(content)

        grp_layer = QGroupBox("Capa de Referencia")
        ll = QVBoxLayout(grp_layer)
        self.layer_combo = QgsMapLayerComboBox()
        self.layer_combo.setFilters(QgsMapLayerProxyModel.Filter.PolygonLayer)
        self.layer_combo.setToolTip("Capa poligonal que define el área de plantación")
        ll.addWidget(self.layer_combo)
        sl.addWidget(grp_layer)

        grp_geo = QGroupBox("Parámetros de Diseño")
        lg = QGridLayout(grp_geo)
        lg.addWidget(QLabel("Espaciado H (m):"), 0, 0)
        self.h_spacing = QLineEdit("1500")
        self.h_spacing.setToolTip("Ancho horizontal de cada bloque (ej: 1500 m)")
        lg.addWidget(self.h_spacing, 0, 1)
        lg.addWidget(QLabel("Espaciado V (m):"), 1, 0)
        self.v_spacing = QLineEdit("300")
        self.v_spacing.setToolTip("Alto vertical de cada subfila (ej: 300 m)")
        lg.addWidget(self.v_spacing, 1, 1)
        lg.addWidget(QLabel("Subdivisiones:"), 2, 0)
        self.subdivisiones = QLineEdit("4")
        self.subdivisiones.setToolTip("Subfilas por fila (ej: 4 -> a,b,c,d)")
        lg.addWidget(self.subdivisiones, 2, 1)
        sl.addWidget(grp_geo)

        grp_opt = QGroupBox("Configuración de Salida")
        lo = QVBoxLayout(grp_opt)
        self.rb_desc = QRadioButton("Sentido: Norte a Sur")
        self.rb_asc = QRadioButton("Sentido: Sur a Norte")
        self.rb_asc.setChecked(True)
        self.dir_group = QButtonGroup(self)
        self.dir_group.addButton(self.rb_desc)
        self.dir_group.addButton(self.rb_asc)
        self.recortar_checkbox = QCheckBox("Recortar al límite del polígono")
        self.recortar_checkbox.setChecked(True)
        self.etiquetar_checkbox = QCheckBox("Activar etiquetas (campo Parcela)")
        self.etiquetar_checkbox.setChecked(True)
        self.output_name = QLineEdit("cuadricula_oilpalm")
        lo.addWidget(self.rb_desc)
        lo.addWidget(self.rb_asc)
        lo.addWidget(QLabel("Nombre de la capa:"))
        lo.addWidget(self.output_name)
        lo.addWidget(self.recortar_checkbox)
        lo.addWidget(self.etiquetar_checkbox)
        sl.addWidget(grp_opt)

        self.btn_generar = QPushButton("GENERAR DISEÑO DE PARCELAS")
        self.btn_generar.setObjectName("btnGenerar")
        self.btn_generar.clicked.connect(self.generar_cuadricula)
        sl.addWidget(self.btn_generar)

        self.btn_export_parcelas = QPushButton("💾 Exportar (GeoPackage / Shapefile)")
        self.btn_export_parcelas.setObjectName("btnExportar")
        self.btn_export_parcelas.clicked.connect(lambda: self._exportar_ultima_capa("parcelas"))
        sl.addWidget(self.btn_export_parcelas)

        self.grp_resumen = QGroupBox("Resumen del Diseño")
        lr = QGridLayout(self.grp_resumen)
        self.resumen_widgets = {}
        items = [("Num. Parcelas:", "num_parc"), ("Área Total (Ha):", "area_tot"),
                 ("Área Mín. (Ha):", "area_min"), ("Área Máx. (Ha):", "area_max"),
                 ("Promedio (Ha):", "area_prom")]
        for i, (txt, key) in enumerate(items):
            val = QLabel("-")
            val.setObjectName("valResumen")
            val.setAlignment(Qt.AlignmentFlag.AlignRight)
            lr.addWidget(QLabel(txt), i, 0)
            lr.addWidget(val, i, 1)
            self.resumen_widgets[key] = val
        sl.addWidget(self.grp_resumen)

        sl.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll)

    # ==================================================================
    #  TAB CARRETERAS
    # ==================================================================
    def setup_tab_carreteras(self):
        layout = QVBoxLayout(self.tab_carreteras)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        sl = QVBoxLayout(content)

        grp_ejes = QGroupBox("1. Extracción de Ejes Inteligentes")
        le = QVBoxLayout(grp_ejes)
        le.addWidget(QLabel("Capa de Parcelas:"))
        self.parcel_layer_combo = QgsMapLayerComboBox()
        self.parcel_layer_combo.setFilters(QgsMapLayerProxyModel.Filter.PolygonLayer)
        le.addWidget(self.parcel_layer_combo)
        le.addWidget(QLabel("Capa Límite del Fundo:"))
        self.boundary_layer_combo = QgsMapLayerComboBox()
        self.boundary_layer_combo.setFilters(QgsMapLayerProxyModel.Filter.PolygonLayer)
        le.addWidget(self.boundary_layer_combo)
        self.check_gen_colindancia = QCheckBox("Generar ejes en colindancia")
        self.check_gen_colindancia.setChecked(True)
        le.addWidget(self.check_gen_colindancia)
        self.btn_extraer_ejes = QPushButton("GENERAR EJES CLASIFICADOS")
        self.btn_extraer_ejes.setObjectName("btnSecundario")
        self.btn_extraer_ejes.clicked.connect(self.extraer_ejes)
        le.addWidget(self.btn_extraer_ejes)
        sl.addWidget(grp_ejes)

        grp_rod = QGroupBox("2. Configuración de Anchos de Vía")
        lr = QGridLayout(grp_rod)
        lr.addWidget(QLabel("Ejes Limpios:"), 0, 0)
        self.road_layer_combo = QgsMapLayerComboBox()
        self.road_layer_combo.setFilters(QgsMapLayerProxyModel.Filter.LineLayer)
        lr.addWidget(self.road_layer_combo, 0, 1)
        lr.addWidget(QLabel("Kilométrica (m):"), 1, 0)
        self.width_kilometrica = QLineEdit("8.0")
        lr.addWidget(self.width_kilometrica, 1, 1)
        lr.addWidget(QLabel("Parcelaria (m):"), 2, 0)
        self.width_parcelaria = QLineEdit("6.0")
        lr.addWidget(self.width_parcelaria, 2, 1)
        lr.addWidget(QLabel("Colindancia (m):"), 3, 0)
        self.width_colindancia = QLineEdit("6.0")
        lr.addWidget(self.width_colindancia, 3, 1)
        sl.addWidget(grp_rod)

        self.btn_generar_vias = QPushButton("GENERAR POLÍGONOS DE VÍAS")
        self.btn_generar_vias.setObjectName("btnGenerar")
        self.btn_generar_vias.clicked.connect(self.generar_vias)
        sl.addWidget(self.btn_generar_vias)

        self.grp_res_vias = QGroupBox("Estadísticas de Vialidad")
        lrv = QGridLayout(self.grp_res_vias)
        self.lbl_num_ejes = QLabel("-")
        self.lbl_long_total = QLabel("-")
        self.lbl_area_vias = QLabel("-")
        for w in (self.lbl_num_ejes, self.lbl_long_total, self.lbl_area_vias):
            w.setObjectName("valResumen")
        lrv.addWidget(QLabel("Nº Ejes:"), 0, 0)
        lrv.addWidget(self.lbl_num_ejes, 0, 1)
        lrv.addWidget(QLabel("Longitud Total (km):"), 1, 0)
        lrv.addWidget(self.lbl_long_total, 1, 1)
        lrv.addWidget(QLabel("Área Vías (Ha):"), 2, 0)
        lrv.addWidget(self.lbl_area_vias, 2, 1)
        sl.addWidget(self.grp_res_vias)

        self.btn_export_vias = QPushButton("💾 Exportar Vías (GeoPackage / Shapefile)")
        self.btn_export_vias.setObjectName("btnExportar")
        self.btn_export_vias.clicked.connect(lambda: self._exportar_ultima_capa("vias"))
        sl.addWidget(self.btn_export_vias)

        sl.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll)

    # ==================================================================
    #  TAB PLANTAS
    # ==================================================================
    def setup_tab_plantas(self):
        layout = QVBoxLayout(self.tab_plantas)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        sl = QVBoxLayout(content)

        grp_siembra = QGroupBox("Configuración de Siembra")
        ls = QGridLayout(grp_siembra)
        ls.addWidget(QLabel("Capa Límite (Fundo):"), 0, 0)
        self.plant_boundary_combo = QgsMapLayerComboBox()
        self.plant_boundary_combo.setFilters(QgsMapLayerProxyModel.Filter.PolygonLayer)
        ls.addWidget(self.plant_boundary_combo, 0, 1)
        ls.addWidget(QLabel("Capa Cuadrícula:"), 1, 0)
        self.plant_grid_combo = QgsMapLayerComboBox()
        self.plant_grid_combo.setFilters(QgsMapLayerProxyModel.Filter.PolygonLayer)
        self.plant_grid_combo.setAllowEmptyLayer(True)
        self.plant_grid_combo.setToolTip(
            "Cuadrícula completa (capa '<nombre>_cuadricula') con el campo 'parcela'. "
            "Define la malla regular sobre la que se numeran las líneas (Oeste->Este) "
            "y las plantas (Sur->Norte)."
        )
        ls.addWidget(self.plant_grid_combo, 1, 1)
        ls.addWidget(QLabel("Capa de Parcelas (recorte):"), 2, 0)
        self.plant_parcels_combo = QgsMapLayerComboBox()
        self.plant_parcels_combo.setFilters(QgsMapLayerProxyModel.Filter.PolygonLayer)
        self.plant_parcels_combo.setAllowEmptyLayer(True)
        self.plant_parcels_combo.setToolTip(
            "Parcelas recortadas al fundo. Tras numerar, se borran las plantas que "
            "NO se superponen con esta capa. Si se deja vacía, se usa el límite del fundo."
        )
        ls.addWidget(self.plant_parcels_combo, 2, 1)
        ls.addWidget(QLabel("Capa de Vías (excluir):"), 3, 0)
        self.plant_roads_combo = QgsMapLayerComboBox()
        self.plant_roads_combo.setFilters(QgsMapLayerProxyModel.Filter.PolygonLayer)
        self.plant_roads_combo.setAllowEmptyLayer(True)
        ls.addWidget(self.plant_roads_combo, 3, 1)
        ls.addWidget(QLabel("Distancia S-N (m):"), 4, 0)
        self.dist_siembra = QLineEdit("9.0")
        ls.addWidget(self.dist_siembra, 4, 1)
        sl.addWidget(grp_siembra)

        grp_inicio = QGroupBox("Punto de Inicio (Origen)")
        li = QGridLayout(grp_inicio)
        self.start_x = QLineEdit()
        self.start_x.setPlaceholderText("X (Este)")
        self.start_y = QLineEdit()
        self.start_y.setPlaceholderText("Y (Norte)")
        btn_pick = QPushButton("📍 Capturar en Mapa")
        btn_pick.setObjectName("btnSecundario")
        btn_pick.clicked.connect(self.activar_captura_punto)
        li.addWidget(QLabel("Coord X:"), 0, 0)
        li.addWidget(self.start_x, 0, 1)
        li.addWidget(QLabel("Coord Y:"), 1, 0)
        li.addWidget(self.start_y, 1, 1)
        li.addWidget(btn_pick, 2, 0, 1, 2)
        sl.addWidget(grp_inicio)

        self.btn_generar_plantas = QPushButton("GENERAR PUNTOS (TRESBOLILLO)")
        self.btn_generar_plantas.setObjectName("btnGenerar")
        self.btn_generar_plantas.clicked.connect(self.generar_puntos_tresbolillo)
        sl.addWidget(self.btn_generar_plantas)

        self.btn_export_plantas = QPushButton("💾 Exportar Plantas (GeoPackage / Shapefile)")
        self.btn_export_plantas.setObjectName("btnExportar")
        self.btn_export_plantas.clicked.connect(lambda: self._exportar_ultima_capa("plantas"))
        sl.addWidget(self.btn_export_plantas)

        self.grp_res_plantas = QGroupBox("Resumen")
        lrp = QGridLayout(self.grp_res_plantas)
        self.lbl_total_plantas = QLabel("-")
        self.lbl_total_plantas.setObjectName("valResumenDestacado")
        self.lbl_densidad = QLabel("-")
        self.lbl_densidad.setObjectName("valResumen")
        lrp.addWidget(QLabel("Total de Plantas:"), 0, 0)
        lrp.addWidget(self.lbl_total_plantas, 0, 1)
        lrp.addWidget(QLabel("Densidad (plantas/Ha):"), 1, 0)
        lrp.addWidget(self.lbl_densidad, 1, 1)
        sl.addWidget(self.grp_res_plantas)

        sl.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll)

    # ==================================================================
    #  Estilos / etiquetas (presentación)
    # ==================================================================
    def activar_etiquetado(self, capa):
        settings = QgsPalLayerSettings()
        settings.fieldName = "parcela"
        settings.placement = QgsPalLayerSettings.Placement.Horizontal
        text_format = QgsTextFormat()
        text_format.setSize(9)
        text_format.setColor(QColor(255, 255, 255))
        buf = QgsTextBufferSettings()
        buf.setEnabled(True)
        buf.setSize(1.0)
        buf.setColor(QColor(0, 0, 0, 180))
        text_format.setBuffer(buf)
        settings.setFormat(text_format)
        capa.setLabeling(QgsVectorLayerSimpleLabeling(settings))
        capa.setLabelsEnabled(True)
        capa.triggerRepaint()

    def aplicar_estilo_ejes(self, capa):
        estilos = {
            "Kilometrica": ("#c0392b", "0.8"),
            "Parcelaria": ("#2980b9", "0.5"),
            "Colindancia": ("#27ae60", "0.5"),
        }
        categorias = []
        for tipo, (color, width) in estilos.items():
            sym = QgsLineSymbol.createSimple({'color': color, 'width': width})
            categorias.append(QgsRendererCategory(tipo, sym, tipo))
        capa.setRenderer(QgsCategorizedSymbolRenderer("tipo", categorias))
        capa.triggerRepaint()

    def actualizar_resumen_parcelas(self, stats):
        if not stats:
            return
        self.resumen_widgets["num_parc"].setText(f"{stats['num']}")
        self.resumen_widgets["area_tot"].setText(f"{stats['total']:,.2f}")
        self.resumen_widgets["area_min"].setText(f"{stats['min']:,.4f}")
        self.resumen_widgets["area_max"].setText(f"{stats['max']:,.4f}")
        self.resumen_widgets["area_prom"].setText(f"{stats['prom']:,.4f}")

    # ==================================================================
    #  ACCIONES
    # ==================================================================
    def generar_cuadricula(self):
        if self._is_running:
            return
        capa = self.layer_combo.currentLayer()
        if not capa:
            QMessageBox.warning(self, "Atención", "Seleccione una capa poligonal de referencia.")
            return
        err = error_crs_metrico(capa)
        if err:
            QMessageBox.warning(self, "CRS no válido", err)
            return
        try:
            esp_h = parse_float(self.h_spacing.text(), "Espaciado H")
            esp_v = parse_float(self.v_spacing.text(), "Espaciado V")
            subdiv = parse_int(self.subdivisiones.text(), "Subdivisiones")
        except ValueError as e:
            QMessageBox.warning(self, "Parámetro inválido", str(e))
            return
        if subdiv > 26:
            QMessageBox.warning(self, "Límite excedido", "Subdivisiones máximo: 26 (a-z).")
            return

        _, _, total = algoritmos.estimar_celdas(capa.extent(), esp_h, esp_v, subdiv)
        if total > 50000:
            resp = QMessageBox.question(
                self, "Advertencia", f"Se generarán {total:,} celdas. ¿Continuar?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if resp == QMessageBox.StandardButton.No:
                return

        self._set_busy(True, self.btn_generar)
        try:
            nombre = self.output_name.text().strip() or "cuadricula"
            recortar = self.recortar_checkbox.isChecked()
            capa_final, capa_cuadricula, stats = algoritmos.generar_parcelas(
                capa, esp_h, esp_v, subdiv,
                sentido_desc=self.rb_desc.isChecked(),
                recortar=recortar,
                nombre=nombre, progress=self._set_progress
            )
            # Cuadrícula completa (sin recortar) como capa de referencia. Solo se
            # agrega aparte cuando hubo recorte; si no, sería idéntica a la final.
            if recortar:
                QgsProject.instance().addMapLayer(capa_cuadricula)
            if self.etiquetar_checkbox.isChecked():
                self.activar_etiquetado(capa_final)
            QgsProject.instance().addMapLayer(capa_final)
            self.actualizar_resumen_parcelas(stats)
            self._ultima_capa_parcelas = capa_final
            self._ultima_capa_cuadricula = capa_cuadricula
            msg = f"Parcelas generadas: {capa_final.featureCount()}"
            if recortar:
                msg += f" (+ cuadrícula completa: {capa_cuadricula.featureCount()})"
            self.iface.messageBar().pushSuccess("Éxito", msg)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error generando parcelas:\n{e}\n\n{traceback.format_exc()}")
        finally:
            self._set_busy(False, self.btn_generar)

    def extraer_ejes(self):
        if self._is_running:
            return
        capa_parcelas = self.parcel_layer_combo.currentLayer()
        capa_limite = self.boundary_layer_combo.currentLayer()
        if not capa_parcelas:
            QMessageBox.warning(self, "Atención", "Seleccione una capa de parcelas.")
            return
        err = error_crs_metrico(capa_parcelas)
        if err:
            QMessageBox.warning(self, "CRS no válido", err)
            return

        self._set_busy(True, self.btn_extraer_ejes)
        try:
            ejes, stats = algoritmos.extraer_ejes(
                capa_parcelas, capa_limite,
                gen_colindancia=self.check_gen_colindancia.isChecked(),
                progress=self._set_progress
            )
            self.aplicar_estilo_ejes(ejes)
            QgsProject.instance().addMapLayer(ejes)
            self.road_layer_combo.setLayer(ejes)
            self._ultima_capa_ejes = ejes
            self.lbl_num_ejes.setText(f"{stats['num_ejes']}")
            self.lbl_long_total.setText(f"{stats['long_km']:,.3f} km")
            self.iface.messageBar().pushSuccess("Éxito", f"Ejes clasificados: {stats['num_ejes']}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error extrayendo ejes:\n{e}\n\n{traceback.format_exc()}")
        finally:
            self._set_busy(False, self.btn_extraer_ejes)

    def generar_vias(self):
        if self._is_running:
            return
        capa_ejes = self.road_layer_combo.currentLayer()
        capa_fundo = self.boundary_layer_combo.currentLayer()
        if not capa_ejes:
            QMessageBox.warning(self, "Atención", "Seleccione una capa de ejes.")
            return
        try:
            w_k = parse_float(self.width_kilometrica.text(), "Kilométrica")
            w_p = parse_float(self.width_parcelaria.text(), "Parcelaria")
            w_c = parse_float(self.width_colindancia.text(), "Colindancia")
        except ValueError as e:
            QMessageBox.warning(self, "Parámetro inválido", str(e))
            return

        self._set_busy(True, self.btn_generar_vias)
        try:
            capa_vias, stats = algoritmos.generar_vias(
                capa_ejes, capa_fundo, w_k, w_p, w_c, progress=self._set_progress
            )
            QgsProject.instance().addMapLayer(capa_vias)
            self._ultima_capa_vias = capa_vias
            self.lbl_long_total.setText(f"{stats['long_km']:,.3f} km")
            self.lbl_area_vias.setText(f"{stats['area_ha']:,.4f} Ha")
            self.iface.messageBar().pushSuccess("Éxito", "Vías generadas correctamente.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error generando vías:\n{e}\n\n{traceback.format_exc()}")
        finally:
            self._set_busy(False, self.btn_generar_vias)

    # ------------------------------------------------------------------
    #  Captura de punto
    # ------------------------------------------------------------------
    def activar_captura_punto(self):
        from qgis.gui import QgsMapToolEmitPoint
        canvas = self.iface.mapCanvas()
        self.point_tool = QgsMapToolEmitPoint(canvas)
        self.point_tool.canvasClicked.connect(self.set_punto_inicio)
        canvas.setMapTool(self.point_tool)
        self.iface.messageBar().pushInfo("Captura", "Haga clic en el mapa para definir el punto de inicio.")

    def set_punto_inicio(self, point, button):
        self.start_x.setText(str(round(point.x(), 3)))
        self.start_y.setText(str(round(point.y(), 3)))
        self.iface.mapCanvas().unsetMapTool(self.point_tool)
        self.point_tool = None
        self.iface.messageBar().pushSuccess("Punto capturado", f"X={point.x():.3f}, Y={point.y():.3f}")

    # ------------------------------------------------------------------
    #  Tresbolillo
    # ------------------------------------------------------------------
    def generar_puntos_tresbolillo(self):
        if self._is_running:
            return
        capa_limite = self.plant_boundary_combo.currentLayer()
        if not capa_limite:
            QMessageBox.warning(self, "Atención", "Seleccione la capa límite del fundo.")
            return
        err = error_crs_metrico(capa_limite)
        if err:
            QMessageBox.warning(self, "CRS no válido", err)
            return
        if not self.start_x.text().strip() or not self.start_y.text().strip():
            QMessageBox.warning(self, "Atención", "Defina el punto de inicio (X, Y). Use '📍 Capturar en Mapa'.")
            return
        try:
            d = parse_float(self.dist_siembra.text(), "Distancia S-N")
            x0 = float(self.start_x.text().replace(',', '.'))
            y0 = float(self.start_y.text().replace(',', '.'))
        except ValueError as e:
            QMessageBox.warning(self, "Parámetro inválido", str(e))
            return

        total_estimado = algoritmos.estimar_puntos_grid(capa_limite.extent(), d, x0, y0)
        if total_estimado > 5_000_000:
            resp = QMessageBox.question(
                self, "Advertencia", f"Se evaluarán ~{total_estimado:,} puntos. ¿Continuar?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if resp == QMessageBox.StandardButton.No:
                return

        self._set_busy(True, self.btn_generar_plantas)
        try:
            capa_vias_excl = self.plant_roads_combo.currentLayer()
            capa_parcelas = self.plant_parcels_combo.currentLayer()
            capa_cuadricula = self.plant_grid_combo.currentLayer()
            capa_puntos, stats = algoritmos.generar_tresbolillo(
                capa_limite, capa_vias_excl, d, x0, y0,
                capa_cuadricula=capa_cuadricula, capa_parcelas=capa_parcelas,
                progress=self._set_progress
            )
            QgsProject.instance().addMapLayer(capa_puntos)
            self._ultima_capa_plantas = capa_puntos
            self.lbl_total_plantas.setText(f"{stats['total']:,}")
            if stats["densidad"] is not None:
                self.lbl_densidad.setText(f"{stats['densidad']:,.1f}")
            else:
                self.lbl_densidad.setText("-")
            self.iface.messageBar().pushSuccess("Éxito", f"Plantas generadas: {stats['total']:,}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error generando plantas:\n{e}\n\n{traceback.format_exc()}")
        finally:
            self._set_busy(False, self.btn_generar_plantas)

    # ------------------------------------------------------------------
    #  Exportación (GeoPackage por defecto, Shapefile opcional)
    # ------------------------------------------------------------------
    def _exportar_ultima_capa(self, tipo):
        capas = {
            "parcelas": (self._ultima_capa_parcelas, "parcelas"),
            "vias": (self._ultima_capa_vias, "vias"),
            "plantas": (self._ultima_capa_plantas, "plantas"),
        }
        capa, nombre_default = capas.get(tipo, (None, tipo))
        if not capa:
            QMessageBox.information(self, "Sin datos", f"No hay capa de {tipo} generada. Genere primero.")
            return

        path, _ = QFileDialog.getSaveFileName(
            self, f"Guardar {tipo}",
            os.path.expanduser(f"~/{nombre_default}.gpkg"),
            "GeoPackage (*.gpkg);;Shapefile (*.shp)"
        )
        if not path:
            return

        options = QgsVectorFileWriter.SaveVectorOptions()
        options.fileEncoding = "UTF-8"
        if path.lower().endswith(".shp"):
            options.driverName = "ESRI Shapefile"
        else:
            if not path.lower().endswith(".gpkg"):
                path += ".gpkg"
            options.driverName = "GPKG"

        result = QgsVectorFileWriter.writeAsVectorFormatV3(
            capa, path, QgsProject.instance().transformContext(), options
        )
        if result[0] == QgsVectorFileWriter.WriterError.NoError:
            self.iface.messageBar().pushSuccess("Exportado", f"Archivo guardado en: {path}")
        else:
            QMessageBox.critical(self, "Error de exportación", f"No se pudo guardar: {result[1]}")
