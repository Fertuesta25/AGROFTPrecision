# -*- coding: utf-8 -*-
"""
Algoritmos de diseño de plantación, separados de la interfaz.

Cada función recibe parámetros ya validados y un callback opcional `progress(pct, texto)`
para reportar avance, y devuelve (capa_resultado, stats). No muestra cuadros de diálogo:
la validación de entradas y la confirmación de operaciones grandes se hacen en el dock.
"""
import math

from collections import defaultdict

from qgis.core import (
    QgsProject, QgsVectorLayer, QgsFeature, QgsGeometry,
    QgsRectangle, QgsField, QgsPointXY, QgsProperty,
    QgsSpatialIndex,
)
import processing

from .utils import (
    _type_string, _type_int, _type_double,
    calcular_area_ha, numero_a_letras,
)


def _noop(*_args, **_kwargs):
    pass


# ---------------------------------------------------------------------------
#  Estimadores (para que el dock pueda advertir antes de operaciones grandes)
# ---------------------------------------------------------------------------
def estimar_celdas(extent, esp_h, esp_v, subdiv):
    num_cols = math.ceil((extent.xMaximum() - extent.xMinimum()) / esp_h)
    num_filas = math.ceil((extent.yMaximum() - extent.yMinimum()) / (esp_v * subdiv))
    return num_cols, num_filas, num_cols * num_filas * subdiv


def estimar_puntos_grid(extent, d, x0, y0):
    dist_y = d
    dist_x = d * (math.sqrt(3) / 2.0)
    col_min = math.floor((extent.xMinimum() - x0) / dist_x) - 1
    col_max = math.ceil((extent.xMaximum() - x0) / dist_x) + 1
    row_min = math.floor((extent.yMinimum() - y0) / dist_y) - 1
    row_max = math.ceil((extent.yMaximum() - y0) / dist_y) + 1
    return (col_max - col_min) * (row_max - row_min)


# ---------------------------------------------------------------------------
#  PARCELAS
# ---------------------------------------------------------------------------
def generar_parcelas(capa_ref, esp_h, esp_v, subdiv, sentido_desc, recortar, nombre, progress=None):
    progress = progress or _noop
    progress(10, "Calculando cuadrícula...")

    extent = capa_ref.extent()
    xmin, ymin = extent.xMinimum(), extent.yMinimum()
    num_cols, num_filas, _ = estimar_celdas(extent, esp_h, esp_v, subdiv)
    crs = capa_ref.crs()

    capa_mem = QgsVectorLayer(f"Polygon?crs={crs.authid()}", "temp", "memory")
    prov = capa_mem.dataProvider()
    prov.addAttributes([
        QgsField("bloque", _type_string),
        QgsField("fila", _type_int),
        QgsField("subfila", _type_string),
        QgsField("parcela", _type_string),
        QgsField("area_ha", _type_double),
    ])
    capa_mem.updateFields()

    progress(20, "Generando celdas...")
    feats = []
    count = 0
    for col in range(num_cols):
        bloque = numero_a_letras(col + 1)
        for row in range(num_filas):
            fila = (num_filas - row) if sentido_desc else (row + 1)
            for s in range(subdiv):
                y1 = ymin + (row * subdiv + s) * esp_v
                y2 = ymin + (row * subdiv + s + 1) * esp_v
                x1 = xmin + col * esp_h
                x2 = xmin + (col + 1) * esp_h
                geom = QgsGeometry.fromRect(QgsRectangle(x1, y1, x2, y2))
                # La letra de subfila acompaña al sentido N-S elegido: en sentido
                # descendente (Norte->Sur) "a" queda al norte de cada fila.
                s_idx = (subdiv - 1 - s) if sentido_desc else s
                sub_letra = chr(97 + s_idx)
                f = QgsFeature(capa_mem.fields())
                f.setGeometry(geom)
                f.setAttributes([bloque, fila, sub_letra, f"{bloque}{fila}{sub_letra}", 0.0])
                feats.append(f)
                count += 1
        if num_cols > 0:
            progress(20 + int(60 * (col + 1) / num_cols), f"Celdas: {count}")
    prov.addFeatures(feats)
    capa_mem.setName(f"{nombre}_cuadricula")

    progress(82, "Recortando parcelas...")
    if recortar:
        capa_final = processing.run("native:clip", {
            'INPUT': capa_mem, 'OVERLAY': capa_ref, 'OUTPUT': 'memory:'
        })['OUTPUT']
    else:
        # Sin recorte, la capa final es una copia independiente de la cuadrícula
        # (para no agregar dos veces el mismo objeto al proyecto).
        capa_final = QgsVectorLayer(f"Polygon?crs={crs.authid()}", nombre, "memory")
        capa_final.dataProvider().addAttributes(capa_mem.fields().toList())
        capa_final.updateFields()
        capa_final.dataProvider().addFeatures(list(capa_mem.getFeatures()))
    capa_final.setName(nombre)

    def _calcular_areas(capa):
        idx_area = capa.fields().indexOf("area_ha")
        cambios = {}
        valores = []
        for f in capa.getFeatures():
            a = round(calcular_area_ha(f.geometry(), crs), 4)
            cambios[f.id()] = {idx_area: a}
            valores.append(a)
        if cambios:
            capa.dataProvider().changeAttributeValues(cambios)
        capa.updateExtents()
        return valores

    progress(88, "Calculando áreas...")
    areas = _calcular_areas(capa_final)
    # La cuadrícula completa (rectangular, sin recortar) también con su área.
    _calcular_areas(capa_mem)

    stats = {}
    if areas:
        total = sum(areas)
        stats = {
            "num": len(areas),
            "total": total,
            "min": min(areas),
            "max": max(areas),
            "prom": total / len(areas),
        }
    progress(100, "Completado")
    return capa_final, capa_mem, stats


