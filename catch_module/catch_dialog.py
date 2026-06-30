# -*- coding: utf-8 -*-
"""Diálogo principal del plugin: matriz regular, aspersor, datos de campo y solape."""
import os
import numpy as np

from qgis.PyQt.QtCore import Qt, QRect
from qgis.PyQt.QtGui import QColor, QFont, QImage, QPainter
from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox, QLabel,
    QSpinBox, QDoubleSpinBox, QComboBox, QPushButton, QTableWidget,
    QTableWidgetItem, QTextEdit, QScrollArea, QWidget, QMessageBox,
    QHeaderView, QTabWidget, QFileDialog, QInputDialog
)

from qgis.core import QgsProject, QgsVectorLayer

def _is_point_layer(lyr):
    # tipo de geometría Punto = 0 en todas las versiones de QGIS (3 y 4)
    try:
        return isinstance(lyr, QgsVectorLayer) and int(lyr.geometryType()) == 0
    except Exception:
        return False

from . import core

# --- Compatibilidad de enums Qt5 (QGIS 3) / Qt6 (QGIS 4) ---
try:
    ALIGN_CENTER = Qt.AlignmentFlag.AlignCenter      # PyQt6 / QGIS 4
except AttributeError:
    ALIGN_CENTER = Qt.AlignCenter                    # PyQt5 / QGIS 3
try:
    HSTRETCH = QHeaderView.ResizeMode.Stretch        # PyQt6 / QGIS 4
except AttributeError:
    HSTRETCH = QHeaderView.Stretch                   # PyQt5 / QGIS 3

# datos de ejemplo (práctica UNALM)
EJEMPLO = [
    [0,0,0,0,0,2,4,5,1,0,0,0,0,0],
    [0,0,0,0,9,19,24,31,29,9,0,0,0,0],
    [0,0,0,0,18,49,51,53,55,31,9,0,0,0],
    [0,0,0,4,35,70,59,42,60,48,24,1,0,0],
    [0,0,0,4,46,78,53,41,51,50,26,3,0,0],
    [0,0,0,8,34,71,65,52,51,42,23,5,0,0],
    [0,0,0,1,11,52,67,59,50,34,19,1,0,0],
    [0,0,0,0,3,28,41,40,24,18,9,0,0,0],
]


def heat_color(t):
    """t en [0,1] -> rojo(bajo)->amarillo->verde(alto)."""
    t = max(0.0, min(1.0, t))
    if t < 0.5:
        r, g, b = 248, int(105 + (235 - 105) * (t / 0.5)), int(107 + (132 - 107) * (t / 0.5))
    else:
        u = (t - 0.5) / 0.5
        r, g, b = int(255 - (255 - 99) * u), int(235 - (235 - 190) * u), int(132 - (132 - 123) * u)
    return QColor(r, g, b)


