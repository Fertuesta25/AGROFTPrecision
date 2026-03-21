# dividirlineas_module/__init__.py

def classFactory(iface):
    from .dividir_lineas_plugin import DividirLineasPlugin
    return DividirLineasPlugin(iface)

def get_module_instance(iface):
    from .dividir_lineas_plugin import DividirLineasPlugin
    return DividirLineasPlugin(iface)