# ---------------------------------------------------------------------------
#  EJES VIALES
# ---------------------------------------------------------------------------
def _azimut_dominante(geom):
    """Azimut (0-180) del segmento más largo de la línea. Más robusto que usar
    solo el primer y último vértice cuando la línea tiene varios tramos."""
    pts = geom.asPolyline()
    if len(pts) < 2:
        return None
    best_len = -1.0
    best_ang = 0.0
    for a, b in zip(pts[:-1], pts[1:]):
        dx, dy = b.x() - a.x(), b.y() - a.y()
        seg = math.hypot(dx, dy)
        if seg > best_len:
            best_len = seg
            best_ang = abs(math.degrees(math.atan2(dy, dx))) % 180
    return best_ang


def extraer_ejes(capa_parcelas, capa_limite, gen_colindancia, progress=None):
    progress = progress or _noop
    progress(10, "Extrayendo líneas...")
    res_lines = processing.run("native:polygonstolines", {'INPUT': capa_parcelas, 'OUTPUT': 'memory:'})
    progress(30, "Disolviendo...")
    res_diss = processing.run("native:dissolve", {'INPUT': res_lines['OUTPUT'], 'OUTPUT': 'memory:'})
    progress(50, "Explotando líneas...")
    res_final = processing.run("native:explodelines", {'INPUT': res_diss['OUTPUT'], 'OUTPUT': 'memory:'})
    capa_raw = res_final['OUTPUT']

    crs = capa_parcelas.crs().authid()
    ejes_final = QgsVectorLayer(f"LineString?crs={crs}", "Ejes_Viales_Clasificados", "memory")
    prov = ejes_final.dataProvider()
    prov.addAttributes([QgsField("tipo", _type_string), QgsField("long_km", _type_double)])
    ejes_final.updateFields()

    boundary_engine = None
    if capa_limite:
        progress(60, "Procesando límite...")
        res_b_diss = processing.run("native:dissolve", {'INPUT': capa_limite, 'OUTPUT': 'memory:'})
        res_b_line = processing.run("native:polygonstolines", {'INPUT': res_b_diss['OUTPUT'], 'OUTPUT': 'memory:'})
        combined = QgsGeometry()
        for f_b in res_b_line['OUTPUT'].getFeatures():
            combined = f_b.geometry() if combined.isEmpty() else combined.combine(f_b.geometry())
        if not combined.isEmpty():
            buff = combined.buffer(0.1, 5)
            if not buff.isEmpty():
                boundary_engine = QgsGeometry.createGeometryEngine(buff.constGet())
                boundary_engine.prepareGeometry()

    progress(70, "Clasificando ejes...")
    feats_to_add = []
    for feat in capa_raw.getFeatures():
        geom = feat.geometry()
        pts = geom.asPolyline()
        if not pts or len(pts) < 2:
            continue
        length_km = geom.length() / 1000.0
        tipo = "Kilometrica"
        es_colindancia = bool(boundary_engine and boundary_engine.contains(geom.constGet()))
        if es_colindancia:
            if not gen_colindancia:
                continue
            tipo = "Colindancia"
        else:
            ang = _azimut_dominante(geom)
            # Ejes ~N-S (verticales, 70-110°) = Kilométrica; el resto = Parcelaria.
            if ang is not None and not (70 <= ang <= 110):
                tipo = "Parcelaria"
        nf = QgsFeature(ejes_final.fields())
        nf.setGeometry(geom)
        nf.setAttributes([tipo, round(length_km, 4)])
        feats_to_add.append(nf)

    prov.addFeatures(feats_to_add)
    ejes_final.updateExtents()
    long_total = sum(f["long_km"] for f in ejes_final.getFeatures() if f["long_km"])
    progress(100, "Completado")
    stats = {"num_ejes": len(feats_to_add), "long_km": long_total}
    return ejes_final, stats


