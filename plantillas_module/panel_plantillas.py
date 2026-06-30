import os
import time
from qgis.PyQt.QtWidgets import (QDockWidget, QWidget, QVBoxLayout, QLabel, QComboBox, 
                               QPushButton, QLineEdit, QFileDialog, QMessageBox, QHBoxLayout,
                               QCheckBox, QApplication)
from qgis.PyQt.QtCore import Qt, QSize, QTimer
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtXml import QDomDocument
from qgis.core import (QgsReadWriteContext, QgsProject, QgsPrintLayout, 
                      QgsLayoutItemAttributeTable, QgsProperty, QgsLayoutObject,
                      QgsLayoutFrame, QgsVectorLayer)


class PanelPlantillas(QDockWidget):
    def __init__(self, iface):
        """Constructor del panel para la selección de plantillas de mapa"""
        super(PanelPlantillas, self).__init__(iface.mainWindow())
        self.iface = iface
        self.setWindowTitle("Plantillas de Mapa")
        
        # Directorio donde está el módulo
        self.module_dir = os.path.dirname(__file__)
        
        # Directorio donde se guardarán las plantillas
        self.plantillas_dir = os.path.join(self.module_dir, "Plantillas")
        
        # Asegurar que el directorio de plantillas existe
        if not os.path.exists(self.plantillas_dir):
            os.makedirs(self.plantillas_dir)
            
        # Configurar la interfaz de usuario
        self.setup_ui()
        
        # Ocultar el panel al inicio
        self.hide()
        
        # Para almacenar la referencia al diseñador abierto
        self.current_designer = None
        
    def setup_ui(self):
        """Configura la interfaz de usuario del panel"""
        main_widget = QWidget()
        main_layout = QVBoxLayout()
        main_widget.setLayout(main_layout)
        
        # Etiqueta para la selección de plantilla
        lbl_plantilla = QLabel("Seleccionar Plantilla:")
        main_layout.addWidget(lbl_plantilla)
        
        # Combobox para la lista de plantillas
        self.combo_plantillas = QComboBox()
        main_layout.addWidget(self.combo_plantillas)
        
        # Botón para refrescar la lista de plantillas
        refresh_layout = QHBoxLayout()
        self.btn_refresh = QPushButton("Refrescar Lista")
        self.btn_refresh.clicked.connect(self.cargar_plantillas)
        refresh_layout.addWidget(self.btn_refresh)
        
        # Botón para importar nueva plantilla
        self.btn_importar = QPushButton("Importar Plantilla")
        self.btn_importar.clicked.connect(self.importar_plantilla)
        refresh_layout.addWidget(self.btn_importar)
        
        main_layout.addLayout(refresh_layout)
        
        # Etiqueta y campo para el nombre del mapa
        lbl_nombre = QLabel("Nombre del Mapa:")
        main_layout.addWidget(lbl_nombre)
        
        self.txt_nombre = QLineEdit()
        main_layout.addWidget(self.txt_nombre)
        
        # Opciones para actualizar tablas
        self.cb_actualizar_resumen = QCheckBox("Actualizar Cuadroresumen (Vertices_Sectores)")
        self.cb_actualizar_resumen.setChecked(True)
        main_layout.addWidget(self.cb_actualizar_resumen)
        
        self.cb_actualizar_redriego = QCheckBox("Actualizar Cuadroredriego (resumen_longitud)")
        self.cb_actualizar_redriego.setChecked(True)
        main_layout.addWidget(self.cb_actualizar_redriego)
        
        # Botón para crear el mapa
        self.btn_crear = QPushButton("Crear Mapa")
        self.btn_crear.clicked.connect(self.crear_mapa)
        main_layout.addWidget(self.btn_crear)
        
        # Añadir espaciador para que los widgets no se estiren
        main_layout.addStretch()
        
        self.setWidget(main_widget)
        
        # Establecer un tamaño mínimo
        self.setMinimumSize(QSize(300, 280))
        
        # Cargar las plantillas al inicio
        self.cargar_plantillas()
        
    def cargar_plantillas(self):
        """Carga la lista de plantillas disponibles en el directorio de plantillas"""
        self.combo_plantillas.clear()
        
        # Obtener los archivos .qpt del directorio de plantillas
        try:
            archivos = [f for f in os.listdir(self.plantillas_dir) 
                       if f.lower().endswith('.qpt')]
            
            if not archivos:
                self.combo_plantillas.addItem("No hay plantillas disponibles")
                self.btn_crear.setEnabled(False)
            else:
                for archivo in sorted(archivos):
                    # Mostrar el nombre sin la extensión
                    nombre = os.path.splitext(archivo)[0]
                    self.combo_plantillas.addItem(nombre, os.path.join(self.plantillas_dir, archivo))
                self.btn_crear.setEnabled(True)
                
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Error al cargar plantillas: {str(e)}")
            self.combo_plantillas.addItem("Error al cargar plantillas")
            self.btn_crear.setEnabled(False)
    
    def importar_plantilla(self):
        """Importa una plantilla nueva al directorio de plantillas"""
        archivo, _ = QFileDialog.getOpenFileName(
            self, "Seleccionar Plantilla", "", "Plantillas QGIS (*.qpt)")
        
        if archivo:
            try:
                # Obtener solo el nombre del archivo
                nombre_archivo = os.path.basename(archivo)
                # Ruta de destino
                destino = os.path.join(self.plantillas_dir, nombre_archivo)
                
                # Comprobar si ya existe una plantilla con el mismo nombre
                if os.path.exists(destino):
                    respuesta = QMessageBox.question(
                        self, "Confirmar Reemplazo", 
                        f"Ya existe una plantilla con el nombre '{nombre_archivo}'. ¿Desea reemplazarla?",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                    )
                    
                    if respuesta == QMessageBox.StandardButton.No:
                        return
                
                # Copiar el archivo
                import shutil
                shutil.copy2(archivo, destino)
                
                # Actualizar la lista de plantillas
                self.cargar_plantillas()
                
                # Seleccionar la plantilla recién importada
                index = self.combo_plantillas.findText(os.path.splitext(nombre_archivo)[0])
                if index >= 0:
                    self.combo_plantillas.setCurrentIndex(index)
                
                QMessageBox.information(self, "Éxito", "Plantilla importada correctamente.")
                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error al importar plantilla: {str(e)}")
    
    def crear_mapa(self):
        """Crea un nuevo mapa basado en la plantilla seleccionada"""
        # Verificar que haya plantillas disponibles
        if self.combo_plantillas.count() == 0 or self.combo_plantillas.currentData() is None:
            QMessageBox.warning(self, "Advertencia", "No hay plantillas disponibles.")
            return
        
        # Obtener el nombre del mapa
        nombre_mapa = self.txt_nombre.text().strip()
        if not nombre_mapa:
            QMessageBox.warning(self, "Advertencia", "Debe ingresar un nombre para el mapa.")
            return
        
        try:
            # Obtener la ruta de la plantilla seleccionada
            plantilla_path = self.combo_plantillas.currentData()
            
            # Obtener acceso al proyecto actual de QGIS
            project = QgsProject.instance()
            
            # Usar la API de QGIS para crear un nuevo diseño desde plantilla
            layout_manager = project.layoutManager()
            
            # Comprobar si ya existe un diseño con ese nombre
            if layout_manager.layoutByName(nombre_mapa):
                respuesta = QMessageBox.question(
                    self, "Confirmar Reemplazo", 
                    f"Ya existe un diseño llamado '{nombre_mapa}'. ¿Desea reemplazarlo?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                
                if respuesta == QMessageBox.StandardButton.Yes:
                    # Eliminar el diseño existente
                    layout_existente = layout_manager.layoutByName(nombre_mapa)
                    layout_manager.removeLayout(layout_existente)
                else:
                    return
            
            # Crear el nuevo diseño a partir de la plantilla
            layout = QgsPrintLayout(project)
            layout.initializeDefaults()
            layout.setName(nombre_mapa)
            
            # Cargar la plantilla
            try:
                with open(plantilla_path, 'r', encoding='utf-8') as template_file:
                    template_content = template_file.read()
            except UnicodeDecodeError:
                # Intenta con otra codificación si utf-8 falla
                with open(plantilla_path, 'r', encoding='latin-1') as template_file:
                    template_content = template_file.read()
            
            # Aplicar la plantilla al diseño
            document = QDomDocument()
            document.setContent(template_content)
            
            # Crear contexto de lectura/escritura y cargar la plantilla
            context = QgsReadWriteContext()
            items, ok = layout.loadFromTemplate(document, context, False)
            
            if ok:
                # Añadir el diseño al gestor de diseños
                layout_manager.addLayout(layout)
                
                # Verificar opciones seleccionadas
                actualizar_resumen = self.cb_actualizar_resumen.isChecked()
                actualizar_redriego = self.cb_actualizar_redriego.isChecked()
                
                # Procesar eventos para evitar bloqueos
                QApplication.processEvents()
                
                # Resultados de las actualizaciones
                resultado_resumen = False
                resultado_redriego = False
                
                # Actualizar tablas según las opciones seleccionadas
                if actualizar_resumen:
                    resultado_resumen = self.actualizar_tabla_atributos(layout, "Cuadroresumen", "Vertices_Sectores")
                
                if actualizar_redriego:
                    resultado_redriego = self.actualizar_tabla_atributos(layout, "Cuadroredriego", "resumen_longitud")
                
                # Asegurarnos de que el diseño se actualice
                layout.refresh()
                QApplication.processEvents()
                
                # Abrir el diseño en el diseñador
                self.current_designer = self.iface.openLayoutDesigner(layout)
                
                # Pausar el proceso para asegurar que el diseñador se abra
                QApplication.processEvents()
                time.sleep(0.5)
                QApplication.processEvents()
                
                # Programar activación de ventana - sin caracteres especiales en el nombre del método
                QTimer.singleShot(500, self.activar_ventana)
                
                # Mostrar mensaje según los resultados pero de forma no modal
                mensaje = ""
                if actualizar_resumen and actualizar_redriego:
                    if resultado_resumen and resultado_redriego:
                        mensaje = f"Mapa '{nombre_mapa}' creado correctamente. Ambas tablas actualizadas."
                    elif resultado_resumen:
                        mensaje = f"Mapa '{nombre_mapa}' creado correctamente. Se actualizó Cuadroresumen pero no Cuadroredriego."
                    elif resultado_redriego:
                        mensaje = f"Mapa '{nombre_mapa}' creado correctamente. Se actualizó Cuadroredriego pero no Cuadroresumen."
                    else:
                        mensaje = f"Mapa '{nombre_mapa}' creado correctamente, pero no se pudieron actualizar las tablas."
                elif actualizar_resumen:
                    if resultado_resumen:
                        mensaje = f"Mapa '{nombre_mapa}' creado correctamente. Cuadroresumen actualizado."
                    else:
                        mensaje = f"Mapa '{nombre_mapa}' creado correctamente, pero no se pudo actualizar Cuadroresumen."
                elif actualizar_redriego:
                    if resultado_redriego:
                        mensaje = f"Mapa '{nombre_mapa}' creado correctamente. Cuadroredriego actualizado."
                    else:
                        mensaje = f"Mapa '{nombre_mapa}' creado correctamente, pero no se pudo actualizar Cuadroredriego."
                else:
                    mensaje = f"Mapa '{nombre_mapa}' creado correctamente."
                
                # Mostrar mensaje no modal para no bloquear la visualización del diseñador
                msgBox = QMessageBox(QMessageBox.Icon.Information, "Éxito", mensaje, QMessageBox.StandardButton.Ok)
                msgBox.setModal(False)
                msgBox.show()
                
                # Programar una segunda activación después del mensaje - sin caracteres especiales
                QTimer.singleShot(1000, self.activar_ventana)
                
            else:
                QMessageBox.critical(self, "Error", "No se pudo cargar la plantilla seleccionada.")
                
        except Exception as e:
            import traceback
            error_msg = f"Error al crear el mapa: {str(e)}\n\n{traceback.format_exc()}"
            QMessageBox.critical(self, "Error Detallado", error_msg)
            print(error_msg)
    
    def activar_ventana(self):
        """Activa la ventana del diseñador de impresión (sin caracteres especiales en el nombre)"""
        if self.current_designer:
            try:
                # Obtener la ventana principal del diseñador
                window = self.current_designer.window()
                if window:
                    # Asegurar que la ventana es visible
                    window.show()
                    window.setVisible(True)
                    # Traer al frente y activar
                    window.raise_()
                    window.activateWindow()
                    window.setFocus()
                    
                # Intentar refrescar el diseño de forma segura
                try:
                    composition = self.current_designer.composition()
                    if composition:
                        composition.refresh()
                except:
                    pass
                    
                print("Ventana del diseñador activada")
            except Exception as e:
                print(f"Error al activar la ventana del diseñador: {str(e)}")
    
    def get_layer_by_name(self, layer_name):
        """Obtiene una capa por su nombre"""
        for layer in QgsProject.instance().mapLayers().values():
            if layer.name() == layer_name and isinstance(layer, QgsVectorLayer):
                return layer
        return None
    
    def actualizar_tabla_atributos(self, layout, table_id, layer_name):
        """
        Actualiza una tabla de atributos específica con la capa especificada
        
        Args:
            layout: El diseño que contiene la tabla
            table_id: El ID de la tabla a actualizar (ej. "Cuadroresumen" o "Cuadroredriego")
            layer_name: El nombre de la capa a usar (ej. "Vertices_Sectores" o "resumen_longitud")
            
        Returns:
            bool: True si la actualización fue exitosa, False en caso contrario
        """
        try:
            print(f"Intentando actualizar tabla con ID: {table_id} usando capa {layer_name}")
            
            # Procesar eventos para evitar bloqueos
            QApplication.processEvents()
            
            # Encontrar el frame con el ID especificado
            frame_tabla = None
            for item in layout.items():
                if isinstance(item, QgsLayoutFrame) and hasattr(item, 'id') and callable(item.id) and item.id() == table_id:
                    frame_tabla = item
                    print(f"Frame encontrado con ID: {item.id()}")
                    break
            
            if frame_tabla:
                # Obtenemos el elemento multimarco al que pertenece este frame
                multi_frame = frame_tabla.multiFrame()
                
                # Verificamos si es una tabla de atributos
                if isinstance(multi_frame, QgsLayoutItemAttributeTable):
                    print(f"El frame '{table_id}' pertenece a una tabla de atributos")
                    
                    # 1. DESACTIVAR la suplantación definida por datos
                    print("Paso 1: Desactivando la suplantación definida por datos...")
                    multi_frame.dataDefinedProperties().setProperty(
                        QgsLayoutObject.AttributeTableSourceLayer,
                        QgsProperty()  # Propiedad vacía = desactivar
                    )
                    
                    # Refrescar para aplicar los cambios
                    multi_frame.refresh()
                    layout.refresh()
                    QApplication.processEvents()
                    time.sleep(0.2)  # Pequeña pausa para asegurar que se procese
                    
                    print("Suplantación desactivada")
                    
                    # 2. ACTIVAR de nuevo la suplantación con la expresión
                    print("Paso 2: Reactivando la suplantación definida por datos...")
                    current_expression = f"'{layer_name}'"
                    multi_frame.dataDefinedProperties().setProperty(
                        QgsLayoutObject.AttributeTableSourceLayer,
                        QgsProperty.fromExpression(current_expression)
                    )
                    
                    # Refrescar para aplicar los cambios
                    multi_frame.refresh()
                    layout.refresh()
                    QApplication.processEvents()
                    time.sleep(0.2)  # Pequeña pausa para asegurar que se procese
                    
                    print(f"Suplantación reactivada con la expresión: {current_expression}")
                    
                    # 3. CAMBIAR la capa en el combobox
                    print(f"Paso 3: Cambiando la capa seleccionada a '{layer_name}'...")
                    target_layer = self.get_layer_by_name(layer_name)
                    
                    if target_layer:
                        multi_frame.setVectorLayer(target_layer)
                        
                        # Refrescar para aplicar los cambios
                        multi_frame.refresh()
                        layout.refresh()
                        QApplication.processEvents()
                        
                        print(f"Capa cambiada correctamente a '{layer_name}' para tabla {table_id}")
                        return True
                    else:
                        print(f"ERROR: No se encontró la capa '{layer_name}' en el proyecto")
                        print("Capas disponibles:")
                        for layer in QgsProject.instance().mapLayers().values():
                            print(f" - {layer.name()} (tipo: {layer.type()})")
                        return False
                    
                else:
                    print(f"El frame es parte de un multi-frame, pero no es una tabla de atributos. Tipo: {type(multi_frame).__name__}")
                    return False
            else:
                print(f"No se encontró el frame con ID '{table_id}'")
                
                # Como alternativa, intentemos encontrar cualquier tabla de atributos
                print("Buscando cualquier tabla de atributos...")
                found_table = None
                for item in layout.items():
                    # Buscar directamente tablas de atributos
                    if isinstance(item, QgsLayoutItemAttributeTable):
                        found_table = item
                        print(f"Tabla de atributos encontrada directamente")
                        break
                        
                    # O buscar frames que pertenezcan a tablas de atributos
                    elif isinstance(item, QgsLayoutFrame):
                        multi_frame = item.multiFrame() if hasattr(item, 'multiFrame') and callable(item.multiFrame) else None
                        if multi_frame and isinstance(multi_frame, QgsLayoutItemAttributeTable):
                            found_table = multi_frame
                            print(f"Encontrado frame de tabla de atributos con ID: {item.id() if hasattr(item, 'id') and callable(item.id) else 'Sin ID'}")
                            break
                
                # Si encontramos alguna tabla, trabajamos con ella
                if found_table:
                    print(f"Usando tabla alternativa para {table_id} ya que no se encontró el ID exacto")
                    
                    # Realizamos los tres pasos en la tabla alternativa
                    # 1. Desactivar
                    print("Paso 1: Desactivando la suplantación definida por datos...")
                    found_table.dataDefinedProperties().setProperty(
                        QgsLayoutObject.AttributeTableSourceLayer,
                        QgsProperty()
                    )
                    found_table.refresh()
                    layout.refresh()
                    QApplication.processEvents()
                    time.sleep(0.2)
                    
                    # 2. Activar de nuevo
                    print("Paso 2: Reactivando la suplantación definida por datos...")
                    found_table.dataDefinedProperties().setProperty(
                        QgsLayoutObject.AttributeTableSourceLayer,
                        QgsProperty.fromExpression(f"'{layer_name}'")
                    )
                    found_table.refresh()
                    layout.refresh()
                    QApplication.processEvents()
                    time.sleep(0.2)
                    
                    # 3. Cambiar capa
                    print(f"Paso 3: Cambiando la capa seleccionada a '{layer_name}'...")
                    target_layer = self.get_layer_by_name(layer_name)
                    if target_layer:
                        found_table.setVectorLayer(target_layer)
                        found_table.refresh()
                        layout.refresh()
                        QApplication.processEvents()
                        print(f"Operaciones completadas en la tabla alternativa para {table_id}")
                        return True
                    else:
                        print(f"No se encontró la capa '{layer_name}'")
                        return False
                else:
                    print("No se encontró ninguna tabla de atributos en el diseño")
                    return False
                    
        except Exception as e:
            import traceback
            error_msg = f"Error al actualizar tabla {table_id}: {str(e)}\n\n{traceback.format_exc()}"
            print(error_msg)
            return False
    
    def actualizar_cuadro_resumen(self, layout):
        """
        Método para mantener compatibilidad con el código anterior.
        Ahora llama al método actualizar_tabla_atributos con el ID "Cuadroresumen"
        """
        return self.actualizar_tabla_atributos(layout, "Cuadroresumen", "Vertices_Sectores")
    
    def toggle_panel(self):
        """Alterna la visibilidad del panel"""
        if self.isVisible():
            self.hide()
        else:
            self.show()
            self.raise_()
            self.activateWindow()
    
    def show_and_activate(self):
        """Muestra el panel y lo activa"""
        self.show()
        self.raise_()
        self.activateWindow()
        
    def unload(self):
        """Libera recursos al descargar el plugin"""
        try:
            self.close()
            self.deleteLater()
        except Exception as e:
            print(f"Error al descargar el panel de plantillas: {str(e)}")