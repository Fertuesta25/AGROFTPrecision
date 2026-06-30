# -*- coding: utf-8 -*-
"""
Filtro por Campo (AGROFT PRECISION)
Versión mejorada: selector de capa, operadores por condición, lógica AND/OR,
panel de resumen (conteo + sumatoria) y construcción de SQL segura.

Compatible con QGIS 4 / Qt6.
"""
from qgis.PyQt.QtCore import Qt, QMetaType
from qgis.PyQt.QtWidgets import (
    QDockWidget, QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QComboBox, QLineEdit, QPushButton, QStackedWidget,
    QRadioButton, QButtonGroup, QCheckBox, QScrollArea, QFrame, QSizePolicy,
)
from qgis.core import (
    QgsProject, QgsVectorLayer, QgsExpression, Qgis,
)

# Límite de valores únicos cargados en los combos (evita combos gigantes)
MAX_UNIQUE = 250


def _is_real(field):
    """True si el campo es de punto flotante (se filtra por rango)."""
    return field.type() in (QMetaType.Type.Double, QMetaType.Type.Float)


def _is_numeric(field):
    """True si el campo es numérico (entero o real)."""
    return field.type() in (
        QMetaType.Type.Int, QMetaType.Type.UInt,
        QMetaType.Type.LongLong, QMetaType.Type.ULongLong,
        QMetaType.Type.Double, QMetaType.Type.Float,
    )


class ConditionRow(QWidget):
    """Una fila de condición: campo · operador · valor (combo / rango / texto)."""

    MODE_COMBO = 0   # valores únicos (texto / entero)
    MODE_TEXT = 1    # entrada libre (fallback)
    MODE_RANGE = 2   # rango min/max (real)

    def __init__(self, fields=None, parent=None):
        super().__init__(parent)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # Campo
        self.combo_field = QComboBox()
        self.combo_field.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.combo_field.setMinimumWidth(90)
        if fields:
            self.combo_field.addItems(fields)
        layout.addWidget(self.combo_field, 2)

        # Operador
        self.combo_op = QComboBox()
        self.combo_op.addItems(["=", "≠", ">", "≥", "<", "≤", "contiene"])
        self.combo_op.setFixedWidth(82)
        self.combo_op.setToolTip("Operador de comparación")
        layout.addWidget(self.combo_op)

        # Valor (apilado: combo / texto / rango)
        self.stack = QStackedWidget()

        page_combo = QWidget()
        pc = QHBoxLayout(page_combo)
        pc.setContentsMargins(0, 0, 0, 0)
        self.combo_values = QComboBox()
        self.combo_values.setEditable(True)
        self.combo_values.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        pc.addWidget(self.combo_values)
        self.stack.addWidget(page_combo)

        page_text = QWidget()
        pt = QHBoxLayout(page_text)
        pt.setContentsMargins(0, 0, 0, 0)
        self.input_value = QLineEdit()
        self.input_value.setPlaceholderText("Valor")
        pt.addWidget(self.input_value)
        self.stack.addWidget(page_text)

        page_range = QWidget()
        pr = QHBoxLayout(page_range)
        pr.setContentsMargins(0, 0, 0, 0)
        self.input_min = QLineEdit()
        self.input_min.setPlaceholderText("Mín.")
        self.input_max = QLineEdit()
        self.input_max.setPlaceholderText("Máx.")
        pr.addWidget(self.input_min)
        pr.addWidget(QLabel("–"))
        pr.addWidget(self.input_max)
        self.stack.addWidget(page_range)

        layout.addWidget(self.stack, 3)

        # Botón eliminar
        self.btn_remove = QPushButton("✕")
        self.btn_remove.setFixedSize(24, 24)
        self.btn_remove.setToolTip("Eliminar esta condición")
        layout.addWidget(self.btn_remove)

    def set_mode(self, mode, unique_values=None):
        """Configura la fila según el tipo de campo."""
        if mode == self.MODE_RANGE:
            self.combo_op.setEnabled(False)
            self.stack.setCurrentIndex(self.MODE_RANGE)
        elif mode == self.MODE_COMBO:
            self.combo_op.setEnabled(True)
            self.combo_values.blockSignals(True)
            self.combo_values.clear()
            if unique_values:
                self.combo_values.addItems(unique_values)
            self.combo_values.setCurrentText("")
            self.combo_values.blockSignals(False)
            self.stack.setCurrentIndex(self.MODE_COMBO)
        else:
            self.combo_op.setEnabled(True)
            self.stack.setCurrentIndex(self.MODE_TEXT)

    def build_expression(self, is_numeric):
        """
        Devuelve un fragmento SQL seguro para esta condición, o None si está
        incompleta. Usa QgsExpression para escapar nombres y valores (evita que
        comillas en los datos rompan la expresión).
        """
        field = self.combo_field.currentText()
        if not field:
            return None
        col = QgsExpression.quotedColumnRef(field)

        # Modo rango (campos reales)
        if self.stack.currentIndex() == self.MODE_RANGE:
            v_min = self.input_min.text().strip().replace(",", ".")
            v_max = self.input_max.text().strip().replace(",", ".")
            try:
                lo = float(v_min) if v_min else None
                hi = float(v_max) if v_max else None
            except ValueError:
                return None
            partes = []
            if lo is not None:
                partes.append(f"{col} >= {lo}")
            if hi is not None:
                partes.append(f"{col} <= {hi}")
            return " AND ".join(partes) if partes else None

        # Modo combo / texto
        if self.stack.currentIndex() == self.MODE_COMBO:
            value = self.combo_values.currentText().strip()
        else:
            value = self.input_value.text().strip()
        if not value:
            return None

        op_visual = self.combo_op.currentText()
        op_map = {"=": "=", "≠": "!=", ">": ">", "≥": ">=", "<": "<", "≤": "<="}

        if op_visual == "contiene":
            patron = QgsExpression.quotedString(f"%{value}%")
            return f"{col} LIKE {patron}"

        op = op_map.get(op_visual, "=")
        if is_numeric:
            valor = value.replace(",", ".")
            try:
                float(valor)
            except ValueError:
                return None
            return f"{col} {op} {valor}"
        return f"{col} {op} {QgsExpression.quotedString(value)}"