# ---------------------------------------------------------------------------
#  VÍAS (polígonos de rodadura)
# ---------------------------------------------------------------------------
def generar_vias(capa_ejes, capa_fundo, w_k, w_p, w_c, progress=None):
    progress = progress or _noop
    progress(15, "Preparando ejes...")

    # Buffer ÚNICO de TODOS los ejes con ancho según el tipo. Bufferar internos y
    # colindancia por separado y luego fusionarlos generaba un pico en los empalmes
    # en ángulo agudo (la unión booleana de dos rectángulos de vía). Con una sola
    # operación de buffer + disolución, los nodos se resuelven con unión redondeada
    # y el contorno queda limpio. Las anchuras se interpretan como semiancho para
    # los ejes internos (ancho total = w) y como ancho completo para la colindancia,
    # que al recortarse contra el fundo deja una franja útil de ~w_c hacia adentro.
    campos = [f.name() for f in capa_ejes.fields()]
    if "tipo" in campos:
        exp = ("CASE "
               f"WHEN \"tipo\" = 'Kilometrica' THEN {w_k / 2} "
               f"WHEN \"tipo\" = 'Colindancia' THEN {w_c} "
               f"ELSE {w_p / 2} END")
    else:
        exp = str(w_p / 2)

    progress(45, "Generando buffer de vías...")
    res_buf = processing.run("native:buffer", {
        'INPUT': capa_ejes,
        'DISTANCE': QgsProperty.fromExpression(exp),
        # Unión y extremos redondeados: sin puntas en ángulos agudos.
        'END_CAP_STYLE': 0, 'JOIN_STYLE': 0, 'SEGMENTS': 8,
        'DISSOLVE': True, 'OUTPUT': 'memory:'
    })

    progress(78, "Disolviendo...")
    capa_disuelta = processing.run("native:dissolve", {
        'INPUT': res_buf['OUTPUT'], 'OUTPUT': 'memory:'
    })['OUTPUT']

    # Recorte final al límite del fundo: ninguna vía sobresale del borde y la
    # colindancia queda con su franja efectiva hacia el interior.
    if capa_fundo:
        progress(90, "Recortando vías al límite del fundo...")
        capa_vias = processing.run("native:clip", {
            'INPUT': capa_disuelta, 'OVERLAY': capa_fundo, 'OUTPUT': 'memory:'
        })['OUTPUT']
    else:
        capa_vias = capa_disuelta
    capa_vias.setName("Capa_Rodadura_Vias_Final")

    progress(95, "Calculando estadísticas...")
    crs_obj = capa_ejes.crs()
    if "long_km" in campos:
        long_km = sum(f["long_km"] for f in capa_ejes.getFeatures() if f["long_km"])
    else:
        long_km = sum(f.geometry().length() for f in capa_ejes.getFeatures()) / 1000.0
    area_h = sum(calcular_area_ha(f.geometry(), crs_obj) for f in capa_vias.getFeatures())
    progress(100, "Completado")
    stats = {"long_km": long_km, "area_ha": area_h}
    return capa_vias, stats


