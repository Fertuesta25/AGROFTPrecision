from qgis.PyQt.QtCore import Qt, QVariant
from qgis.PyQt.QtWidgets import (QDockWidget, QVBoxLayout, QHBoxLayout, 
                                QLabel, QComboBox, QPushButton, QWidget, QSizePolicy,
                                QCheckBox, QStackedWidget, QDoubleSpinBox, QRadioButton,
                                QButtonGroup, QScrollArea, QFrame, QApplication)
from qgis.core import QgsVectorLayer, NULL
import traceback

from .utils import find_min_max_values, get_unique_field_values

class FilterCondition(QWidget):
    """Widget para una condición de filtrado individual"""
    def __init__(self, parent, filter_dock):
        super().__init__(parent)
        self.filter_dock = filter_dock
        self.current_field_type = None
        
        # Configurar el widget
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        
        # Sección para seleccionar campo
        field_layout = QHBoxLayout()
        field_layout.setSpacing(5)
        field_label = QLabel("Campo:")
        field_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
        field_layout.addWidget(field_label)
        self.field_combo = QComboBox()
        self.field_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        field_layout.addWidget(self.field_combo)
        
        # Botón para eliminar esta condición
        self.remove_btn = QPushButton("×")
        self.remove_btn.setMaximumWidth(25)
        self.remove_btn.setToolTip("Eliminar esta condición")
        field_layout.addWidget(self.remove_btn)
        
        layout.addLayout(field_layout)
        
        # StackedWidget para valores de texto vs. rangos numéricos
        self.value_stack = QStackedWidget()
        
        # Página 1: ComboBox para valores de texto
        combobox_page = QWidget()
        combobox_layout = QHBoxLayout(combobox_page)
        combobox_layout.setContentsMargins(0, 0, 0, 0)
        combobox_layout.setSpacing(5)
        value_label = QLabel("Valor:")
        value_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
        combobox_layout.addWidget(value_label)
        self.value_combo = QComboBox()
        self.value_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        combobox_layout.addWidget(self.value_combo)
        self.value_stack.addWidget(combobox_page)
        
        # Página 2: Campos de rango numérico
        range_page = QWidget()
        range_layout = QVBoxLayout(range_page)
        range_layout.setContentsMargins(0, 0, 0, 0)
        range_layout.setSpacing(5)
        
        # Rango mínimo
        min_layout = QHBoxLayout()
        min_label = QLabel("Mínimo:")
        min_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
        min_layout.addWidget(min_label)
        self.min_value_spin = QDoubleSpinBox()
        self.min_value_spin.setRange(-999999999, 999999999)
        self.min_value_spin.setDecimals(6)
        self.min_value_spin.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        min_layout.addWidget(self.min_value_spin)
        range_layout.addLayout(min_layout)
        
        # Rango máximo
        max_layout = QHBoxLayout()
        max_label = QLabel("Máximo:")
        max_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
        max_layout.addWidget(max_label)
        self.max_value_spin = QDoubleSpinBox()
        self.max_value_spin.setRange(-999999999, 999999999)
        self.max_value_spin.setDecimals(6)
        self.max_value_spin.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        max_layout.addWidget(self.max_value_spin)
        range_layout.addLayout(max_layout)
        
        self.value_stack.addWidget(range_page)
        
        layout.addWidget(self.value_stack)
        
        # Añadir un separador horizontal
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        layout.addWidget(separator)
        
        # Conectar señales
        self.field_combo.currentIndexChanged.connect(self.field_changed)
        self.remove_btn.clicked.connect(self.remove_self)
        
    def field_changed(self):
        """Actualiza los valores disponibles cuando cambia el campo seleccionado"""
        if self.field_combo.currentIndex() == -1:
            return
            
        layer = self.filter_dock.current_layer
        if not layer or not isinstance(layer, QgsVectorLayer):
            return
        
        try:    
            field_name = self.field_combo.currentText()
            field_idx = layer.fields().indexOf(field_name)
            
            if field_idx == -1:  # Comprobar si el campo existe
                return
                
            field = layer.fields().at(field_idx)
            
            # Determinar el tipo de campo y configurar la interfaz adecuada
            is_numeric = field.type() in [QVariant.Int, QVariant.Double, QVariant.LongLong]
            self.current_field_type = field.type()
            
            # Habilitar todos los controles y botones en el dock principal
            self.filter_dock.enable_controls()
            
            # Habilitar controles de este widget
            self.value_combo.setEnabled(True)
            self.min_value_spin.setEnabled(True)
            self.max_value_spin.setEnabled(True)
            
            if is_numeric:
                # Configurar controles para campo numérico
                min_val, max_val = find_min_max_values(layer, field_name)
                self.min_value_spin.setValue(min_val)
                self.max_value_spin.setValue(max_val)
                self.value_stack.setCurrentIndex(1)  # Mostrar controles de rango
            else:
                # Configurar combobox para campo de texto
                self.value_combo.blockSignals(True)  # Bloquear señales
                self.value_combo.clear()
                self.value_combo.addItem("(Todos los valores)")
                
                unique_values = get_unique_field_values(layer, field_name)
                for value in sorted(unique_values):
                    if value:  # Solo agregar valores no vacíos
                        self.value_combo.addItem(str(value))
                
                self.value_combo.blockSignals(False)  # Desbloquear señales
                self.value_stack.setCurrentIndex(0)  # Mostrar combobox
        except Exception as e:
            # Manejo de errores
            print(f"Error en field_changed: {str(e)}")
    
    def get_filter_expression(self):
        """Devuelve la expresión de filtro para esta condición"""
        if self.field_combo.currentIndex() == -1:
            return None
            
        field_name = self.field_combo.currentText()
        
        # Crear expresión según el tipo de campo
        if self.value_stack.currentIndex() == 1:  # Control de rango numérico
            min_val = self.min_value_spin.value()
            max_val = self.max_value_spin.value()
            return f'("{field_name}" >= {min_val} AND "{field_name}" <= {max_val})'
        else:  # Combobox
            value_text = self.value_combo.currentText()
            if value_text == "(Todos los valores)":
                return None
            return f'"{field_name}" = \'{value_text}\''
    
    def remove_self(self):
        """Elimina esta condición del dock"""
        self.filter_dock.remove_condition(self)
        
    def update_fields(self, layer):
        """Actualiza el combobox de campos con los campos de la capa"""
        self.field_combo.blockSignals(True)  # Bloquear señales para evitar llamadas innecesarias
        self.field_combo.clear()
        
        if not layer or not isinstance(layer, QgsVectorLayer):
            self.field_combo.blockSignals(False)
            return
            
        for field in layer.fields():
            self.field_combo.addItem(field.name())
            
        self.field_combo.blockSignals(False)  # Desbloquear señales
        
        # Actualizar los valores si hay un campo seleccionado
        if self.field_combo.count() > 0:
            self.field_combo.setCurrentIndex(0)
            self.field_changed()

