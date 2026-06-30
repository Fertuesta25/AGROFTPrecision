# AGROFT Precisión

**AGROFT Precisión** (`agroft_precision`) es un completo plugin para QGIS enfocado en el diseño y la documentación de proyectos de **riego de precisión**, integrando herramientas modulares para tareas agronómicas, hidráulicas y cartográficas en campo.

> **Versión 1.2.5** — Totalmente migrado y compatible con **QGIS 4.0 / Qt6**, con dos módulos nuevos (Diseñador de Plantación PRO y Uniformidad de Aspersión / Catch3D) y una identidad visual unificada.

## 🎯 Funcionalidades principales

- 📐 **Creación automática de capas** temáticas (sectores, emisores, red, cotas, etc.) con estilos `.qml` listos para usar.
- 🌐 **Diseño de red de riego** desde un panel especializado, con dibujo de tramos por longitud exacta, snapping y bloqueo de ángulo.
- 🌴 **Diseñador de Plantación PRO** *(nuevo)*: diseño de plantaciones de palma aceitera con parcelas subdivididas, red vial clasificada por azimut y siembra en tresbolillo.
- 💧 **Uniformidad de Aspersión – Catch3D** *(nuevo)*: evaluación de uniformidad de riego por aspersión (CU de Christiansen y DU del cuarto inferior) desde una matriz de pluviómetros, con traslape de marcos y reporte.
- 🏞️ **Cálculo de Balsas de Riego**: volúmenes útil y muerto a partir de la geometría del reservorio.
- ⛰️ **Extracción de alturas** de la red de riego desde un MDE.
- ✂️ **División de líneas** hidráulicas por longitud o número de segmentos.
- 🔲 **División de polígonos** en áreas iguales o en partes iguales (subdivisión de sectores).
- 🧮 **Enumeración automática de polígonos** y cálculo de áreas/perímetros.
- 📍 **Generación de vértices** y tabla de coordenadas (exportable).
- ➕ **Carga de puntos clave** como válvulas, hidrantes o emisores.
- 🧭 **Generación de líneas desde una base**, con dirección manual y espaciamiento definido.
- 🗂️ **Plantillas de impresión** automáticas para planos de riego (coordenadas, resumen de red, plano general).
- 🔍 **Filtro avanzado** para selección personalizada de objetos.

## ✨ Novedades de la versión 1.2.x

Resumen de las mejoras y añadiduras incorporadas respecto a la versión antigua (que no era compatible con QGIS 4.0).

### Compatibilidad con QGIS 4.0 / Qt6
- Migración completa del código a **Qt6**: enums de Qt en su forma *scoped* (p. ej. `Qt.AlignmentFlag.AlignCenter`), `QRegExp` → `QRegularExpression`, `exec_()` → `exec()`, y tipos de campo `QVariant.*` → `QMetaType.Type.*`.
- `qgisMinimumVersion` actualizado a **3.38**; el plugin funciona en **QGIS 3.38+ y QGIS 4.0**.
- Reparación de referencias de carga (`classFactory`) y limpieza de cachés.

### Módulos nuevos
- **🌴 Diseñador de Plantación PRO** (`disenador_module`): genera parcelas y subdivisiones sobre un polígono, una red vial con clasificación de ejes por azimut, y la siembra en **tresbolillo** (marco triangular). Requiere capa en CRS métrico (UTM).
- **💧 Uniformidad de Aspersión – Catch3D** (`catch_module`): calcula los coeficientes **CU** (Christiansen) y **DU** (cuarto inferior) desde una matriz regular de pluviómetros, con simulación de **traslape de marcos**, conversión a pluviometría, carga de datos desde **Excel/CSV** o desde una **capa de puntos GPS**, y exportación de **reporte HTML/PDF**. Reproduce la metodología de Catch3D.

### Identidad visual
- Nuevo set de **16 iconos SVG** en estilo lineal duotono (**turquesa `#57B8D0`** + **verde lima `#84B62E`**), coherente en toda la barra de herramientas y nítido en cualquier escala y en temas claro/oscuro.
- Los divisores de polígonos pasaron de PNG a SVG.