# ---------------------------------------------------------------------------
#  PLANTAS (tresbolillo)
# ---------------------------------------------------------------------------
def generar_tresbolillo(capa_limite, capa_vias_excl, d, x0, y0,
                        capa_cuadricula=None, capa_parcelas=None, progress=None):
    """Genera el tresbolillo y numera líneas/plantas sobre la CUADRÍCULA completa.

    Flujo (según el diseño solicitado):
      1. Se crea la malla tresbolillo sobre la extensión de la cuadrícula.
      2. Cada planta recibe su 'parcela' a partir de la capa cuadrícula (malla
         regular completa), su 'linea' (Oeste->Este, reinicia por parcela) y su
         'planta' (Sur->Norte, reinicia por línea). La numeración se hace sobre
         TODAS las plantas de la malla, antes de borrar nada.
      3. Se borran las plantas que no se superponen con la capa de parcelas
         (la recortada al fundo). Las supervivientes conservan su numeración.
    """
    progress = progress or _noop
    progress(8, "Preparando geometría...")
    dist_y = d
    dist_x = d * (math.sqrt(3) / 2.0)

    # La extensión y la asignación de parcela se basan en la cuadrícula si existe.
    capa_ref_ext = capa_cuadricula if capa_cuadricula is not None else capa_limite
    extent = capa_ref_ext.extent()
    col_min = math.floor((extent.xMinimum() - x0) / dist_x) - 1
    col_max = math.ceil((extent.xMaximum() - x0) / dist_x) + 1
    row_min = math.floor((extent.yMinimum() - y0) / dist_y) - 1
    row_max = math.ceil((extent.yMaximum() - y0) / dist_y) + 1

    crs = capa_limite.crs()
    capa_puntos = QgsVectorLayer(f"Point?crs={crs.authid()}", "plantas_tresbolillo", "memory")
    prov = capa_puntos.dataProvider()
    prov.addAttributes([
        QgsField("id", _type_int),
        QgsField("col", _type_int),      # columna global del tresbolillo (Oeste->Este)
        QgsField("fila", _type_int),     # fila global del tresbolillo (Sur->Norte)
        QgsField("parcela", _type_string),
        QgsField("linea", _type_int),    # línea Oeste->Este, reinicia en 1 por parcela
        QgsField("planta", _type_int),   # planta Sur->Norte, reinicia en 1 por línea
    ])
    capa_puntos.updateFields()

    # --- Exclusión opcional de vías ---
    engine_vias = None
    if capa_vias_excl and capa_vias_excl.featureCount() > 0:
        progress(16, "Procesando exclusión de vías...")
        res_v = processing.run("native:dissolve", {'INPUT': capa_vias_excl, 'OUTPUT': 'memory:'})
        geom_vias = next(res_v['OUTPUT'].getFeatures()).geometry()
        if not geom_vias.isEmpty():
            engine_vias = QgsGeometry.createGeometryEngine(geom_vias.constGet())
            engine_vias.prepareGeometry()

    # --- Índice espacial de la CUADRÍCULA (asigna parcela a cada planta) ---
    cuad_index = None
    cuad_geoms = {}
    cuad_engines = {}
    cuad_nombre = {}
    fuente_parcela = capa_cuadricula if capa_cuadricula is not None else capa_parcelas
    if fuente_parcela is not None and fuente_parcela.featureCount() > 0:
        progress(22, "Indexando cuadrícula...")
        tiene_campo = "parcela" in [f.name() for f in fuente_parcela.fields()]
        cuad_index = QgsSpatialIndex(fuente_parcela.getFeatures())
        for cf in fuente_parcela.getFeatures():
            cuad_geoms[cf.id()] = cf.geometry()
            cuad_nombre[cf.id()] = (cf["parcela"] if tiene_campo else str(cf.id()))

    def parcela_de(geom_pt):
        if cuad_index is None:
            return ""
        for fid in cuad_index.intersects(geom_pt.boundingBox()):
            eng = cuad_engines.get(fid)
            if eng is None:
                eng = QgsGeometry.createGeometryEngine(cuad_geoms[fid].constGet())
                eng.prepareGeometry()
                cuad_engines[fid] = eng
            if eng.contains(geom_pt.constGet()):
                return cuad_nombre[fid]
        return ""

    # --- Motor de borrado: superposición con la capa de PARCELAS (recortada) ---
    # Si no hay capa de parcelas, se usa el límite del fundo como filtro.
    progress(28, "Preparando filtro de parcelas...")
    if capa_parcelas is not None and capa_parcelas.featureCount() > 0:
        res_p = processing.run("native:dissolve", {'INPUT': capa_parcelas, 'OUTPUT': 'memory:'})
        geom_filtro = next(res_p['OUTPUT'].getFeatures()).geometry()
    else:
        res_l = processing.run("native:dissolve", {'INPUT': capa_limite, 'OUTPUT': 'memory:'})
        geom_filtro = next(res_l['OUTPUT'].getFeatures()).geometry()
    engine_filtro = QgsGeometry.createGeometryEngine(geom_filtro.constGet())
    engine_filtro.prepareGeometry()

    # ------------------------------------------------------------------
    #  1) Generar TODAS las plantas de la malla (dentro de la cuadrícula),
    #     guardando si sobreviven al filtro de parcelas y a las vías.
    # ------------------------------------------------------------------
    progress(34, "Generando puntos...")
    puntos_info = []
    total_cols = col_max - col_min + 1
    for i, c in enumerate(range(col_min, col_max + 1)):
        curr_x = x0 + (c * dist_x)
        offset_y = (dist_y / 2.0) if (c % 2 != 0) else 0.0
        for r in range(row_min, row_max + 1):
            curr_y = y0 + (r * dist_y) + offset_y
            geom_pt = QgsGeometry.fromPointXY(QgsPointXY(curr_x, curr_y))
            parcela = parcela_de(geom_pt)
            # Solo interesan los puntos que caen en alguna celda de la cuadrícula.
            if not parcela:
                continue
            # ¿Sobrevive? Debe superponerse con parcelas y no caer en vía.
            sobrevive = engine_filtro.intersects(geom_pt.constGet())
            if sobrevive and engine_vias and engine_vias.contains(geom_pt.constGet()):
                sobrevive = False
            puntos_info.append({"c": c, "r": r, "y": curr_y, "geom": geom_pt,
                                "parcela": parcela, "sobrevive": sobrevive})
        if total_cols > 0:
            progress(34 + int(48 * (i + 1) / total_cols), f"Plantas en malla: {len(puntos_info)}")

    # ------------------------------------------------------------------
    #  2) Numerar sobre la malla COMPLETA: linea (O->E por parcela),
    #     planta (S->N por línea). Se numera antes de borrar.
    # ------------------------------------------------------------------
    progress(84, "Numerando líneas y plantas...")
    por_parcela = defaultdict(list)
    for p in puntos_info:
        por_parcela[p["parcela"]].append(p)

    for parcela, pts in por_parcela.items():
        cols_ordenadas = sorted(set(p["c"] for p in pts))      # Oeste -> Este
        col_a_linea = {c: i + 1 for i, c in enumerate(cols_ordenadas)}
        por_col = defaultdict(list)
        for p in pts:
            por_col[p["c"]].append(p)
        for c, cpts in por_col.items():
            cpts.sort(key=lambda p: p["y"])                    # Sur -> Norte
            linea = col_a_linea[c]
            for n, p in enumerate(cpts):
                p["linea"] = linea
                p["planta"] = n + 1

    # ------------------------------------------------------------------
    #  3) Borrar las que no se superponen con parcelas: solo se agregan
    #     al resultado las plantas marcadas como supervivientes.
    # ------------------------------------------------------------------
    progress(92, "Borrando plantas fuera de parcelas y agregando...")
    feats = []
    idx = 0
    for p in puntos_info:
        if not p["sobrevive"]:
            continue
        f = QgsFeature(capa_puntos.fields())
        f.setGeometry(p["geom"])
        f.setAttributes([idx, p["c"], p["r"], p["parcela"],
                         p.get("linea", 0), p.get("planta", 0)])
        feats.append(f)
        idx += 1
    prov.addFeatures(feats)
    capa_puntos.updateExtents()

    # Área para densidad: la de parcelas (área realmente plantada) si está; si no, límite.
    if capa_parcelas is not None and capa_parcelas.featureCount() > 0:
        area_ha = sum(calcular_area_ha(f.geometry(), crs) for f in capa_parcelas.getFeatures())
    else:
        area_ha = calcular_area_ha(geom_filtro, crs)
    total = len(feats)
    densidad = (total / area_ha) if area_ha and area_ha > 0 else None
    progress(100, "Completado")
    stats = {"total": total, "densidad": densidad, "area_ha": area_ha}
    return capa_puntos, stats
