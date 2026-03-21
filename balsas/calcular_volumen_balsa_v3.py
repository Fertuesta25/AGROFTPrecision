# balsas_module/calcular_volumen_balsa_v3.py
from qgis.core import (
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterNumber,
    QgsProcessingParameterFeatureSink,
    QgsProcessingException,
    QgsFeature,
    QgsGeometry,
    QgsFields,
    QgsField,
    QgsWkbTypes,
    QgsDistanceArea,
    QgsCoordinateTransform,
    QgsCoordinateReferenceSystem,
    Qgis
)
from qgis.PyQt.QtCore import QVariant, QCoreApplication
import math

class CalcularVolumenBalsaV3(QgsProcessingAlgorithm):
    """
    Algoritmo para calcular volumen de balsas de riego - Version 3.0 con 3D
    """
    
    INPUT_POLYGON = 'INPUT_POLYGON'
    PROFUNDIDAD = 'PROFUNDIDAD'
    TALUD_HORIZONTAL = 'TALUD_HORIZONTAL'
    TALUD_VERTICAL = 'TALUD_VERTICAL'
    ALTURA_SEGURIDAD = 'ALTURA_SEGURIDAD'
    ALTURA_PISO_MUERTO = 'ALTURA_PISO_MUERTO'
    AGARRE_LATERAL = 'AGARRE_LATERAL'
    PORCENTAJE_PERDIDAS = 'PORCENTAJE_PERDIDAS'
    OUTPUT = 'OUTPUT'
    OUTPUT_COMBINADO = 'OUTPUT_COMBINADO'
    OUTPUT_3D = 'OUTPUT_3D'

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.INPUT_POLYGON,
                'Poligono de la balsa',
                [QgsProcessing.TypeVectorPolygon]
            )
        )
        
        self.addParameter(
            QgsProcessingParameterNumber(
                self.PROFUNDIDAD,
                'Profundidad total (m)',
                type=QgsProcessingParameterNumber.Double,
                minValue=0.1,
                maxValue=50.0,
                defaultValue=2.0
            )
        )
        
        self.addParameter(
            QgsProcessingParameterNumber(
                self.TALUD_HORIZONTAL,
                'Talud horizontal (m)',
                type=QgsProcessingParameterNumber.Double,
                minValue=0.1,
                maxValue=10.0,
                defaultValue=1.0
            )
        )
        
        self.addParameter(
            QgsProcessingParameterNumber(
                self.TALUD_VERTICAL,
                'Talud vertical (m)',
                type=QgsProcessingParameterNumber.Double,
                minValue=0.1,
                maxValue=10.0,
                defaultValue=1.0
            )
        )
        
        self.addParameter(
            QgsProcessingParameterNumber(
                self.ALTURA_SEGURIDAD,
                'Altura de seguridad (m) - Margen superior',
                type=QgsProcessingParameterNumber.Double,
                minValue=0.0,
                maxValue=5.0,
                defaultValue=0.3
            )
        )
        
        self.addParameter(
            QgsProcessingParameterNumber(
                self.ALTURA_PISO_MUERTO,
                'Altura de piso muerto (m) - Margen inferior',
                type=QgsProcessingParameterNumber.Double,
                minValue=0.0,
                maxValue=2.0,
                defaultValue=0.2
            )
        )
        
        self.addParameter(
            QgsProcessingParameterNumber(
                self.AGARRE_LATERAL,
                'Agarre lateral geomembrana (m) - Anclaje en bordes',
                type=QgsProcessingParameterNumber.Double,
                minValue=0.5,
                maxValue=10.0,
                defaultValue=3.0
            )
        )
        
        self.addParameter(
            QgsProcessingParameterNumber(
                self.PORCENTAJE_PERDIDAS,
                'Porcentaje de perdidas (%) - Cortes y desperdicios',
                type=QgsProcessingParameterNumber.Double,
                minValue=0.0,
                maxValue=20.0,
                defaultValue=5.0
            )
        )
        
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT,
                'Balsa con volumenes calculados'
            )
        )
        
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT_COMBINADO,
                'Capa con los 4 niveles de la balsa (opcional)',
                type=QgsProcessing.TypeVectorPolygon,
                optional=True
            )
        )
        
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT_3D,
                'Capa 3D para visualizacion (opcional)',
                type=QgsProcessing.TypeVectorPolygon,
                optional=True
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        source = self.parameterAsSource(parameters, self.INPUT_POLYGON, context)
        
        # Obtener valores con manejo robusto de punto flotante
        profundidad = round(self.parameterAsDouble(parameters, self.PROFUNDIDAD, context), 6)
        talud_h = round(self.parameterAsDouble(parameters, self.TALUD_HORIZONTAL, context), 6)
        talud_v = round(self.parameterAsDouble(parameters, self.TALUD_VERTICAL, context), 6)
        altura_seg = round(self.parameterAsDouble(parameters, self.ALTURA_SEGURIDAD, context), 6)
        piso_muerto = round(self.parameterAsDouble(parameters, self.ALTURA_PISO_MUERTO, context), 6)
        agarre_lateral = round(self.parameterAsDouble(parameters, self.AGARRE_LATERAL, context), 6)
        porcentaje_perdidas = round(self.parameterAsDouble(parameters, self.PORCENTAJE_PERDIDAS, context), 6)
        
        # DEBUG: Mostrar todos los valores recibidos y redondeados
        feedback.pushInfo(f"=== VALORES RECIBIDOS Y PROCESADOS ===")
        feedback.pushInfo(f"Profundidad: {profundidad}")
        feedback.pushInfo(f"Talud horizontal: {talud_h}")
        feedback.pushInfo(f"Talud vertical: {talud_v}")
        feedback.pushInfo(f"Altura seguridad: {altura_seg}")
        feedback.pushInfo(f"Piso muerto: {piso_muerto}")
        feedback.pushInfo(f"Agarre lateral: {agarre_lateral}")
        feedback.pushInfo(f"Porcentaje perdidas: {porcentaje_perdidas}")
        feedback.pushInfo(f"====================================")
        
        # Validación con tolerancia para punto flotante (epsilon = 1e-10)
        epsilon = 1e-10
        
        if profundidad <= epsilon:
            raise QgsProcessingException(f"ERROR: Profundidad debe ser > 0 (recibido: {profundidad})")
        if talud_h <= epsilon:
            raise QgsProcessingException(f"ERROR: Talud horizontal debe ser > 0 (recibido: {talud_h})")
        if talud_v <= epsilon:
            raise QgsProcessingException(f"ERROR: Talud vertical debe ser > 0 (recibido: {talud_v})")
        if altura_seg < -epsilon:  # Permitir exactamente 0 para altura de seguridad
            raise QgsProcessingException(f"ERROR: Altura seguridad no puede ser negativa (recibido: {altura_seg})")
        if piso_muerto < -epsilon:  # Permitir exactamente 0 para piso muerto
            raise QgsProcessingException(f"ERROR: Piso muerto no puede ser negativo (recibido: {piso_muerto})")
        
        # Verificar que la suma de márgenes no sea mayor que la profundidad
        suma_margenes = altura_seg + piso_muerto
        if suma_margenes >= (profundidad - epsilon):
            raise QgsProcessingException(f"ERROR: Suma altura seguridad ({altura_seg:.3f}) + piso muerto ({piso_muerto:.3f}) = {suma_margenes:.3f} >= profundidad ({profundidad:.3f})")
        
        prof_efectiva = profundidad - altura_seg - piso_muerto
        relacion_talud = talud_h / talud_v
        reduccion_total = profundidad * relacion_talud
        reduccion_nivel = altura_seg * relacion_talud
        
        feedback.pushInfo(f"✅ VALIDACIÓN EXITOSA - Calculando volúmenes...")
        feedback.pushInfo(f"Profundidad total: {profundidad:.2f} m")
        feedback.pushInfo(f"Altura de seguridad: {altura_seg:.2f} m")
        feedback.pushInfo(f"Altura piso muerto: {piso_muerto:.2f} m")
        feedback.pushInfo(f"Profundidad efectiva (utilizable): {prof_efectiva:.2f} m")
        feedback.pushInfo(f"Relacion de talud: {relacion_talud:.2f}")
        feedback.pushInfo(f"Reduccion total: {reduccion_total:.2f} m")
        feedback.pushInfo(f"Reduccion nivel util: {reduccion_nivel:.2f} m")
        feedback.pushInfo(f"Agarre lateral geomembrana: {agarre_lateral:.2f} m")
        feedback.pushInfo(f"Porcentaje de perdidas: {porcentaje_perdidas:.1f}%")
        
        output_fields = self.crear_campos_principales(source.fields())
        
        (sink_principal, dest_id) = self.parameterAsSink(
            parameters,
            self.OUTPUT,
            context,
            output_fields,
            QgsWkbTypes.Polygon,
            source.sourceCrs()
        )
        
        sink_combinado = None
        dest_id_combinado = None
        if parameters[self.OUTPUT_COMBINADO] is not None:
            campos_combinado = self.crear_campos_combinado(source.fields())
            (sink_combinado, dest_id_combinado) = self.parameterAsSink(
                parameters,
                self.OUTPUT_COMBINADO,
                context,
                campos_combinado,
                QgsWkbTypes.Polygon,
                source.sourceCrs()
            )
        
        sink_3d = None
        dest_id_3d = None
        if parameters.get(self.OUTPUT_3D) is not None:
            campos_3d = self.crear_campos_3d(source.fields())
            (sink_3d, dest_id_3d) = self.parameterAsSink(
                parameters,
                self.OUTPUT_3D,
                context,
                campos_3d,
                QgsWkbTypes.PolygonZ,
                source.sourceCrs()
            )
        
        total = source.featureCount()
        contador = 0
        volumen_acumulado = 0
        
        for current, feature in enumerate(source.getFeatures()):
            if feedback.isCanceled():
                break
            
            feedback.setProgress(int(current * 100 / total))
            
            datos = self.calcular_datos_balsa(
                feature, profundidad, prof_efectiva, reduccion_total, 
                reduccion_nivel, context, feedback, piso_muerto, 
                agarre_lateral, porcentaje_perdidas, relacion_talud
            )
            
            if datos:
                feature_principal = self.crear_feature_principal(
                    feature, output_fields, datos, profundidad, 
                    altura_seg, piso_muerto, relacion_talud
                )
                
                if feature_principal:
                    sink_principal.addFeature(feature_principal)
                    contador += 1
                    volumen_acumulado += datos['volumen_util']
                    
                    if sink_combinado:
                        self.generar_capa_combinada(
                            feature, campos_combinado, datos, profundidad, 
                            altura_seg, piso_muerto, relacion_talud, sink_combinado
                        )
                    
                    if sink_3d:
                        self.generar_capa_3d(
                            feature, campos_3d, datos, profundidad, 
                            altura_seg, piso_muerto, relacion_talud, sink_3d
                        )
        
        feedback.pushInfo(f"\nProcesamiento completado:")
        feedback.pushInfo(f"Features procesados: {contador}/{total}")
        feedback.pushInfo(f"Volumen total: {volumen_acumulado:.2f} m3")
        feedback.pushInfo(f"Capacidad total: {volumen_acumulado * 1000:.0f} L")
        
        resultado = {self.OUTPUT: dest_id}
        if dest_id_combinado:
            resultado[self.OUTPUT_COMBINADO] = dest_id_combinado
        if dest_id_3d:
            resultado[self.OUTPUT_3D] = dest_id_3d
        
        return resultado

    def crear_campos_principales(self, campos_originales):
        fields = QgsFields()
        
        for field in campos_originales:
            fields.append(field)
        
        campos_nuevos = [
            ('area_sup_m2', QVariant.Double),
            ('area_inf_m2', QVariant.Double),
            ('area_util_m2', QVariant.Double),
            ('perimetro_m', QVariant.Double),
            ('vol_util_m3', QVariant.Double),
            ('vol_total_m3', QVariant.Double),
            ('vol_muerto_m3', QVariant.Double),
            ('cap_util_L', QVariant.Double),
            ('cap_total_L', QVariant.Double),
            ('cap_muerto_L', QVariant.Double),
            ('prof_efect_m', QVariant.Double),
            ('reduccion_m', QVariant.Double),
            ('relacion_areas', QVariant.Double),
            ('area_revestimiento_m2', QVariant.Double),
            ('area_revestimiento_comercial_m2', QVariant.Double),
            ('valido', QVariant.Bool)
        ]
        
        for nombre, tipo in campos_nuevos:
            campo = QgsField()
            campo.setName(nombre)
            if tipo == QVariant.Double:
                campo.setType(QVariant.Double)
                campo.setTypeName('double')
            elif tipo == QVariant.Bool:
                campo.setType(QVariant.Bool)
                campo.setTypeName('bool')
            fields.append(campo)
        
        return fields

    def crear_campos_3d(self, campos_originales):
        fields = QgsFields()
        
        for field in campos_originales:
            fields.append(field)
        
        campos_3d = [
            ('nivel_balsa', QVariant.String),
            ('elevacion_z', QVariant.Double),
            ('area_m2', QVariant.Double),
            ('perimetro_m', QVariant.Double),
            ('descripcion', QVariant.String),
            ('color_sugerido', QVariant.String)
        ]
        
        for nombre, tipo in campos_3d:
            campo = QgsField()
            campo.setName(nombre)
            if tipo == QVariant.Double:
                campo.setType(QVariant.Double)
                campo.setTypeName('double')
            elif tipo == QVariant.String:
                campo.setType(QVariant.String)
                campo.setTypeName('string')
            fields.append(campo)
        
        return fields

    def crear_campos_combinado(self, campos_originales):
        fields = QgsFields()
        
        for field in campos_originales:
            fields.append(field)
        
        campos_combinado = [
            ('nivel_balsa', QVariant.String),
            ('area_nivel_m2', QVariant.Double),
            ('perimetro_nivel_m', QVariant.Double),
            ('altura_superficie_m', QVariant.Double),
            ('altura_base_m', QVariant.Double),
            ('reduccion_m', QVariant.Double),
            ('volumen_m3', QVariant.Double),
            ('capacidad_L', QVariant.Double),
            ('descripcion', QVariant.String)
        ]
        
        for nombre, tipo in campos_combinado:
            campo = QgsField()
            campo.setName(nombre)
            if tipo == QVariant.Double:
                campo.setType(QVariant.Double)
                campo.setTypeName('double')
            elif tipo == QVariant.String:
                campo.setType(QVariant.String)
                campo.setTypeName('string')
            fields.append(campo)
        
        return fields

    def calcular_area_cartesiana(self, geometria, context):
        try:
            crs_origen = context.project().crs() if context.project() else None
            
            if crs_origen and crs_origen.isGeographic():
                centroide = geometria.centroid().asPoint()
                zona_utm = int((centroide.x() + 180) / 6) + 1
                hemisferio = 'N' if centroide.y() >= 0 else 'S'
                
                if hemisferio == 'N':
                    epsg_code = 32600 + zona_utm
                else:
                    epsg_code = 32700 + zona_utm
                
                crs_utm = QgsCoordinateReferenceSystem()
                crs_utm.createFromEpsg(epsg_code)
                
                transform = QgsCoordinateTransform(crs_origen, crs_utm, context.transformContext())
                geom_utm = QgsGeometry(geometria)
                geom_utm.transform(transform)
                
                da = QgsDistanceArea()
                return da.measureArea(geom_utm)
            else:
                da = QgsDistanceArea()
                return da.measureArea(geometria)
                
        except Exception:
            return geometria.area()

    def calcular_datos_balsa(self, feature, prof_total, prof_efectiva, red_total, red_nivel, context, feedback, piso_muerto, agarre_lateral, porcentaje_perdidas, relacion_talud):
        geom = feature.geometry()
        
        if not geom or geom.isEmpty():
            return None
        
        area_sup = self.calcular_area_cartesiana(geom, context)
        if area_sup <= 0:
            return None
        
        segmentos = 10
        geom_base = geom.buffer(-red_total, segmentos)
        geom_util = geom.buffer(-red_nivel, segmentos)
        
        reduccion_piso_muerto = (prof_total - piso_muerto) * red_total / prof_total
        geom_piso_muerto = geom.buffer(-reduccion_piso_muerto, segmentos)
        
        area_base = self.calcular_area_cartesiana(geom_base, context) if not geom_base.isEmpty() else 0
        area_util = self.calcular_area_cartesiana(geom_util, context) if not geom_util.isEmpty() else area_sup
        area_piso_muerto = self.calcular_area_cartesiana(geom_piso_muerto, context) if not geom_piso_muerto.isEmpty() else area_sup
        
        if area_base < 0: area_base = 0
        if area_util < 0: area_util = area_sup
        if area_piso_muerto < 0: area_piso_muerto = area_sup
        
        perimetro = geom.length()
        perimetro_base = geom_base.length() if not geom_base.isEmpty() else 0
        
        # Cálculo de volúmenes usando fórmula de prismoide
        if area_base > 0:
            if area_piso_muerto > area_base:
                vol_util = (prof_efectiva / 3) * (area_util + area_piso_muerto + math.sqrt(area_util * area_piso_muerto))
            else:
                vol_util = (prof_efectiva / 3) * (area_util + area_base + math.sqrt(area_util * area_base))
            
            vol_total = (prof_total / 3) * (area_sup + area_base + math.sqrt(area_sup * area_base))
            
            if area_piso_muerto > area_base:
                vol_muerto = (piso_muerto / 3) * (area_piso_muerto + area_base + math.sqrt(area_piso_muerto * area_base))
            else:
                vol_muerto = piso_muerto * area_base
        else:
            vol_util = (prof_efectiva * area_sup) / 3
            vol_total = (prof_total * area_sup) / 3
            vol_muerto = 0
        
        area_revestimiento = self.calcular_area_revestimiento(
            area_sup, area_base, perimetro, perimetro_base, prof_total, relacion_talud, 
            agarre_lateral, porcentaje_perdidas, feedback
        )
        
        datos = {
            'area_superior': area_sup,
            'area_base': area_base,
            'area_util': area_util,
            'area_piso_muerto': area_piso_muerto,
            'perimetro': perimetro,
            'volumen_util': vol_util,
            'volumen_total': vol_total,
            'volumen_muerto': vol_muerto,
            'relacion_areas': area_base / area_sup if area_sup > 0 else 0,
            'valido': vol_util > 0,
            'area_revestimiento': area_revestimiento,
            'geom_base': geom_base if not geom_base.isEmpty() else None,
            'geom_util': geom_util if not geom_util.isEmpty() else None,
            'geom_piso_muerto': geom_piso_muerto if not geom_piso_muerto.isEmpty() else None
        }
        
        feedback.pushInfo(f"Feature {feature.id()}: Area sup={area_sup:.2f} m2, Base={area_base:.2f} m2, Vol util={vol_util:.2f} m3, Geomembrana={area_revestimiento['area_neta']:.2f} m2")
        
        return datos

    def calcular_area_revestimiento(self, area_superior, area_base, perimetro_superior, perimetro_base, prof_total, relacion_talud, agarre_lateral, porcentaje_perdidas, feedback):
        try:
            area_agarre = perimetro_superior * agarre_lateral
            
            reduccion_total = prof_total * relacion_talud
            longitud_inclinada = math.sqrt(prof_total**2 + reduccion_total**2)
            
            if perimetro_base > 0:
                area_paredes = ((perimetro_superior + perimetro_base) / 2) * longitud_inclinada
                metodo_usado = "Geometrico (buffer)"
            else:
                area_paredes = perimetro_superior * longitud_inclinada * 0.5
                metodo_usado = "Aproximacion"
            
            area_fondo = area_base
            area_neta = area_agarre + area_paredes + area_fondo
            area_comercial = area_neta * (1 + porcentaje_perdidas / 100.0)
            
            if feedback:
                feedback.pushInfo(f"  - Agarre lateral: {perimetro_superior:.1f}m x {agarre_lateral:.1f}m = {area_agarre:.2f} m2")
                feedback.pushInfo(f"  - Paredes trapezoidales ({metodo_usado}):")
                feedback.pushInfo(f"    * Perimetro superior: {perimetro_superior:.1f} m")
                feedback.pushInfo(f"    * Perimetro base: {perimetro_base:.1f} m")
                feedback.pushInfo(f"    * Longitud inclinada: {longitud_inclinada:.2f} m")
                feedback.pushInfo(f"    * Area paredes: ({perimetro_superior:.1f} + {perimetro_base:.1f})/2 x {longitud_inclinada:.2f} = {area_paredes:.2f} m2")
                feedback.pushInfo(f"  - Fondo: {area_fondo:.2f} m2")
                feedback.pushInfo(f"  - Total neto: {area_neta:.2f} m2")
                feedback.pushInfo(f"  - Con perdidas ({porcentaje_perdidas:.1f}%): {area_comercial:.2f} m2")
            
            return {
                'area_agarre': area_agarre,
                'area_paredes': area_paredes,
                'area_fondo': area_fondo,
                'area_neta': area_neta,
                'area_comercial': area_comercial,
                'longitud_inclinada': longitud_inclinada,
                'perimetro_superior': perimetro_superior,
                'perimetro_base': perimetro_base,
                'metodo_usado': metodo_usado,
                'agarre_usado': agarre_lateral,
                'perdidas_porcentaje': porcentaje_perdidas
            }
            
        except Exception as e:
            if feedback:
                feedback.pushInfo(f"Error calculando revestimiento: {str(e)}")
            return {
                'area_agarre': 0,
                'area_paredes': 0,
                'area_fondo': 0,
                'area_neta': 0,
                'area_comercial': 0,
                'longitud_inclinada': 0,
                'perimetro_superior': 0,
                'perimetro_base': 0,
                'metodo_usado': 'Error',
                'agarre_usado': agarre_lateral,
                'perdidas_porcentaje': porcentaje_perdidas
            }

    def crear_feature_principal(self, feature_orig, fields, datos, prof_total, altura_seg, piso_muerto, relacion_talud):
        try:
            nueva_feature = QgsFeature(fields)
            nueva_feature.setGeometry(feature_orig.geometry())
            
            atributos = feature_orig.attributes() + [
                datos['area_superior'],
                datos['area_base'],
                datos['area_util'],
                datos['perimetro'],
                datos['volumen_util'],
                datos['volumen_total'],
                datos['volumen_muerto'],
                datos['volumen_util'] * 1000,
                datos['volumen_total'] * 1000,
                datos['volumen_muerto'] * 1000,
                prof_total - altura_seg - piso_muerto,
                prof_total * relacion_talud,
                datos['relacion_areas'],
                datos['area_revestimiento']['area_neta'],
                datos['area_revestimiento']['area_comercial'],
                datos['valido']
            ]
            
            nueva_feature.setAttributes(atributos)
            return nueva_feature
            
        except Exception:
            return None

    def generar_capa_combinada(self, feature_orig, fields, datos, prof_total, altura_seg, piso_muerto, relacion_talud, sink):
        try:
            # 1. Superficie (nivel máximo)
            f_superficie = QgsFeature(fields)
            f_superficie.setGeometry(feature_orig.geometry())
            atributos_sup = feature_orig.attributes() + [
                "Superficie", datos['area_superior'], datos['perimetro'],
                0.0, prof_total, 0.0, datos['volumen_total'], datos['volumen_total'] * 1000,
                "Borde superior - Capacidad maxima"
            ]
            f_superficie.setAttributes(atributos_sup)
            sink.addFeature(f_superficie)
            
            # 2. Nivel útil (superficie del agua)
            if datos.get('geom_util'):
                f_util = QgsFeature(fields)
                f_util.setGeometry(datos['geom_util'])
                atributos_util = feature_orig.attributes() + [
                    "Nivel util", datos['area_util'], datos['geom_util'].length(),
                    altura_seg, prof_total - altura_seg, altura_seg * relacion_talud,
                    datos['volumen_util'], datos['volumen_util'] * 1000,
                    "Superficie del agua - Volumen bombeable"
                ]
                f_util.setAttributes(atributos_util)
                sink.addFeature(f_util)
            
            # 3. Nivel piso muerto
            if datos.get('geom_piso_muerto'):
                f_piso = QgsFeature(fields)
                f_piso.setGeometry(datos['geom_piso_muerto'])
                atributos_piso = feature_orig.attributes() + [
                    "Nivel piso muerto", datos['area_piso_muerto'], datos['geom_piso_muerto'].length(),
                    prof_total - piso_muerto, piso_muerto, (prof_total - piso_muerto) * relacion_talud,
                    datos['volumen_muerto'], datos['volumen_muerto'] * 1000,
                    "Limite de bombeo - Volumen sedimentos"
                ]
                f_piso.setAttributes(atributos_piso)
                sink.addFeature(f_piso)
            
            # 4. Base inferior (fondo)
            if datos.get('geom_base'):
                f_base = QgsFeature(fields)
                f_base.setGeometry(datos['geom_base'])
                atributos_base = feature_orig.attributes() + [
                    "Base inferior", datos['area_base'], datos['geom_base'].length(),
                    prof_total, 0.0, prof_total * relacion_talud,
                    0.0, 0.0, "Fondo excavacion - Base estructural"
                ]
                f_base.setAttributes(atributos_base)
                sink.addFeature(f_base)
                
        except Exception as e:
            if feedback:
                feedback.pushInfo(f"Error generando capa combinada: {str(e)}")

    def generar_capa_3d(self, feature_orig, fields, datos, prof_total, altura_seg, piso_muerto, relacion_talud, sink):
        try:
            elev_superficie = 0.0
            elev_nivel_util = -altura_seg
            elev_piso_muerto = -(prof_total - piso_muerto)
            elev_base = -prof_total
            
            def convertir_a_3d(geometria, elevacion):
                if not geometria or geometria.isEmpty():
                    return None
                
                try:
                    if geometria.wkbType() == QgsWkbTypes.Polygon:
                        polygon = geometria.asPolygon()
                        if polygon and len(polygon) > 0:
                            coords_wkt = []
                            for punto in polygon[0]:
                                coords_wkt.append(f"{punto.x()} {punto.y()} {elevacion}")
                            
                            wkt_3d = f"POLYGONZ(({','.join(coords_wkt)}))"
                            geom_3d = QgsGeometry.fromWkt(wkt_3d)
                            return geom_3d
                except Exception:
                    pass
                
                return None
            
            def crear_paredes_laterales(geom_superior, geom_inferior, elev_superior, elev_inferior, nombre_pared):
                """Crear las paredes laterales entre dos niveles"""
                if not geom_superior or not geom_inferior or geom_superior.isEmpty() or geom_inferior.isEmpty():
                    return []
                
                paredes = []
                try:
                    poly_sup = geom_superior.asPolygon()[0]
                    poly_inf = geom_inferior.asPolygon()[0]
                    
                    # Crear segmentos de pared entre cada par de puntos adyacentes
                    for i in range(len(poly_sup) - 1):
                        # Puntos del segmento superior
                        p1_sup = poly_sup[i]
                        p2_sup = poly_sup[i + 1]
                        
                        # Encontrar los puntos correspondientes en el polígono inferior
                        factor = i / (len(poly_sup) - 1)
                        idx_inf = int(factor * (len(poly_inf) - 1))
                        idx_inf_next = min(idx_inf + 1, len(poly_inf) - 1)
                        
                        p1_inf = poly_inf[idx_inf]
                        p2_inf = poly_inf[idx_inf_next]
                        
                        # Crear polígono de pared (cuadrilátero)
                        coords_pared = [
                            f"{p1_sup.x()} {p1_sup.y()} {elev_superior}",
                            f"{p2_sup.x()} {p2_sup.y()} {elev_superior}",
                            f"{p2_inf.x()} {p2_inf.y()} {elev_inferior}",
                            f"{p1_inf.x()} {p1_inf.y()} {elev_inferior}",
                            f"{p1_sup.x()} {p1_sup.y()} {elev_superior}"  # Cerrar polígono
                        ]
                        
                        wkt_pared = f"POLYGONZ(({','.join(coords_pared)}))"
                        geom_pared = QgsGeometry.fromWkt(wkt_pared)
                        
                        if geom_pared and not geom_pared.isEmpty():
                            f_pared = QgsFeature(fields)
                            f_pared.setGeometry(geom_pared)
                            atributos = feature_orig.attributes() + [
                                f"Pared {nombre_pared} {i+1}", (elev_superior + elev_inferior) / 2, 
                                geom_pared.area(), geom_pared.length(), 
                                f"Pared lateral {nombre_pared}", "#8B4513"
                            ]
                            f_pared.setAttributes(atributos)
                            paredes.append(f_pared)
                
                except Exception:
                    pass
                
                return paredes
            
            # 1. Superficie (nivel 0) - Solo borde, no relleno
            geom_3d_superficie = convertir_a_3d(feature_orig.geometry(), elev_superficie)
            if geom_3d_superficie:
                f_superficie = QgsFeature(fields)
                f_superficie.setGeometry(geom_3d_superficie)
                atributos = feature_orig.attributes() + [
                    "Superficie", elev_superficie, datos['area_superior'], 
                    datos['perimetro'], "Borde superior de la balsa", "#1f77b4"
                ]
                f_superficie.setAttributes(atributos)
                sink.addFeature(f_superficie)
            
            # 2. Nivel útil
            if datos.get('geom_util'):
                geom_3d_util = convertir_a_3d(datos['geom_util'], elev_nivel_util)
                if geom_3d_util:
                    f_util = QgsFeature(fields)
                    f_util.setGeometry(geom_3d_util)
                    atributos = feature_orig.attributes() + [
                        "Nivel util", elev_nivel_util, datos['area_util'],
                        datos['geom_util'].length(), "Superficie del agua", "#4A90E2"
                    ]
                    f_util.setAttributes(atributos)
                    sink.addFeature(f_util)
                
                # Paredes entre superficie y nivel útil
                paredes_sup_util = crear_paredes_laterales(
                    feature_orig.geometry(), datos['geom_util'], 
                    elev_superficie, elev_nivel_util, "Superior"
                )
                for pared in paredes_sup_util:
                    sink.addFeature(pared)
            
            # 3. Nivel piso muerto
            if datos.get('geom_piso_muerto'):
                geom_3d_piso = convertir_a_3d(datos['geom_piso_muerto'], elev_piso_muerto)
                if geom_3d_piso:
                    f_piso = QgsFeature(fields)
                    f_piso.setGeometry(geom_3d_piso)
                    atributos = feature_orig.attributes() + [
                        "Piso muerto", elev_piso_muerto, datos['area_piso_muerto'],
                        datos['geom_piso_muerto'].length(), "Limite de bombeo", "#2ca02c"
                    ]
                    f_piso.setAttributes(atributos)
                    sink.addFeature(f_piso)
                
                # Paredes entre nivel útil y piso muerto
                if datos.get('geom_util'):
                    paredes_util_piso = crear_paredes_laterales(
                        datos['geom_util'], datos['geom_piso_muerto'],
                        elev_nivel_util, elev_piso_muerto, "Intermedia"
                    )
                    for pared in paredes_util_piso:
                        sink.addFeature(pared)
            
            # 4. Base (fondo) - Superficie sólida
            if datos.get('geom_base'):
                geom_3d_base = convertir_a_3d(datos['geom_base'], elev_base)
                if geom_3d_base:
                    f_base = QgsFeature(fields)
                    f_base.setGeometry(geom_3d_base)
                    atributos = feature_orig.attributes() + [
                        "Base", elev_base, datos['area_base'],
                        datos['geom_base'].length(), "Fondo de excavacion", "#654321"
                    ]
                    f_base.setAttributes(atributos)
                    sink.addFeature(f_base)
                
                # Paredes entre piso muerto y base
                if datos.get('geom_piso_muerto'):
                    paredes_piso_base = crear_paredes_laterales(
                        datos['geom_piso_muerto'], datos['geom_base'],
                        elev_piso_muerto, elev_base, "Inferior"
                    )
                    for pared in paredes_piso_base:
                        sink.addFeature(pared)
                elif datos.get('geom_util'):
                    # Si no hay piso muerto, conectar directamente util con base
                    paredes_util_base = crear_paredes_laterales(
                        datos['geom_util'], datos['geom_base'],
                        elev_nivel_util, elev_base, "Lateral"
                    )
                    for pared in paredes_util_base:
                        sink.addFeature(pared)
                    
        except Exception as e:
            if feedback:
                feedback.pushInfo(f"Error generando capa 3D: {str(e)}")

    def name(self):
        return 'calcular_volumen_balsa_v3'

    def displayName(self):
        return 'Calcular Volumen de Balsa v3.0 con 3D'
        
    def group(self):
        return self.tr('Hidrologia y Riego')

    def groupId(self):
        return 'hidrologia_riego'

    def shortHelpString(self):
        return self.tr("""
        <h3>Calcular Volumen de Balsa v3.0 con 3D</h3>
        <p>Calcula volumenes y area de revestimiento para balsas de riego.</p>
        
        <h4>Calculos incluidos:</h4>
        <ul>
            <li><b>Volumenes:</b> Total, util y piso muerto</li>
            <li><b>Areas:</b> Superficie, nivel util y base</li>
            <li><b>Geomembrana:</b> Agarre + paredes + fondo (NO superficie del agua)</li>
        </ul>
        
        <h4>Componentes de geomembrana:</h4>
        <ul>
            <li><b>Agarre lateral:</b> Franja de anclaje en bordes superiores</li>
            <li><b>Paredes inclinadas:</b> Revestimiento interior segun talud</li>
            <li><b>Fondo:</b> Base de la excavacion</li>
            <li><b>Perdidas:</b> Porcentaje adicional por cortes y desperdicios</li>
        </ul>
        
        <h4>Salidas disponibles:</h4>
        <ul>
            <li><b>Capa principal:</b> Datos completos de volumenes y revestimiento</li>
            <li><b>Capa combinada:</b> 4 niveles por separado (2D)</li>
            <li><b>Capa 3D:</b> Geometrias con elevacion Z para vista 3D de QGIS</li>
        </ul>
        
        <h4>Vista 3D en QGIS:</h4>
        <ol>
            <li>Activar la capa 3D generada</li>
            <li>Ir a Vista - Nueva vista de mapa 3D</li>
            <li>Configurar extrusion basada en elevacion Z</li>
            <li>Ajustar colores y transparencias</li>
        </ol>
        """)

    def tr(self, string):
        return QCoreApplication.translate('Processing', string)

    def createInstance(self):
        return CalcularVolumenBalsaV3()