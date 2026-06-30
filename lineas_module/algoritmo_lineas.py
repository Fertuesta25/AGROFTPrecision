from qgis.core import (
    QgsFeature, QgsGeometry, QgsPointXY, QgsFields, QgsField,
    QgsWkbTypes, QgsVectorLayer, QgsProject, QgsFeatureRequest, 
    QgsCoordinateTransform, QgsCoordinateReferenceSystem, QgsFeedback
)
from qgis.PyQt.QtCore import QVariant, QMetaType
import math

def generar_lineas(base_layer, direccion_geom, espaciado, longitud, offset, lado, context=None, usar_seleccion=False):
    """
    Genera líneas perpendiculares a una línea base según una dirección especificada.
    
    Args:
        base_layer: Capa vectorial de líneas que servirá como base
        direccion_geom: Geometría de la línea que define la dirección
        espaciado: Distancia entre líneas generadas
        longitud: Longitud de las líneas a generar
        offset: Distancia desde el inicio de la línea base para la primera línea
        lado: 0=Derecha, 1=Izquierda, 2=Ambos lados
        context: Contexto de procesamiento (opcional)
        usar_seleccion: Si es True, solo procesa las entidades seleccionadas
        
    Returns:
        QgsVectorLayer: Capa de memoria con las líneas generadas
    """
    # Validar parámetros
    if espaciado <= 0:
        raise ValueError("El espaciado debe ser mayor que cero")
    if longitud <= 0:
        raise ValueError("La longitud debe ser mayor que cero")
    if offset < 0:
        raise ValueError("El offset debe ser mayor o igual a cero")
    
    # Crear estructura para la capa resultante
    results = []
    fields = QgsFields()
    fields.append(QgsField("id", QMetaType.Type.Int))
    fields.append(QgsField("linea_base_id", QMetaType.Type.Int))  # ID de la entidad base

    # Procesar la línea de dirección
    line = direccion_geom.asPolyline()
    if len(line) < 2:
        raise ValueError("La línea de dirección debe tener al menos dos puntos")
        
    dx, dy = line[-1].x() - line[0].x(), line[-1].y() - line[0].y()
    mag = math.hypot(dx, dy)
    
    if mag < 1e-10:  # Prevenir división por cero
        raise ValueError("Los puntos de dirección son demasiado cercanos")
        
    # Vector unitario de dirección
    ux, uy = dx / mag, dy / mag

    # Crear objeto de retroalimentación para mostrar progreso si hay contexto
    feedback = QgsFeedback() if context is None else context.feedback()
    
    # Crear una solicitud para obtener solo la geometría de las entidades
    request = QgsFeatureRequest().setNoAttributes()
    
    # Obtener las entidades de la capa base (seleccionadas o todas)
    if usar_seleccion:
        # Usar solo entidades seleccionadas
        features = base_layer.getSelectedFeatures(request)
        feature_count = base_layer.selectedFeatureCount()
    else:
        # Usar todas las entidades
        features = base_layer.getFeatures(request)
        feature_count = base_layer.featureCount()
    
    feature_id = 1
    
    # Procesar cada entidad de la capa base
    for i, feat in enumerate(features):
        if feedback and feedback.isCanceled():
            break
            
        # Actualizar progreso si hay contexto
        if feedback:
            feedback.setProgress(int(100 * i / feature_count))
            
        # Obtener geometría
        geom = feat.geometry()
        if geom.isEmpty() or geom.type() != QgsWkbTypes.LineGeometry:
            continue
            
        # Calcular longitud total y generar puntos a intervalos regulares
        total_length = geom.length()
        
        # Si el offset es mayor que la longitud total, pasar a la siguiente entidad
        if offset >= total_length:
            continue
            
        # Generar puntos a lo largo de la línea base
        dist = offset
        while dist <= total_length:
            # Obtener punto en la línea y su normal
            pt = geom.interpolate(dist).asPoint()
            p0 = QgsPointXY(pt.x(), pt.y())

            # Determinar direcciones según el lado seleccionado
            directions = []
            if lado == 0:  # Derecha
                directions.append((ux, uy))
            elif lado == 1:  # Izquierda
                directions.append((-ux, -uy))
            elif lado == 2:  # Ambos lados
                directions.append((ux, uy))
                directions.append((-ux, -uy))

            # Crear líneas en las direcciones seleccionadas
            for uxi, uyi in directions:
                p1 = QgsPointXY(p0.x() + uxi * longitud, p0.y() + uyi * longitud)
                new_geom = QgsGeometry.fromPolylineXY([p0, p1])
                
                # Crear entidad
                f = QgsFeature(fields)
                f.setGeometry(new_geom)
                f.setAttributes([feature_id, feat.id()])
                results.append(f)
                feature_id += 1
                
            # Avanzar al siguiente punto
            dist += espaciado

    # Crear capa de memoria con los resultados
    vl = QgsVectorLayer("LineString?crs=" + base_layer.crs().authid(), "LineasGeneradas", "memory")
    pr = vl.dataProvider()
    pr.addAttributes(fields)
    vl.updateFields()
    
    # Añadir entidades en bloque para mejorar el rendimiento
    if results:
        pr.addFeatures(results)
        vl.updateExtents()
        vl.triggerRepaint()
        
        # Añadir la capa al proyecto
        QgsProject.instance().addMapLayer(vl)
    
    return vl