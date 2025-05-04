def classFactory(iface):
    from .agroft_plugin import AgroFTPrecisionPlugin
    return AgroFTPrecisionPlugin(iface)