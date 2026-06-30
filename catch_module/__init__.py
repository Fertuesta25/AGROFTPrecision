# -*- coding: utf-8 -*-
"""
Módulo Uniformidad de Aspersión (Catch3D) integrado en AGROFT PRECISION.

Evalúa la uniformidad de riego por aspersión (CU de Christiansen, DU del cuarto
inferior) desde una matriz regular de pluviómetros, con traslape de marcos,
conversión a pluviometría, carga desde Excel/CSV o capa de puntos GPS y reporte
HTML/PDF. Reproduce los coeficientes de Catch3D.

Autor original: Fernando Tuesta. Adaptado como módulo de AGROFT PRECISION.
"""


def get_module_instance(iface):
    """Devuelve una instancia del diálogo de Uniformidad de Aspersión."""
    from .catch_dialog import CatchDialog
    return CatchDialog(iface, iface.mainWindow())