class FilterDock(QDockWidget):
    def __init__(self, iface):
        super().__init__("Filtro por Campo", iface.mainWindow())
        self.iface = iface
        self.current_layer = None
        self.conditions = []  # Lista de condiciones de filtrado
        
        # Configurar el widget
        self.setup_ui()
        
        # Conectar señales
        self.connect_signals()
        
        # Actualizar con la capa actual
        self.layer_changed()

        # Configurar el dock para siempre aparecer a la derecha
        self.setAllowedAreas(Qt.RightDockWidgetArea)

        # Añadir el panel al dock de QGIS en la parte derecha
        iface.addDockWidget(Qt.RightDockWidgetArea, self)
        
        # Hacer que el panel ocupe todo el espacio disponible
        self.setFeatures(QDockWidget.DockWidgetFloatable | QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetClosable)
    
    def setup_ui(self):
        """Configura todos los elementos de la interfaz gráfica"""
        self.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        
        # Widget principal
        main_widget = QWidget()
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        
        # Área desplazable para las condiciones
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        
        self.conditions_widget = QWidget()
        self.conditions_layout = QVBoxLayout(self.conditions_widget)
        self.conditions_layout.setContentsMargins(0, 0, 0, 0)
        self.conditions_layout.setSpacing(10)
        self.conditions_layout.addStretch(1)
        
        scroll_area.setWidget(self.conditions_widget)
        main_layout.addWidget(scroll_area)
        
        # Botón para agregar condición
        add_condition_layout = QHBoxLayout()
        add_condition_layout.setSpacing(10)
        
        self.add_condition_btn = QPushButton("Agregar Condición")
        self.add_condition_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        add_condition_layout.addWidget(self.add_condition_btn)
        
        main_layout.addLayout(add_condition_layout)
        
        # Operador lógico
        operator_layout = QHBoxLayout()
        operator_layout.setSpacing(10)
        
        operator_label = QLabel("Operador:")
        operator_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
        operator_layout.addWidget(operator_label)
        
        self.operator_group = QButtonGroup(self)
        
        self.and_radio = QRadioButton("Y (AND)")
        self.and_radio.setChecked(True)
        self.operator_group.addButton(self.and_radio)
        operator_layout.addWidget(self.and_radio)
        
        self.or_radio = QRadioButton("O (OR)")
        self.operator_group.addButton(self.or_radio)
        operator_layout.addWidget(self.or_radio)
        
        main_layout.addLayout(operator_layout)
        
        # Opción de zoom automático
        self.zoom_checkbox = QCheckBox("Zoom automático al filtrar")
        self.zoom_checkbox.setChecked(True)
        main_layout.addWidget(self.zoom_checkbox)
        
        # Botones de acción
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        
        self.apply_btn = QPushButton("Aplicar Filtro")
        self.apply_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        
        self.clear_btn = QPushButton("Limpiar Filtro")
        self.clear_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        
        button_layout.addWidget(self.apply_btn)
        button_layout.addWidget(self.clear_btn)
        
        main_layout.addLayout(button_layout)
        
        self.setWidget(main_widget)
        self.setMinimumWidth(300)
        self.setMinimumHeight(400)
    
    def connect_signals(self):
        """Conecta las señales a sus correspondientes slots"""
        self.iface.currentLayerChanged.connect(self.layer_changed)
        self.add_condition_btn.clicked.connect(self.add_condition)
        self.apply_btn.clicked.connect(self.apply_filter)
        self.clear_btn.clicked.connect(self.clear_filter)
    
    def disconnect_signals(self):
        """Desconecta todas las señales"""
        try:
            self.iface.currentLayerChanged.disconnect(self.layer_changed)
            self.add_condition_btn.clicked.disconnect(self.add_condition)
            self.apply_btn.clicked.disconnect(self.apply_filter)
            self.clear_btn.clicked.disconnect(self.clear_filter)
        except:
            pass  # Si alguna señal no estaba conectada, ignorar
    
    def layer_changed(self):
        """Actualiza la interfaz cuando cambia la capa activa"""
        layer = self.iface.activeLayer()
        self.current_layer = layer
        
        if not layer or not isinstance(layer, QgsVectorLayer):
            self.disable_controls()
            return
        
        # Limpiar condiciones existentes
        while self.conditions:
            condition = self.conditions[0]
            self.conditions_layout.removeWidget(condition)
            condition.deleteLater()
            self.conditions.pop(0)
        
        # Agregar una nueva condición
        self.add_condition()
            
        # Habilitar controles
        self.enable_controls()
    
    def add_condition(self):
        """Agrega una nueva condición de filtrado"""
        try:
            # Mostrar un cursor de espera
            QApplication.setOverrideCursor(Qt.WaitCursor)
            
            condition = FilterCondition(self.conditions_widget, self)
            
            # Eliminar el stretch antes de agregar la condición
            if self.conditions_layout.count() > 0:
                item = self.conditions_layout.itemAt(self.conditions_layout.count() - 1)
                if item and item.spacerItem():
                    self.conditions_layout.takeAt(self.conditions_layout.count() - 1)
            
            # Agregar la condición y volver a añadir el stretch
            self.conditions_layout.addWidget(condition)
            self.conditions_layout.addStretch(1)
            
            # Agregar a la lista de condiciones
            self.conditions.append(condition)
            
            # Habilitar el botón para quitar condiciones si hay más de una
            if len(self.conditions) > 1:
                for cond in self.conditions:
                    cond.remove_btn.setEnabled(True)
            else:
                self.conditions[0].remove_btn.setEnabled(False)
                
            # Habilitar todos los controles
            self.enable_controls()
            
            # Actualizar los campos de la nueva condición
            if self.current_layer and isinstance(self.current_layer, QgsVectorLayer):
                condition.update_fields(self.current_layer)
            
            # Asegurar que la interfaz se refresque
            QApplication.processEvents()
            
        except Exception as e:
            print(f"Error al agregar condición: {str(e)}")
            traceback.print_exc()
        finally:
            # Restaurar el cursor
            QApplication.restoreOverrideCursor()
    
    def remove_condition(self, condition):
        """Elimina una condición de filtrado"""
        # Eliminar de la lista
        if condition in self.conditions:
            self.conditions.remove(condition)
            
        # Eliminar de la interfaz
        self.conditions_layout.removeWidget(condition)
        condition.deleteLater()
        
        # Si no quedan condiciones, agregar una nueva
        if not self.conditions:
            self.add_condition()
            
        # Deshabilitar el botón para quitar condiciones si solo queda una
        if len(self.conditions) == 1:
            self.conditions[0].remove_btn.setEnabled(False)
    
    def apply_filter(self):
        """Aplica el filtro a la capa actual"""
        if not self.current_layer or not isinstance(self.current_layer, QgsVectorLayer):
            return
            
        # Obtener las expresiones de todas las condiciones
        expressions = []
        for condition in self.conditions:
            expr = condition.get_filter_expression()
            if expr:
                expressions.append(expr)
                
        # Si no hay expresiones, limpiar el filtro
        if not expressions:
            self.clear_filter()
            return
            
        # Combinar expresiones con el operador seleccionado
        operator = " AND " if self.and_radio.isChecked() else " OR "
        filter_expr = operator.join(expressions)
        
        # Para múltiples condiciones, agregar paréntesis
        if len(expressions) > 1:
            filter_expr = "(" + filter_expr + ")"
        
        # Aplicar el filtro
        self.current_layer.setSubsetString(filter_expr)
        
        # Zoom a los elementos filtrados si está marcada la opción
        if self.zoom_checkbox.isChecked():
            self.iface.mapCanvas().zoomToFeatureExtent(self.current_layer.extent())
            self.iface.mapCanvas().refresh()
    
    def clear_filter(self):
        """Elimina el filtro de la capa actual"""
        if not self.current_layer or not isinstance(self.current_layer, QgsVectorLayer):
            return
            
        self.current_layer.setSubsetString("")
        
        # Zoom a todos los elementos si está marcada la opción
        if self.zoom_checkbox.isChecked():
            self.iface.mapCanvas().zoomToFeatureExtent(self.current_layer.extent())
            self.iface.mapCanvas().refresh()
    
    def disable_controls(self):
        """Deshabilita todos los controles"""
        self.add_condition_btn.setEnabled(False)
        self.and_radio.setEnabled(False)
        self.or_radio.setEnabled(False)
        self.zoom_checkbox.setEnabled(False)
        self.apply_btn.setEnabled(False)
        self.clear_btn.setEnabled(False)
        
        # Eliminar todas las condiciones
        for condition in self.conditions[:]:
            self.remove_condition(condition)
        self.conditions = []

    def enable_controls(self):
        """Habilita todos los controles"""
        self.add_condition_btn.setEnabled(True)
        self.and_radio.setEnabled(True)
        self.or_radio.setEnabled(True)
        self.zoom_checkbox.setEnabled(True)
        self.apply_btn.setEnabled(True)
        self.clear_btn.setEnabled(True)

    def show_and_activate(self):
        """Muestra y activa el panel, trayéndolo al frente"""
        self.show()
        self.raise_()
        self.activateWindow()
