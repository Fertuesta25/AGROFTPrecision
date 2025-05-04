from qgis.PyQt.QtCore import Qt, QVariant
from qgis.PyQt.QtWidgets import (QDockWidget, QVBoxLayout, QHBoxLayout, 
                                QLabel, QComboBox, QPushButton, QWidget, QSizePolicy,
                                QCheckBox, QStackedWidget, QDoubleSpinBox)
from qgis.core import QgsVectorLayer, NULL

from .filter_logic import apply_layer_filter, clear_layer_filter
from .utils import find_min_max_values, get_unique_field_values

class FilterDock(QDockWidget):
    def __init__(self, iface):
        super().__init__("Filtro por Campo", iface.mainWindow())
        self.iface = iface
        self.current_layer = None
        self.current_field_type = None
        
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
        layout = QVBoxLayout(main_widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)
        
        # Sección para seleccionar campo
        field_layout = QHBoxLayout()
        field_layout.setSpacing(5)
        field_label = QLabel("Campo:")
        field_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
        field_layout.addWidget(field_label)
        self.field_combo = QComboBox()
        self.field_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        field_layout.addWidget(self.field_combo)
        layout.addLayout(field_layout)
        
        layout.addSpacing(5)
        
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
        
        # Opción de zoom automático
        self.zoom_checkbox = QCheckBox("Zoom automático al filtrar")
        self.zoom_checkbox.setChecked(True)
        layout.addWidget(self.zoom_checkbox)
        
        layout.addSpacing(10)
        
        # Botones de acción
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        self.apply_btn = QPushButton("Aplicar Filtro")
        self.apply_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.clear_btn = QPushButton("Limpiar Filtro")
        self.clear_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        button_layout.addWidget(self.apply_btn)
        button_layout.addWidget(self.clear_btn)
        layout.addLayout(button_layout)
        
        layout.addStretch(1)
        
        self.setWidget(main_widget)
        self.setMinimumWidth(200)
        self.setMinimumHeight(220)
    
    def connect_signals(self):
        """Conecta las señales a sus correspondientes slots"""
        self.iface.currentLayerChanged.connect(self.layer_changed)
        self.field_combo.currentIndexChanged.connect(self.field_changed)
        self.apply_btn.clicked.connect(self.apply_filter)
        self.clear_btn.clicked.connect(self.clear_filter)
    
    def disconnect_signals(self):
        """Desconecta todas las señales"""
        try:
            self.iface.currentLayerChanged.disconnect(self.layer_changed)
            self.field_combo.currentIndexChanged.disconnect(self.field_changed)
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
        
        # Actualizar combobox de campos
        self.field_combo.clear()
        for field in layer.fields():
            self.field_combo.addItem(field.name())
            
        # Habilitar controles si hay campos
        enabled = self.field_combo.count() > 0
        self.field_combo.setEnabled(enabled)
        
        # Actualizar los valores si hay un campo seleccionado
        if enabled:
            self.field_changed()
    
    def field_changed(self):
        """Actualiza los valores disponibles cuando cambia el campo seleccionado"""
        if self.field_combo.currentIndex() == -1:
            return
            
        layer = self.current_layer
        if not layer or not isinstance(layer, QgsVectorLayer):
            return
            
        field_name = self.field_combo.currentText()
        field_idx = layer.fields().indexOf(field_name)
        field = layer.fields().at(field_idx)
        
        # Determinar el tipo de campo y configurar la interfaz adecuada
        is_numeric = field.type() in [QVariant.Int, QVariant.Double, QVariant.LongLong]
        self.current_field_type = field.type()
        
        if is_numeric:
            # Configurar controles para campo numérico
            min_val, max_val = find_min_max_values(layer, field_name)
            self.min_value_spin.setValue(min_val)
            self.max_value_spin.setValue(max_val)
            self.value_stack.setCurrentIndex(1)  # Mostrar controles de rango
        else:
            # Configurar combobox para campo de texto
            unique_values = get_unique_field_values(layer, field_name)
            self.value_combo.clear()
            self.value_combo.addItem("(Todos los valores)")
            for value in sorted(unique_values):
                self.value_combo.addItem(value)
            self.value_stack.setCurrentIndex(0)  # Mostrar combobox
    
    def apply_filter(self):
        """Aplica el filtro a la capa actual"""
        if not self.current_layer or not isinstance(self.current_layer, QgsVectorLayer):
            return
            
        field_name = self.field_combo.currentText()
        zoom_to_features = self.zoom_checkbox.isChecked()
        
        # Crear expresión de filtro según el tipo de campo
        if self.value_stack.currentIndex() == 1:  # Control de rango numérico
            min_val = self.min_value_spin.value()
            max_val = self.max_value_spin.value()
            apply_layer_filter(self.current_layer, field_name, 
                              numeric_range=(min_val, max_val),
                              zoom=zoom_to_features, iface=self.iface)
        else:  # Combobox
            value_text = self.value_combo.currentText()
            if value_text == "(Todos los valores)":
                self.clear_filter()
                return
            apply_layer_filter(self.current_layer, field_name,
                              text_value=value_text,
                              zoom=zoom_to_features, iface=self.iface)
    
    def clear_filter(self):
        """Elimina el filtro de la capa actual"""
        if not self.current_layer or not isinstance(self.current_layer, QgsVectorLayer):
            return
            
        clear_layer_filter(self.current_layer, 
                         zoom=self.zoom_checkbox.isChecked(), 
                         iface=self.iface)
    
    def disable_controls(self):
        """Deshabilita todos los controles"""
        self.field_combo.clear()
        self.field_combo.setEnabled(False)
        self.value_combo.clear()
        self.value_combo.setEnabled(False)
        self.min_value_spin.setEnabled(False)
        self.max_value_spin.setEnabled(False)
        self.zoom_checkbox.setEnabled(False)
        self.apply_btn.setEnabled(False)
        self.clear_btn.setEnabled(False)

    def show_and_activate(self):
        """Muestra y activa el panel, trayéndolo al frente"""
        self.show()
        self.raise_()
        self.activateWindow()