### Mejoras en herramientas existentes
- **🔍 Filtro avanzado** reescrito: selector de capa, operadores por condición (`=`, `≠`, `>`, `≥`, `<`, `≤`, *contiene*), panel de resumen (conteo y suma) e **invertir selección**, con construcción segura de expresiones.
- **🏞️ Cálculo de Balsas**: corrección de la fórmula de volumen (útil/muerto acotados al área del piso) y botón **«Copiar resumen»**.
- **🌐 Herramienta «Dibujar red»** (panel Red de Riego), revisada a fondo:
  - **Longitud geodésica correcta** en CRS geográfico (`computeSpheroidProject`); la línea de previa coincide siempre con la línea final.
  - **Bloqueo de ángulo con `Shift`** a múltiplos de 45° (0/45/90/135…), con **indicador de azimut** (`∠ 90°`) y aviso `⊾ orto` en la caja flotante.
  - **Clic derecho** para terminar la cadena continua.
  - **`Supr`** para deshacer el último tramo: la red se conserva y el dibujo continúa desde el vértice anterior.
  - Longitud y diámetro del tramo en la **barra de estado** (sin saturar la barra de mensajes).
  - Corrección de la transformación capa↔mapa cuando el CRS de la capa difiere del proyecto, y mejora de rendimiento de la previa.

## 🧱 Estructura del plugin

    agroft_precision/
    ├── agroft_plugin.py              # Núcleo del plugin
    ├── metadata.txt                  # Metadatos para QGIS
    ├── Plantilla*.qpt                # Plantillas de impresión
    ├── resources/
    │   └── icons/*.svg               # Set de iconos duotono (turquesa/verde)
    ├── capas_module/                 # Generación de capas temáticas
    │   └── styles/*.qml              # Estilos predefinidos
    ├── redriego_module/              # Panel de red de riego (dibujo de tramos)
    ├── disenador_module/             # 🌴 Diseñador de Plantación PRO (nuevo)
    ├── catch_module/                 # 💧 Uniformidad de Aspersión – Catch3D (nuevo)
    ├── balsas_module/                # Cálculo de balsas de riego
    ├── altura_module/                # Extracción de alturas desde MDE
    ├── dividirlineas_module/         # División de líneas
    ├── divisor_module/               # División de polígonos (áreas / partes)
    ├── puntos_module/                # Carga de puntos relevantes
    ├── enumerar_poligonos_module/    # Enumeración y etiquetado
    ├── vertices_module/              # Cálculo de vértices y coordenadas
    ├── lineas_module/                # Generación de líneas paralelas
    ├── plantillas_module/            # Manejo de plantillas .qpt
    └── filter_module/                # Herramientas de filtrado

## 🛠️ Herramienta «Dibujar red» — atajos

Al activar el dibujo en el panel **Red de Riego**:

| Acción | Atajo |
| --- | --- |
| Colocar el punto inicial | **Clic izquierdo** |
| Fijar la longitud del tramo | Teclear el número, o mover y hacer clic |
| Bloquear el ángulo a 0/45/90° | Mantener **Shift** mientras se dibuja |
| Terminar la cadena de tramos | **Clic derecho** |
| Deshacer el último tramo | **Supr** |

## 🚀 Instalación

1. Descarga el archivo `agroft_precision.zip`.
2. Extrae el contenido en la carpeta de plugins de QGIS:
   - **Windows:** `C:\Users\<usuario>\AppData\Roaming\QGIS\QGIS3\profiles\default\python\plugins\`
   - **Linux/macOS:** `~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/`
3. Reinicia QGIS y activa el plugin en el **Administrador de complementos**.

## ✅ Requisitos

- **QGIS 3.38 o superior**, totalmente compatible con **QGIS 4.0 (Qt6)**.
- Python 3.x (incluido en QGIS).
- `numpy` (incluido en QGIS), usado por el módulo de Uniformidad de Aspersión.

## 🖼️ Capturas de pantalla

*Agrega aquí imágenes que muestren la interfaz del plugin, el diseño de red, la siembra en tresbolillo, el reporte de uniformidad y los resultados de impresión.*

## 📌 Créditos

Desarrollado por **Fernando Tuesta** con apoyo de la IA Claude, como parte de un proyecto de digitalización y diseño técnico de redes de riego agrícola con herramientas SIG.
