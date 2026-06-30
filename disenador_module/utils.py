# -*- coding: utf-8 -*-
"""
Utilidades puras (sin UI) del plugin Diseñador de Plantación PRO.

Aquí viven los parseos de entrada, el cálculo de áreas, la conversión a letras
de bloque y la validación de CRS. Al no depender de widgets Qt, estas funciones
se pueden probar de forma aislada (p. ej. verificar que d=9 m da ~143 plantas/ha).
"""
import math

from qgis.PyQt.QtCore import QVariant
try:
    from qgis.PyQt.QtCore import QMetaType
except ImportError:
    QMetaType = None

from qgis.core import QgsDistanceArea, QgsProject

# ---------------------------------------------------------------------------
#  Compatibilidad de tipos de campo: QGIS 3.x (QVariant) vs 4.0/Qt6 (QMetaType)
# ---------------------------------------------------------------------------
try:
    _type_string = QMetaType.Type.QString
    _type_int = QMetaType.Type.Int
    _type_double = QMetaType.Type.Double
except (AttributeError, TypeError):
    _type_string = QVariant.String
    _type_int = QVariant.Int
    _type_double = QVariant.Double


def parse_float(text, field_name="campo"):
    """Convierte texto a float positivo. Acepta coma o punto decimal."""
    cleaned = text.strip().replace(',', '.')
    if not cleaned:
        raise ValueError(f"El campo '{field_name}' está vacío.")
    try:
        val = float(cleaned)
    except ValueError:
        raise ValueError(f"El campo '{field_name}' no contiene un número válido: '{text}'")
    if val <= 0:
        raise ValueError(f"El campo '{field_name}' debe ser mayor que cero (valor: {val}).")
    return val


def parse_int(text, field_name="campo"):
    """Convierte texto a entero positivo."""
    cleaned = text.strip()
    if not cleaned:
        raise ValueError(f"El campo '{field_name}' está vacío.")
    try:
        val = int(cleaned)
    except ValueError:
        raise ValueError(f"El campo '{field_name}' no contiene un entero válido: '{text}'")
    if val <= 0:
        raise ValueError(f"El campo '{field_name}' debe ser mayor que cero (valor: {val}).")
    return val


def calcular_area_ha(geometry, crs):
    """Área elipsoidal en hectáreas para la geometría dada."""
    da = QgsDistanceArea()
    da.setSourceCrs(crs, QgsProject.instance().transformContext())
    da.setEllipsoid(QgsProject.instance().ellipsoid())
    area_m2 = da.measureArea(geometry)
    return area_m2 / 10000.0


def numero_a_letras(num):
    """1->A, 2->B, ... 26->Z, 27->AA (estilo columnas de hoja de cálculo)."""
    letras = []
    while num > 0:
        num -= 1
        letras.insert(0, chr(ord('A') + num % 26))
        num //= 26
    return ''.join(letras)


def error_crs_metrico(capa):
    """Devuelve un mensaje de error si el CRS de la capa no sirve para diseñar
    en metros, o None si es válido (proyectado/métrico).

    Es la validación más importante: todos los espaciamientos se interpretan en
    las unidades del CRS. Con un CRS geográfico (grados) el diseño saldría mal
    sin lanzar ningún error visible.
    """
    crs = capa.crs()
    if not crs.isValid():
        return "La capa no tiene un sistema de coordenadas (CRS) válido asignado."
    if crs.isGeographic():
        return (f"La capa está en coordenadas geográficas (grados): {crs.authid()}.\n\n"
                "Los espaciamientos se interpretan en las unidades del CRS, así que "
                "reproyecte la capa a un CRS métrico/proyectado (por ejemplo "
                "UTM 18S, EPSG:32718) antes de continuar.")
    return None