class FilterDock(QDockWidget):
    """Panel acoplable de filtrado por campo."""

    def __init__(self, iface):
        super().__init__("Filtro por Campo", iface.mainWindow())
        self.iface = iface
        self.condition_rows = []
        self._prev_subsets = {}  # id_capa -> último subset válido (para restaurar)

        self.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea
        )
        self.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetFloatable
            | QDockWidget.DockWidgetFeature.DockWidgetMovable
            | QDockWidget.DockWidgetFeature.DockWidgetClosable
        )

        self._setup_ui()
        self._connect_signals()
        self.refresh_layers(prefer=self.iface.activeLayer())
        self._on_layer_changed()

    # ── Construcción de la interfaz ───────────────────────────────────────
    def _setup_ui(self):
        contenedor = QWidget()
        outer = QVBoxLayout(contenedor)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(6)

        # Selector de capa
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        self.combo_layers = QComboBox()
        form.addRow("Capa:", self.combo_layers)
        outer.addLayout(form)

        # Cabecera de condiciones + lógica
        cab = QHBoxLayout()
        cab.addWidget(QLabel("Condiciones:"))
        cab.addStretch()
        cab.addWidget(QLabel("Unir con:"))
        self.and_radio = QRadioButton("Y")
        self.or_radio = QRadioButton("O")
        self.and_radio.setChecked(True)
        self.logic_group = QButtonGroup(self)
        self.logic_group.addButton(self.and_radio)
        self.logic_group.addButton(self.or_radio)
        cab.addWidget(self.and_radio)
        cab.addWidget(self.or_radio)
        outer.addLayout(cab)

        # Área desplazable con las condiciones
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        cont_cond = QWidget()
        self.conditions_layout = QVBoxLayout(cont_cond)
        self.conditions_layout.setContentsMargins(0, 0, 0, 0)
        self.conditions_layout.setSpacing(4)
        self.conditions_layout.addStretch(1)
        scroll.setWidget(cont_cond)
        outer.addWidget(scroll, 1)

        self.btn_add = QPushButton("＋  Añadir condición")
        self.btn_add.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        outer.addWidget(self.btn_add)

        self.zoom_checkbox = QCheckBox("Zoom automático al filtrar")
        self.zoom_checkbox.setChecked(True)
        outer.addWidget(self.zoom_checkbox)

        sep1 = QFrame()
        sep1.setFrameShape(QFrame.Shape.HLine)
        sep1.setFrameShadow(QFrame.Shadow.Sunken)
        outer.addWidget(sep1)

        botones = QHBoxLayout()
        self.btn_apply = QPushButton("Aplicar filtro")
        self.btn_invert = QPushButton("Invertir")
        self.btn_invert.setToolTip("Mostrar las entidades que NO cumplen las condiciones")
        self.btn_clear = QPushButton("Limpiar filtro")
        for b in (self.btn_apply, self.btn_invert, self.btn_clear):
            b.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        botones.addWidget(self.btn_apply)
        botones.addWidget(self.btn_invert)
        botones.addWidget(self.btn_clear)
        outer.addLayout(botones)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setFrameShadow(QFrame.Shadow.Sunken)
        outer.addWidget(sep2)

        # Resumen
        fila_sum = QHBoxLayout()
        fila_sum.addWidget(QLabel("Sumar:"))
        self.combo_sum_field = QComboBox()
        self.combo_sum_field.setToolTip("Campo numérico para la sumatoria")
        fila_sum.addWidget(self.combo_sum_field, 1)
        outer.addLayout(fila_sum)

        self.lbl_count = QLabel("Entidades: —")
        self.lbl_sum = QLabel("Suma: —")
        self.lbl_count.setStyleSheet("font-size: 11px;")
        self.lbl_sum.setStyleSheet("font-size: 11px;")
        outer.addWidget(self.lbl_count)
        outer.addWidget(self.lbl_sum)

        self.setWidget(contenedor)
        self.setMinimumWidth(320)

    def _connect_signals(self):
        self.combo_layers.currentIndexChanged.connect(self._on_layer_changed)
        self.combo_sum_field.currentIndexChanged.connect(self._update_summary)
        self.btn_add.clicked.connect(self.add_condition)
        self.btn_apply.clicked.connect(self.apply_filter)
        self.btn_invert.clicked.connect(self.invert_filter)
        self.btn_clear.clicked.connect(self.clear_filter)

    # ── Capas ─────────────────────────────────────────────────────────────
    def _vector_layers(self):
        return [l for l in QgsProject.instance().mapLayers().values()
                if isinstance(l, QgsVectorLayer) and l.isValid()]

    def refresh_layers(self, prefer=None):
        """Repuebla el combo de capas conservando la selección si es posible."""
        anterior = self.combo_layers.currentData()
        objetivo = prefer.id() if isinstance(prefer, QgsVectorLayer) else anterior
        self.combo_layers.blockSignals(True)
        self.combo_layers.clear()
        for capa in self._vector_layers():
            self.combo_layers.addItem(capa.name(), capa.id())
        if objetivo is not None:
            idx = self.combo_layers.findData(objetivo)
            if idx >= 0:
                self.combo_layers.setCurrentIndex(idx)
        self.combo_layers.blockSignals(False)

    def _current_layer(self):
        return QgsProject.instance().mapLayer(self.combo_layers.currentData())

    def _on_layer_changed(self):
        for row in list(self.condition_rows):
            self._remove_row(row)
        self._populate_sum_fields()
        self._reset_summary()
        self.add_condition()

    # ── Información de campos ──────────────────────────────────────────────
    def _field_names(self):
        capa = self._current_layer()
        return [f.name() for f in capa.fields()] if capa else []

    def _field_info(self, field_name):
        """(is_numeric, is_real, valores_unicos|None)."""
        capa = self._current_layer()
        if not capa:
            return False, False, []
        idx = capa.fields().indexOf(field_name)
        if idx < 0:
            return False, False, []
        field = capa.fields().at(idx)
        numeric = _is_numeric(field)
        if _is_real(field):
            return True, True, None
        raw = capa.uniqueValues(idx, MAX_UNIQUE)
        unicos = sorted(str(v) for v in raw if v is not None)
        return numeric, False, unicos

    def _populate_sum_fields(self):
        self.combo_sum_field.blockSignals(True)
        self.combo_sum_field.clear()
        capa = self._current_layer()
        if capa:
            self.combo_sum_field.addItems(
                [f.name() for f in capa.fields() if _is_numeric(f)]
            )
        self.combo_sum_field.blockSignals(False)

    # ── Condiciones ───────────────────────────────────────────────────────
    def add_condition(self):
        row = ConditionRow(fields=self._field_names(), parent=self)
        row.combo_field.currentIndexChanged.connect(
            lambda _=None, r=row: self._update_row_mode(r)
        )
        row.btn_remove.clicked.connect(lambda _=None, r=row: self._remove_row(r))
        # Insertar antes del stretch final
        self.conditions_layout.insertWidget(self.conditions_layout.count() - 1, row)
        self.condition_rows.append(row)
        self._update_row_mode(row)
        self._update_remove_buttons()

    def _update_row_mode(self, row):
        numeric, is_real, unicos = self._field_info(row.combo_field.currentText())
        if is_real:
            row.set_mode(ConditionRow.MODE_RANGE)
        else:
            row.set_mode(ConditionRow.MODE_COMBO, unique_values=unicos)

    def _remove_row(self, row):
        if row in self.condition_rows:
            self.condition_rows.remove(row)
        self.conditions_layout.removeWidget(row)
        row.deleteLater()
        if not self.condition_rows:
            self.add_condition()
        else:
            self._update_remove_buttons()

    def _update_remove_buttons(self):
        # Con una sola condición, su botón eliminar se desactiva
        solo_una = len(self.condition_rows) == 1
        for r in self.condition_rows:
            r.btn_remove.setEnabled(not solo_una)

    # ── Aplicar / limpiar ─────────────────────────────────────────────────
    def _collect_expression(self):
        """Combina todas las condiciones en una sola expresión SQL, o None."""
        partes = []
        for row in self.condition_rows:
            numeric, _, _ = self._field_info(row.combo_field.currentText())
            expr = row.build_expression(numeric)
            if expr:
                partes.append(f"({expr})")
        if not partes:
            return None
        union = " AND " if self.and_radio.isChecked() else " OR "
        return union.join(partes)

    def _apply_subset(self, capa, expresion, invertido=False):
        """Aplica una expresión con validación, restauración y feedback."""
        anterior = capa.subsetString()
        if not capa.setSubsetString(expresion):
            # Restaurar el filtro previo si la expresión fue rechazada
            capa.setSubsetString(anterior)
            self._msg("La expresión no es válida para esta capa.", Qgis.MessageLevel.Critical)
            return
        self._prev_subsets[capa.id()] = expresion
        n = capa.featureCount()
        if n > 0:
            if self.zoom_checkbox.isChecked():
                capa.updateExtents()
                self.iface.mapCanvas().zoomToFeatureExtent(capa.extent())
            if invertido:
                self._msg(f"Filtro invertido: {n:,} entidad(es) no cumplen las condiciones.",
                          Qgis.MessageLevel.Success)
            else:
                self._msg(f"{n:,} entidad(es) coinciden con el filtro.",
                          Qgis.MessageLevel.Success)
        else:
            self._msg("El filtro no devolvió resultados.", Qgis.MessageLevel.Info)
        self.iface.mapCanvas().refresh()
        self._update_summary()

    def apply_filter(self):
        capa = self._current_layer()
        if not capa:
            self._msg("Selecciona una capa vectorial.", Qgis.MessageLevel.Warning)
            return
        expresion = self._collect_expression()
        if not expresion:
            self._msg("Completa al menos una condición.", Qgis.MessageLevel.Warning)
            return
        self._apply_subset(capa, expresion)

    def invert_filter(self):
        """Aplica el complemento: las entidades que NO cumplen las condiciones."""
        capa = self._current_layer()
        if not capa:
            self._msg("Selecciona una capa vectorial.", Qgis.MessageLevel.Warning)
            return
        expresion = self._collect_expression()
        if not expresion:
            self._msg("Completa al menos una condición para invertir.", Qgis.MessageLevel.Warning)
            return
        self._apply_subset(capa, f"NOT ({expresion})", invertido=True)

    def clear_filter(self):
        capa = self._current_layer()
        if capa:
            capa.setSubsetString("")
            self._prev_subsets.pop(capa.id(), None)
            if self.zoom_checkbox.isChecked():
                capa.updateExtents()
                self.iface.mapCanvas().zoomToFeatureExtent(capa.extent())
            self.iface.mapCanvas().refresh()
        for row in list(self.condition_rows):
            self._remove_row(row)
        self._reset_summary()

    # ── Resumen ───────────────────────────────────────────────────────────
    def _reset_summary(self):
        self.lbl_count.setText("Entidades: —")
        self.lbl_sum.setText("Suma: —")

    def _update_summary(self):
        capa = self._current_layer()
        if not capa:
            self._reset_summary()
            return
        self.lbl_count.setText(f"Entidades: {capa.featureCount():,}")

        campo = self.combo_sum_field.currentText()
        if not campo:
            self.lbl_sum.setText("Suma: —")
            return
        idx = capa.fields().indexOf(campo)
        if idx < 0:
            self.lbl_sum.setText("Suma: —")
            return
        total = 0.0
        for feat in capa.getFeatures():
            val = feat.attribute(idx)
            if val is not None:
                try:
                    total += float(val)
                except (TypeError, ValueError):
                    pass
        if _is_real(capa.fields().at(idx)):
            self.lbl_sum.setText(f"Suma ({campo}): {total:,.4f}")
        else:
            self.lbl_sum.setText(f"Suma ({campo}): {int(total):,}")

    # ── Utilidades ────────────────────────────────────────────────────────
    def _msg(self, texto, nivel):
        self.iface.messageBar().pushMessage("Filtro por Campo", texto, level=nivel, duration=4)

    def show_and_activate(self):
        """Muestra el panel y refresca la lista de capas."""
        self.refresh_layers()
        self.show()
        self.raise_()
        self.activateWindow()
