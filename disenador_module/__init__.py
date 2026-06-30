# -*- coding: utf-8 -*-
"""
Módulo Diseñador de Plantación PRO (Oil Palm) integrado en AGROFT PRECISION.

Diseño de plantaciones de palma aceitera: parcelas con subdivisiones, red vial
con clasificación de ejes por azimut y siembra en tresbolillo.

Autor original: Fernando (UNALM). Adaptado como módulo de AGROFT PRECISION.
"""
import os


def get_module_instance(iface):
    """Devuelve una instancia del dock del diseñador de plantación."""
    from .dock import GeneradorCuadriculaProDock
    return GeneradorCuadriculaProDock(iface, os.path.dirname(__file__))