class CatchDialog(QDialog):
    def __init__(self, iface, parent=None):
        super().__init__(parent)
        self.iface = iface
        self.last_overlap = None
        self.last_results = None
        self.last_cmp = None
        self.setWindowTitle("Uniformidad de Aspersión — Matriz regular")
        self.resize(720, 760)
        self._build_ui()

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        outer = QVBoxLayout(self)
        tabs = QTabWidget()
        outer.addWidget(tabs)

        # ---------- pestaña ENTRADA ----------
        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        inner = QWidget(); lay = QVBoxLayout(inner)
        scroll.setWidget(inner)
        tabs.addTab(scroll, "1-3 · Datos de campo")

        # --- 1. Matriz regular ---
        g1 = QGroupBox("1. Matriz regular de pluviómetros")
        l1 = QGridLayout(g1)
        self.sp_rows = QSpinBox(); self.sp_rows.setRange(2, 60); self.sp_rows.setValue(8)
        self.sp_cols = QSpinBox(); self.sp_cols.setRange(2, 60); self.sp_cols.setValue(14)
        self.sp_space = QDoubleSpinBox(); self.sp_space.setRange(0.1, 50); self.sp_space.setValue(3.0); self.sp_space.setSuffix(" m")
        l1.addWidget(QLabel("Filas:"), 0, 0); l1.addWidget(self.sp_rows, 0, 1)
        l1.addWidget(QLabel("Columnas:"), 0, 2); l1.addWidget(self.sp_cols, 0, 3)
        l1.addWidget(QLabel("Espaciamiento entre vasos:"), 0, 4); l1.addWidget(self.sp_space, 0, 5)
        btn_gen = QPushButton("Generar / redimensionar matriz")
        btn_gen.clicked.connect(self.generate_matrix)
        btn_ej = QPushButton("Cargar ejemplo (UNALM)")
        btn_ej.clicked.connect(self.load_example)
        btn_gps = QPushButton("Importar desde capa de puntos (GPS)…")
        btn_gps.clicked.connect(self.import_points)
        btn_xlsx = QPushButton("Cargar desde Excel / CSV…")
        btn_xlsx.clicked.connect(self.import_excel)
        l1.addWidget(btn_gen, 1, 0, 1, 3); l1.addWidget(btn_ej, 1, 3, 1, 3)
        l1.addWidget(btn_gps, 2, 0, 1, 3); l1.addWidget(btn_xlsx, 2, 3, 1, 3)
        l1.addWidget(QLabel("Digite el volumen captado (ml) en cada celda:"), 3, 0, 1, 6)
        self.table = QTableWidget(8, 14)
        self.table.setMinimumHeight(230)
        l1.addWidget(self.table, 4, 0, 1, 6)
        lay.addWidget(g1)

        # --- 2. Ubicación del aspersor ---
        g2 = QGroupBox("2. Ubicación del aspersor en la matriz")
        l2 = QHBoxLayout(g2)
        self.sp_asp_row = QSpinBox(); self.sp_asp_row.setRange(1, 60); self.sp_asp_row.setValue(4)
        self.sp_asp_col = QSpinBox(); self.sp_asp_col.setRange(1, 60); self.sp_asp_col.setValue(7)
        l2.addWidget(QLabel("Fila del aspersor:")); l2.addWidget(self.sp_asp_row)
        l2.addSpacing(20)
        l2.addWidget(QLabel("Columna del aspersor:")); l2.addWidget(self.sp_asp_col)
        l2.addStretch()
        lay.addWidget(g2)

        # --- 3. Datos de campo ---
        g3 = QGroupBox("3. Información recolectada en campo")
        l3 = QGridLayout(g3)
        self.in_altura = QDoubleSpinBox(); self.in_altura.setRange(0, 20); self.in_altura.setValue(1.20); self.in_altura.setSuffix(" m")
        self.in_presion = QDoubleSpinBox(); self.in_presion.setRange(0, 2000); self.in_presion.setValue(400); self.in_presion.setSuffix(" kPa")
        self.in_caudal = QDoubleSpinBox(); self.in_caudal.setRange(0, 100000); self.in_caudal.setValue(2010); self.in_caudal.setSuffix(" L/h")
        self.in_viento = QDoubleSpinBox(); self.in_viento.setRange(0, 50); self.in_viento.setValue(2.0); self.in_viento.setSuffix(" m/s")
        self.in_vientodir = QDoubleSpinBox(); self.in_vientodir.setRange(0, 360); self.in_vientodir.setValue(0); self.in_vientodir.setSuffix(" °")
        self.in_tiempo = QDoubleSpinBox(); self.in_tiempo.setRange(0.1, 1440); self.in_tiempo.setValue(60); self.in_tiempo.setSuffix(" min")
        self.in_diam = QDoubleSpinBox(); self.in_diam.setRange(0.1, 100); self.in_diam.setValue(12.0); self.in_diam.setSuffix(" cm")
        campos = [
            ("Altura del aspersor:", self.in_altura), ("Presión de trabajo:", self.in_presion),
            ("Caudal del aspersor:", self.in_caudal), ("Velocidad del viento:", self.in_viento),
            ("Dirección del viento:", self.in_vientodir), ("Duración del ensayo:", self.in_tiempo),
            ("Diámetro de boca del pluviómetro:", self.in_diam),
        ]
        for i, (txt, w) in enumerate(campos):
            l3.addWidget(QLabel(txt), i // 2, (i % 2) * 2)
            l3.addWidget(w, i // 2, (i % 2) * 2 + 1)
        lay.addWidget(g3)
        lay.addStretch()

        # ---------- pestaña SOLAPE / RESULTADOS ----------
        w2 = QWidget(); rl = QVBoxLayout(w2)
        tabs.addTab(w2, "4 · Solape y resultados")

        g4 = QGroupBox("4. Solape / marco de riego")
        l4 = QGridLayout(g4)
        self.sp_marco_f = QSpinBox(); self.sp_marco_f.setRange(1, 60); self.sp_marco_f.setValue(3)
        self.sp_marco_c = QSpinBox(); self.sp_marco_c.setRange(1, 60); self.sp_marco_c.setValue(5)
        self.cb_tipo = QComboBox(); self.cb_tipo.addItems(["Rectangular", "Cuadrado"])
        self.lbl_marco_m = QLabel("9.0 × 15.0 m")
        self.sp_marco_f.valueChanged.connect(self._update_marco_label)
        self.sp_marco_c.valueChanged.connect(self._update_marco_label)
        self.sp_space.valueChanged.connect(self._update_marco_label)
        l4.addWidget(QLabel("Marco — Filas (celdas):"), 0, 0); l4.addWidget(self.sp_marco_f, 0, 1)
        l4.addWidget(QLabel("Marco — Columnas (celdas):"), 0, 2); l4.addWidget(self.sp_marco_c, 0, 3)
        l4.addWidget(QLabel("Tipo de solape:"), 1, 0); l4.addWidget(self.cb_tipo, 1, 1)
        l4.addWidget(QLabel("Marco resultante:"), 1, 2); l4.addWidget(self.lbl_marco_m, 1, 3)
        btn_calc = QPushButton("CALCULAR  (CU · DU · pluviometría)")
        btn_calc.setStyleSheet("font-weight:bold; padding:6px;")
        btn_calc.clicked.connect(self.calculate)
        l4.addWidget(btn_calc, 2, 0, 1, 4)
        rl.addWidget(g4)

        self.txt_res = QTextEdit(); self.txt_res.setReadOnly(True); self.txt_res.setMaximumHeight(210)
        rl.addWidget(self.txt_res)

        rr = QHBoxLayout()
        rr.addWidget(QLabel("Rampa de color:"))
        self.cb_ramp = QComboBox(); self.cb_ramp.addItems(core.ramp_names())
        self.cb_ramp.currentIndexChanged.connect(self._recolor)
        rr.addWidget(self.cb_ramp); rr.addStretch()
        rl.addLayout(rr)
        rl.addWidget(QLabel("Matriz traslapada (lámina relativa por celda):"))
        self.table_ovl = QTableWidget(0, 0); self.table_ovl.setMinimumHeight(200)
        rl.addWidget(self.table_ovl)

        hb = QHBoxLayout()
        self.btn_png = QPushButton("Exportar imagen (PNG)…")
        self.btn_png.clicked.connect(self.export_png); self.btn_png.setEnabled(False)
        self.btn_report = QPushButton("Reporte HTML/PDF…")
        self.btn_report.clicked.connect(self.generate_report); self.btn_report.setEnabled(False)
        self.btn_raster = QPushButton("Ráster a QGIS")
        self.btn_raster.clicked.connect(self.export_raster); self.btn_raster.setEnabled(False)
        btn_close = QPushButton("Cerrar"); btn_close.clicked.connect(self.close)
        hb.addWidget(self.btn_png); hb.addWidget(self.btn_report); hb.addWidget(self.btn_raster)
        hb.addStretch(); hb.addWidget(btn_close)
        rl.addLayout(hb)

        # ---------- pestaña COMPARACIÓN ----------
        w3 = QWidget(); cl = QVBoxLayout(w3)
        tabs.addTab(w3, "5 · Comparación de marcos")
        cl.addWidget(QLabel("Compara CU y DU para todos los marcos que caben en la matriz "
                            "(de 2 a 6 celdas por lado). Orden: mejor CU primero."))
        btn_cmp = QPushButton("Generar comparación de marcos")
        btn_cmp.setStyleSheet("font-weight:bold; padding:6px;")
        btn_cmp.clicked.connect(self.compare_action)
        cl.addWidget(btn_cmp)
        self.table_cmp = QTableWidget(0, 6)
        self.table_cmp.setHorizontalHeaderLabels(
            ["Marco (m)", "Filas (celdas)", "Columnas (celdas)", "CU (%)", "DU (%)", "Valoración"])
        cl.addWidget(self.table_cmp)

        self.generate_matrix()
        self._update_marco_label()

    # ------------------------------------------------------------- helpers
    def _update_marco_label(self):
        sp = self.sp_space.value()
        if self.cb_tipo.currentText() == "Cuadrado":
            self.sp_marco_c.setValue(self.sp_marco_f.value())
        self.lbl_marco_m.setText(f"{self.sp_marco_f.value()*sp:.1f} × {self.sp_marco_c.value()*sp:.1f} m")

    def generate_matrix(self):
        r, c = self.sp_rows.value(), self.sp_cols.value()
        old = self._read_matrix(silent=True)
        self.table.setRowCount(r); self.table.setColumnCount(c)
        self.table.setHorizontalHeaderLabels([str(i + 1) for i in range(c)])
        self.table.setVerticalHeaderLabels([str(r - i) for i in range(r)])
        for i in range(r):
            for j in range(c):
                val = ""
                if old is not None and i < old.shape[0] and j < old.shape[1]:
                    val = "" if old[i, j] == 0 else str(int(old[i, j]) if float(old[i, j]).is_integer() else old[i, j])
                it = QTableWidgetItem(val); it.setTextAlignment(ALIGN_CENTER)
                self.table.setItem(i, j, it)
        self.table.horizontalHeader().setSectionResizeMode(HSTRETCH)
        self.sp_asp_row.setMaximum(r); self.sp_asp_col.setMaximum(c)

    def load_example(self):
        self.sp_rows.setValue(8); self.sp_cols.setValue(14); self.sp_space.setValue(3.0)
        self.generate_matrix()
        for i in range(8):
            for j in range(14):
                v = EJEMPLO[i][j]
                self.table.item(i, j).setText("" if v == 0 else str(v))
        self.sp_asp_row.setValue(4); self.sp_asp_col.setValue(7)

    def _read_matrix(self, silent=False):
        r, c = self.table.rowCount(), self.table.columnCount()
        if r == 0 or c == 0:
            return None
        G = np.zeros((r, c))
        for i in range(r):
            for j in range(c):
                it = self.table.item(i, j)
                if it and it.text().strip():
                    try:
                        G[i, j] = float(it.text().replace(",", "."))
                    except ValueError:
                        if not silent:
                            QMessageBox.warning(self, "Dato inválido",
                                                f"Valor no numérico en fila {r-i}, columna {j+1}.")
                        return None
        return G

    # --------------------------------------------------------------- cálculo
    def calculate(self):
        G = self._read_matrix()
        if G is None or G.sum() <= 0:
            QMessageBox.warning(self, "Sin datos", "Ingrese volúmenes (ml) en la matriz.")
            return
        a, b = self.sp_marco_f.value(), self.sp_marco_c.value()
        if a > G.shape[0] or b > G.shape[1]:
            QMessageBox.warning(self, "Marco mayor que la matriz",
                                "El marco no puede exceder el tamaño de la matriz.")
            return
        sp = self.sp_space.value()
        diam = self.in_diam.value()
        dur_h = self.in_tiempo.value() / 60.0
        Q = self.in_caudal.value()

        cu0, du0 = core.unoverlapped_stats(G)
        cu, du, o = core.overlapped_stats(G, a, b)
        self.last_overlap = (o, sp)
        pluv = core.pluviometry_mm_h(o.mean(), diam, dur_h)
        teo, dev = core.mass_balance(pluv, Q, a * sp, b * sp)
        flag, pct = core.edge_warning(G)

        def cls(c):
            return ("Excelente" if c >= 88 else "Muy bueno" if c >= 84
                    else "Bueno" if c >= 80 else "Aceptable" if c >= 75 else "Deficiente")

        html = []
        html.append(f"<b>Aspersor:</b> fila {self.sp_asp_row.value()}, columna {self.sp_asp_col.value()} · "
                    f"altura {self.in_altura.value():.2f} m · {self.in_presion.value():.0f} kPa · "
                    f"viento {self.in_viento.value():.1f} m/s")
        html.append(f"<b>Marco de riego:</b> {a*sp:.1f} × {b*sp:.1f} m ({a}×{b} celdas, {self.cb_tipo.currentText().lower()})")
        html.append("<hr>")
        html.append(f"<b>Patrón individual (sin traslape):</b> CU = {cu0:.1f} %  ·  DU = {du0:.1f} %")
        html.append(f"<b>Con traslape:</b> &nbsp; CU = <b>{cu:.1f} %</b> ({cls(cu)}) &nbsp;·&nbsp; "
                    f"DU = <b>{du:.1f} %</b>")
        html.append(f"<b>Pluviometría media:</b> {pluv:.1f} mm/h "
                    f"(mín {o.min()*10/(np.pi*diam**2/4)/dur_h:.1f} · máx {o.max()*10/(np.pi*diam**2/4)/dur_h:.1f})")
        if teo is not None:
            color = "green" if abs(dev) <= 0.10 else "#c00000"
            html.append(f"<b>Balance de masa:</b> teórica {teo:.1f} mm/h · "
                        f"desviación <span style='color:{color}'>{dev*100:+.1f} %</span>")
        if flag:
            peor = max(pct, key=pct.get)
            html.append(f"<span style='color:#c00000'><b>⚠ Aviso:</b> el patrón no se cierra a cero en el borde "
                        f"({peor.replace('_',' ')} = {pct[peor]:.1f} % del total). "
                        f"Posible captación parcial; considere ampliar la malla en esa dirección.</span>")
        self.txt_res.setHtml("<br>".join(html))
        self._fill_overlap_table(o)
        area = np.pi * diam ** 2 / 4.0
        pmin = (o.min() * 10 / area / dur_h) if area > 0 and dur_h > 0 else 0.0
        pmax = (o.max() * 10 / area / dur_h) if area > 0 and dur_h > 0 else 0.0
        peak = (max(pct, key=pct.get), pct[max(pct, key=pct.get)]) if (flag and pct) else ('', 0)
        self.last_results = {
            'subtitle': f"Aspersor fila {self.sp_asp_row.value()}, col {self.sp_asp_col.value()} \u00b7 "
                        f"{self.in_presion.value():.0f} kPa \u00b7 viento {self.in_viento.value():.1f} m/s",
            'marco_str': f"{a*sp:.1f} \u00d7 {b*sp:.1f} m", 'spacing': sp,
            'cu': cu, 'du': du, 'cu0': cu0, 'du0': du0, 'pluv': pluv,
            'pluv_min': pmin, 'pluv_max': pmax, 'teorica': (teo or 0.0), 'dev': dev,
            'edge_flag': flag, 'edge_peak': peak, 'input_matrix': G, 'overlap_matrix': o,
            'params': {'asp_row': self.sp_asp_row.value(), 'asp_col': self.sp_asp_col.value(),
                       'altura': self.in_altura.value(), 'presion': self.in_presion.value(),
                       'caudal': self.in_caudal.value(), 'viento': self.in_viento.value(),
                       'vientodir': self.in_vientodir.value(), 'tiempo': self.in_tiempo.value(),
                       'diam': diam}}
        for _b in (self.btn_raster, self.btn_png, self.btn_report):
            _b.setEnabled(True)

    def _fill_overlap_table(self, o):
        r, c = o.shape
        self.table_ovl.setRowCount(r); self.table_ovl.setColumnCount(c)
        self.table_ovl.setHorizontalHeaderLabels([str(j + 1) for j in range(c)])
        self.table_ovl.setVerticalHeaderLabels([str(i + 1) for i in range(r)])
        mn, mx = o.min(), o.max()
        rng = (mx - mn) if mx > mn else 1.0
        for i in range(r):
            for j in range(c):
                it = QTableWidgetItem(f"{o[i, j]:.0f}")
                it.setTextAlignment(ALIGN_CENTER)
                it.setBackground(self._ramp_qcolor((o[i, j] - mn) / rng))
                self.table_ovl.setItem(i, j, it)
        self.table_ovl.horizontalHeader().setSectionResizeMode(HSTRETCH)

    # ------------------------------------------------------ comparación
    def compare_action(self):
        G = self._read_matrix()
        if G is None or G.sum() <= 0:
            QMessageBox.warning(self, "Sin datos", "Ingrese vol\u00famenes (ml) en la matriz.")
            return
        sp = self.sp_space.value()
        nr, nc = G.shape
        marcos = []
        for a in range(2, min(nr, 6) + 1):
            for b in range(a, min(nc, 6) + 1):
                marcos.append((a, b))
        rows = core.compare_marcos(G, marcos)
        self.last_cmp = rows
        self.table_cmp.setRowCount(len(rows))
        for i, r in enumerate(rows):
            cells = [f"{r['a']*sp:.0f} \u00d7 {r['b']*sp:.0f}", str(r['a']), str(r['b']),
                     f"{r['cu']:.1f}", f"{r['du']:.1f}", core.valoracion(r['cu'])]
            for j, v in enumerate(cells):
                it = QTableWidgetItem(v); it.setTextAlignment(ALIGN_CENTER)
                self.table_cmp.setItem(i, j, it)
        self._color_cmp()
        self.table_cmp.horizontalHeader().setSectionResizeMode(HSTRETCH)

    # ------------------------------------------------------ puntos GPS
    def import_points(self):
        dlg = PointImportDialog(self)
        if dlg.exec():
            G, info = dlg.result_matrix, dlg.result_info
            if G is None:
                return
            self.sp_space.setValue(round(info['spacing'], 3))
            self.sp_rows.setValue(G.shape[0]); self.sp_cols.setValue(G.shape[1])
            self.generate_matrix()
            if 'asp_row' in info and 'asp_col' in info:
                self.sp_asp_row.setValue(info['asp_row'])
                self.sp_asp_col.setValue(info['asp_col'])
            for i in range(G.shape[0]):
                for j in range(G.shape[1]):
                    v = G[i, j]
                    txt = "" if v == 0 else (str(int(v)) if float(v).is_integer() else f"{v:.1f}")
                    self.table.item(i, j).setText(txt)
            msg = (f"Importado desde \u00ab{info['layer']}\u00bb: {info['nrows']}\u00d7{info['ncols']} "
                   f"celdas, espaciamiento {info['spacing']:.2f} m.")
            if 'asp_row' in info:
                msg += f"\nAspersor ubicado en fila {info['asp_row']}, columna {info['asp_col']}."
            if info['off_grid'] > 0:
                msg += (f"\n\u26a0 {info['off_grid']} punto(s) no ca\u00edan exactamente en la grilla; "
                        f"se ajustaron al nodo m\u00e1s cercano.")
            QMessageBox.information(self, "Importaci\u00f3n completada", msg)

    # ------------------------------------------------------ rampa de color
    def _current_ramp(self):
        return self.cb_ramp.currentText() if hasattr(self, "cb_ramp") else "RdYlGn"

    def _ramp_qcolor(self, t):
        return QColor(*core.ramp_color(self._current_ramp(), max(0.0, min(1.0, t))))

    def _color_cmp(self):
        if not self.last_cmp:
            return
        for i, r in enumerate(self.last_cmp):
            it = self.table_cmp.item(i, 3)
            if it:
                it.setBackground(self._ramp_qcolor((r["cu"] - 70) / 25.0))

    def _recolor(self):
        if self.last_overlap is not None:
            self._fill_overlap_table(self.last_overlap[0])
        self._color_cmp()

    # ------------------------------------------------------ importar Excel/CSV
    def import_excel(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Cargar matriz", "", "Excel/CSV (*.xlsx *.xls *.csv)")
        if not path:
            return
        try:
            if path.lower().endswith(".csv"):
                G, info = core.matrix_from_csv(path)
            else:
                try:
                    sheets = core.xlsx_sheets(path)
                except ImportError as e:
                    QMessageBox.warning(self, "openpyxl no disponible",
                                        str(e) + "\n\nSugerencia: exporte la hoja a CSV y c\u00e1rguela "
                                        "(no requiere librer\u00edas adicionales).")
                    return
                sheet = sheets[0]
                if len(sheets) > 1:
                    sheet, ok = QInputDialog.getItem(self, "Hoja de Excel",
                                                     "Seleccione la hoja:", sheets, 0, False)
                    if not ok:
                        return
                G, info = core.matrix_from_xlsx(path, sheet=sheet)
        except Exception as e:
            QMessageBox.critical(self, "Error al leer el archivo", str(e))
            return
        self.sp_rows.setValue(G.shape[0]); self.sp_cols.setValue(G.shape[1])
        self.generate_matrix()
        for i in range(G.shape[0]):
            for j in range(G.shape[1]):
                v = G[i, j]
                txt = "" if v == 0 else (str(int(v)) if float(v).is_integer() else f"{v:.1f}")
                self.table.item(i, j).setText(txt)
        det = []
        if info.get("header_removed"): det.append("fila de encabezado")
        if info.get("label_removed"): det.append("columna de etiquetas")
        msg = f"Cargada matriz de {info['nrows']}\u00d7{info['ncols']} celdas."
        if det:
            msg += " Se omiti\u00f3 autom\u00e1ticamente: " + ", ".join(det) + "."
        QMessageBox.information(self, "Importaci\u00f3n completada", msg)

    # ------------------------------------------------------ exportar PNG
    def export_png(self):
        if self.last_overlap is None:
            return
        o, sp = self.last_overlap
        path, _ = QFileDialog.getSaveFileName(self, "Guardar imagen", "mapa_traslapado.png",
                                              "PNG (*.png)")
        if not path:
            return
        try:
            fmt = QImage.Format.Format_ARGB32      # Qt6
        except AttributeError:
            fmt = QImage.Format_ARGB32             # Qt5
        r, c = o.shape
        cell, mh, mw = 52, 26, 36
        img = QImage(mw + c * cell, mh + r * cell, fmt)
        img.fill(QColor("white"))
        pnt = QPainter(img)
        pnt.setFont(QFont("Arial", 9))
        mn, mx = o.min(), o.max(); rng = (mx - mn) if mx > mn else 1.0
        pnt.setPen(QColor("#1F4E5F"))
        for j in range(c):
            pnt.drawText(QRect(mw + j * cell, 0, cell, mh), ALIGN_CENTER, str(j + 1))
        for i in range(r):
            pnt.drawText(QRect(0, mh + i * cell, mw, cell), ALIGN_CENTER, str(i + 1))
        for i in range(r):
            for j in range(c):
                x, y = mw + j * cell, mh + i * cell
                col = QColor(*core.ramp_color(self._current_ramp(), (o[i, j] - mn) / rng))
                pnt.fillRect(x, y, cell, cell, col)
                pnt.setPen(QColor(220, 220, 220)); pnt.drawRect(x, y, cell, cell)
                lum = 0.299 * col.red() + 0.587 * col.green() + 0.114 * col.blue()
                pnt.setPen(QColor("black") if lum > 140 else QColor("white"))
                pnt.drawText(QRect(x, y, cell, cell), ALIGN_CENTER, f"{o[i, j]:.0f}")
        pnt.end()
        img.save(path, "PNG")
        QMessageBox.information(self, "Imagen exportada", f"Guardada en:\n{path}")

    # ------------------------------------------------------ reporte HTML/PDF
    def generate_report(self):
        if not self.last_results:
            QMessageBox.warning(self, "Calcule primero",
                                "Ejecute el c\u00e1lculo antes de generar el reporte.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Guardar reporte", "reporte_uniformidad.html",
                                              "HTML (*.html);;PDF (*.pdf)")
        if not path:
            return
        ctx = dict(self.last_results)
        ctx["ramp"] = self._current_ramp()
        G = self._read_matrix()
        if G is not None:
            nr, nc = G.shape
            marcos = [(a, b) for a in range(2, min(nr, 6) + 1) for b in range(a, min(nc, 6) + 1)]
            ctx["comparison"] = core.compare_marcos(G, marcos)
        html = core.build_html_report(ctx)
        if path.lower().endswith(".pdf"):
            if not self._html_to_pdf(html, path):
                hp = path[:-4] + ".html"
                open(hp, "w", encoding="utf-8").write(html)
                QMessageBox.information(self, "Reporte (HTML)",
                                        "No se pudo generar el PDF en este equipo; se guard\u00f3 el HTML en:\n"
                                        + hp + "\n\nPuede abrirlo en el navegador e imprimir a PDF.")
                return
        else:
            open(path, "w", encoding="utf-8").write(html)
        QMessageBox.information(self, "Reporte generado", f"Guardado en:\n{path}")

    def _html_to_pdf(self, html, path):
        try:
            from qgis.PyQt.QtGui import QTextDocument, QPdfWriter
        except Exception:
            return False
        try:
            writer = QPdfWriter(path); writer.setResolution(150)
            doc = QTextDocument(); doc.setHtml(html)
            printfn = getattr(doc, "print", None) or getattr(doc, "print_")
            printfn(writer)
            return True
        except Exception:
            return False

    # --------------------------------------------------------------- ráster
    def export_raster(self):
        if self.last_overlap is None:
            return
        try:
            from osgeo import gdal, osr
        except ImportError:
            QMessageBox.warning(self, "GDAL no disponible", "No se pudo importar GDAL.")
            return
        o, sp = self.last_overlap
        path, _ = QFileDialog.getSaveFileName(self, "Guardar ráster", "lamina_traslapada.tif",
                                              "GeoTIFF (*.tif)")
        if not path:
            return
        r, c = o.shape
        drv = gdal.GetDriverByName("GTiff")
        ds = drv.Create(path, c, r, 1, gdal.GDT_Float32)
        ds.SetGeoTransform((0, sp, 0, r * sp, 0, -sp))  # origen arbitrario, celda = espaciamiento
        srs = osr.SpatialReference(); srs.ImportFromEPSG(32718)  # UTM 18S (referencial)
        ds.SetProjection(srs.ExportToWkt())
        ds.GetRasterBand(1).WriteArray(o.astype("float32"))
        ds.FlushCache(); ds = None
        layer = self.iface.addRasterLayer(path, "Lámina traslapada (mm rel.)")
        self._style_raster(layer, o)
        QMessageBox.information(self, "Ráster creado",
                                "Se añadió la capa al proyecto.\nNota: el origen es arbitrario "
                                "(modo matriz regular); ajuste la georreferencia si lo necesita.")

    def _style_raster(self, layer, o):
        """Aplica al ráster un renderizador pseudocolor con la rampa elegida."""
        if layer is None or not layer.isValid():
            return
        try:
            from qgis.core import (QgsColorRampShader, QgsRasterShader,
                                   QgsSingleBandPseudoColorRenderer)
            mn, mx = float(o.min()), float(o.max())
            name = self._current_ramp(); steps = 12
            items = []
            for k in range(steps + 1):
                t = k / steps
                val = mn + (mx - mn) * t
                r, g, b = core.ramp_color(name, t)
                items.append(QgsColorRampShader.ColorRampItem(val, QColor(r, g, b), f"{val:.0f}"))
            ramp = QgsColorRampShader(); ramp.setColorRampItemList(items)
            try:
                ramp.setColorRampType(QgsColorRampShader.Interpolated)
            except Exception:
                pass
            shader = QgsRasterShader(); shader.setRasterShaderFunction(ramp)
            renderer = QgsSingleBandPseudoColorRenderer(layer.dataProvider(), 1, shader)
            layer.setRenderer(renderer); layer.triggerRepaint()
        except Exception:
            pass


# ============================================================
#  Sub-diálogo: importar matriz desde una capa de puntos (GPS)
# ============================================================
class PointImportDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Importar desde capa de puntos (GPS)")
        self.resize(460, 220)
        self.result_matrix = None
        self.result_info = None

        lay = QGridLayout(self)
        lay.addWidget(QLabel("Capa de puntos:"), 0, 0)
        self.cb_layer = QComboBox(); lay.addWidget(self.cb_layer, 0, 1)
        lay.addWidget(QLabel("Campo con el volumen captado (ml):"), 1, 0)
        self.cb_field = QComboBox(); lay.addWidget(self.cb_field, 1, 1)
        lay.addWidget(QLabel("Capa del aspersor (punto, opcional):"), 2, 0)
        self.cb_asp = QComboBox(); lay.addWidget(self.cb_asp, 2, 1)
        lay.addWidget(QLabel("Espaciamiento (m, 0 = automático):"), 3, 0)
        self.sp_spacing = QDoubleSpinBox(); self.sp_spacing.setRange(0, 200); self.sp_spacing.setValue(0)
        lay.addWidget(self.sp_spacing, 3, 1)
        self.lbl_warn = QLabel(""); self.lbl_warn.setStyleSheet("color:#c00000;")
        self.lbl_warn.setWordWrap(True)
        lay.addWidget(self.lbl_warn, 4, 0, 1, 2)

        hb = QHBoxLayout()
        ok = QPushButton("Importar"); ok.clicked.connect(self.do_import)
        cancel = QPushButton("Cancelar"); cancel.clicked.connect(self.reject)
        hb.addStretch(); hb.addWidget(ok); hb.addWidget(cancel)
        lay.addLayout(hb, 5, 0, 1, 2)

        self._layers = []
        self._populate_layers()
        self.cb_layer.currentIndexChanged.connect(self._populate_fields)
        self._populate_fields()

    def _populate_layers(self):
        self.cb_layer.clear(); self.cb_asp.clear(); self._layers = []
        self.cb_asp.addItem("(ninguna)")
        for lyr in QgsProject.instance().mapLayers().values():
            if _is_point_layer(lyr):
                self._layers.append(lyr)
                self.cb_layer.addItem(lyr.name())
                self.cb_asp.addItem(lyr.name())
        if not self._layers:
            self.lbl_warn.setText("No hay capas de puntos en el proyecto.")

    def _populate_fields(self):
        self.cb_field.clear()
        idx = self.cb_layer.currentIndex()
        if idx < 0 or idx >= len(self._layers):
            return
        lyr = self._layers[idx]
        for f in lyr.fields():
            self.cb_field.addItem(f.name())
        if lyr.crs().isGeographic():
            self.lbl_warn.setText("\u26a0 La capa está en coordenadas geográficas (grados). "
                                  "Reproyecte a un sistema métrico (p. ej. UTM) para que el "
                                  "espaciamiento se calcule en metros.")
        else:
            self.lbl_warn.setText("")

    def do_import(self):
        idx = self.cb_layer.currentIndex()
        if idx < 0 or idx >= len(self._layers):
            QMessageBox.warning(self, "Sin capa", "Seleccione una capa de puntos.")
            return
        lyr = self._layers[idx]
        field = self.cb_field.currentText()
        coords, values = [], []
        for feat in lyr.getFeatures():
            g = feat.geometry()
            if g is None or g.isEmpty():
                continue
            try:
                p = g.asPoint()
            except Exception:
                mp = g.asMultiPoint()
                if not mp:
                    continue
                p = mp[0]
            coords.append((p.x(), p.y()))
            v = feat[field]
            try:
                values.append(float(v) if v not in (None, "") else 0.0)
            except (TypeError, ValueError):
                values.append(0.0)
        if len(coords) < 4:
            QMessageBox.warning(self, "Pocos puntos", "La capa tiene menos de 4 puntos válidos.")
            return
        sp = self.sp_spacing.value() or None
        try:
            G, info = core.matrix_from_points(coords, values, spacing=sp)
        except Exception as e:
            QMessageBox.critical(self, "Error al construir la matriz", str(e))
            return
        info['layer'] = lyr.name()
        # ubicación del aspersor desde su capa de punto (opcional)
        ai = self.cb_asp.currentIndex() - 1   # -1 por la opción "(ninguna)"
        if 0 <= ai < len(self._layers):
            asp_layer = self._layers[ai]
            ap = None
            for feat in asp_layer.getFeatures():
                gg = feat.geometry()
                if gg is None or gg.isEmpty():
                    continue
                try:
                    ap = gg.asPoint()
                except Exception:
                    mp = gg.asMultiPoint()
                    ap = mp[0] if mp else None
                if ap is not None:
                    break
            if ap is not None:
                row, col = core.point_to_cell(ap.x(), ap.y(), info)
                info['asp_row'] = int(row); info['asp_col'] = int(col)
        self.result_matrix = G
        self.result_info = info
        self.accept()
