# AGROFTPrecisión

**agroft_precision** es un completo plugin para QGIS enfocado en el diseño y documentación de proyectos de **riego de precisión**, integrando herramientas modulares para facilitar tareas agronómicas, hidráulicas y cartográficas en campo.

## 🎯 Funcionalidades principales

- 📐 **Creación automática de capas** temáticas (sectores, emisores, red, cotas, etc.) con estilos `.qml` listos para usar.
- ✂️ **División de líneas** hidráulicas por longitud o número de segmentos.
- 🔲 **División de polígonos** (e.g. subdividir sectores).
- 🧮 **Enumeración automática de polígonos** y cálculo de áreas/perímetros.
- 📍 **Generación de vértices** y tabla de coordenadas (exportable).
- 🌐 **Diseño de red de riego** desde panel especializado.
- ➕ **Carga de puntos clave** como válvulas, hidrantes o emisores.
- 🧭 **Generación de líneas desde una base**, con dirección manual y espaciamiento definido.
- 🗂️ **Plantillas de impresión** automáticas para planos de riego:
  - Coordenadas
  - Resumen de red
  - Plano general
- 🔍 **Filtro avanzado** para selección personalizada de objetos.

## 🧱 Estructura del plugin

    agroft_precision/
    ├── agroft_plugin.py # Núcleo del plugin
    ├── metadata.txt # Metadatos para QGIS
    ├── Plantilla*.qpt # Plantillas de impresión
    ├── capas_module/ # Generación de capas temáticas
    │ └── styles/*.qml # Estilos predefinidos
    ├── dividirlineas_module/ # División de líneas
    ├── divisor_module/ # División de polígonos
    ├── redriego_module/ # Panel de red de riego
    ├── puntos_module/ # Carga de puntos relevantes
    ├── enumerar_poligonos_module/ # Enumeración y etiquetado
    ├── vertices_module/ # Cálculo de vértices y coordenadas
    ├── lineas_module/ # Generación de líneas paralelas
    ├── plantillas_module/ # Manejo de plantillas .qpt
    └── filter_module/ # Herramientas de filtrado


## 🚀 Instalación

1. Descarga el archivo `agroft_precision.zip`.
2. Extrae el contenido en la carpeta de plugins de QGIS:
   - Windows:  
     `C:\Users\<usuario>\AppData\Roaming\QGIS\QGIS3\profiles\default\python\plugins\`
   - Linux/macOS:  
     `~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/`
3. Reinicia QGIS y activa el plugin en el administrador de complementos.

## ✅ Requisitos

- QGIS 3.10 o superior (se recomienda QGIS 3.42)
- Python 3.x (incluido en QGIS)

## 🖼️ Capturas de pantalla

*Agrega aquí imágenes que muestren la interfaz del plugin, resultados de impresión, capas generadas, etc.*

## 📌 Créditos

Desarrollado por Fernando Tuesta, como parte de un proyecto de digitalización y diseño técnico de redes de riego agrícola con herramientas SIG.
