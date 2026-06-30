"""
Utilidades adicionales para el módulo de extracción de alturas
"""
import math
import os
from qgis.core import (
    QgsVectorLayer, QgsRasterLayer, QgsProject, QgsCoordinateReferenceSystem,
    QgsCoordinateTransform, QgsPointXY, QgsGeometry, QgsFeature
)
# Cambio a la capa de compatibilidad dinámica de QGIS
from qgis.PyQt.QtWidgets import QMessageBox


class AlturaUtils:
    """Clase con utilidades adicionales para trabajar con alturas"""
    
    @staticmethod
    def validar_crs_compatibilidad(capa_vector, capa_raster):
        """Verifica si las capas tienen CRS compatibles"""
        try:
            crs_vector = capa_vector.crs()
            crs_raster = capa_raster.crs()
            
            # Si son exactamente iguales
            if crs_vector.authid() == crs_raster.authid():
                return True, "CRS idénticos"
            
            # Si uno es geográfico y otro proyectado pero en la misma zona
            if crs_vector.isGeographic() != crs_raster.isGeographic():
                return True, "CRS compatibles (geográfico/proyectado)"
            
            # Advertencia si son diferentes
            return False, f"CRS diferentes: Vector={crs_vector.authid()}, Raster={crs_raster.authid()}"
            
        except Exception as e:
            return False, f"Error verificando CRS: {str(e)}"
    
    @staticmethod
    def transformar_punto_si_necesario(punto, crs_origen, crs_destino):
        """Transforma un punto entre sistemas de coordenadas si es necesario"""
        try:
            if crs_origen.authid() == crs_destino.authid():
                return punto
            
            transformador = QgsCoordinateTransform(
                crs_origen, crs_destino, QgsProject.instance()
            )
            punto_transformado = transformador.transform(punto)
            return punto_transformado
            
        except Exception as e:
            print(f"Error transformando punto: {str(e)}")
            return punto
    
    @staticmethod
    def calcular_pendiente_grados(diferencia_altura, longitud_horizontal):
        """Calcula la pendiente en grados"""
        try:
            if longitud_horizontal <= 0:
                return None
            
            pendiente_radianes = math.atan(diferencia_altura / longitud_horizontal)
            pendiente_grados = math.degrees(pendiente_radianes)
            return pendiente_grados
            
        except Exception as e:
            print(f"Error calculando pendiente en grados: {str(e)}")
            return None
    
    @staticmethod
    def clasificar_pendiente(pendiente_porcentaje):
        """Clasifica la pendiente según rangos estándar"""
        try:
            if pendiente_porcentaje is None:
                return "No definida"
            
            pendiente_abs = abs(pendiente_porcentaje)
            
            if pendiente_abs < 0.5:
                return "Muy suave"
            elif pendiente_abs < 2.0:
                return "Suave"
            elif pendiente_abs < 5.0:
                return "Moderada"
            elif pendiente_abs < 10.0:
                return "Pronunciada"
            elif pendiente_abs < 20.0:
                return "Muy pronunciada"
            else:
                return "Extrema"
                
        except Exception as e:
            print(f"Error clasificando pendiente: {str(e)}")
            return "Error"
    
    @staticmethod
    def detectar_problemas_hidraulicos(altura_inicial, altura_final, longitud, tolerancia_contrapendiente=0.1):
        """Detecta posibles problemas hidráulicos en el tramo"""
        problemas = []
        
        try:
            if altura_inicial is None or altura_final is None:
                problemas.append("Alturas no disponibles")
                return problemas
            
            diferencia = altura_final - altura_inicial
            pendiente_pct = (diferencia / longitud) * 100 if longitud > 0 else 0
            
            # Detectar contrapendiente significativa
            if diferencia > tolerancia_contrapendiente:
                problemas.append(f"Contrapendiente: +{diferencia:.2f}m ({pendiente_pct:.2f}%)")
            
            # Detectar pendiente excesiva
            if abs(pendiente_pct) > 15:
                problemas.append(f"Pendiente excesiva: {pendiente_pct:.2f}%")
            
            # Detectar pendiente insuficiente
            if abs(pendiente_pct) < 0.1:
                problemas.append(f"Pendiente muy baja: {pendiente_pct:.4f}%")
            
            return problemas
            
        except Exception as e:
            return [f"Error análisis: {str(e)}"]
    
    @staticmethod
    def generar_perfil_longitudinal(geometria_linea, dem_layer, num_puntos=50):
        """Genera un perfil longitudinal de la línea con más puntos intermedios"""
        try:
            if geometria_linea.isMultipart():
                linea = geometria_linea.asMultiPolyline()[0]
            else:
                linea = geometria_linea.asPolyline()
            
            if len(linea) < 2:
                return None
            
            # Calcular longitud total
            longitud_total = geometria_linea.length()
            
            # Generar puntos equidistantes
            perfil = []
            for i in range(num_puntos + 1):
                distancia = (i / num_puntos) * longitud_total
                punto = geometria_linea.interpolate(distancia)
                
                if punto and not punto.isEmpty():
                    punto_xy = punto.asPoint()
                    altura = dem_layer.dataProvider().sample(punto_xy, 1)
                    
                    perfil.append({
                        'distancia': distancia,
                        'punto': punto_xy,
                        'altura': altura[1] if altura[0] else None
                    })
            
            return perfil
            
        except Exception as e:
            print(f"Error generando perfil longitudinal: {str(e)}")
            return None
    
    @staticmethod
    def calcular_volumen_excavacion_aproximado(perfil, ancho_zanja=0.6, profundidad_zanja=0.8):
        """Calcula un volumen aproximado de excavación basado en el perfil"""
        try:
            if not perfil or len(perfil) < 2:
                return None
            
            volumen_total = 0
            
            for i in range(len(perfil) - 1):
                punto_actual = perfil[i]
                punto_siguiente = perfil[i + 1]
                
                if punto_actual['altura'] is not None and punto_siguiente['altura'] is not None:
                    # Distancia entre puntos
                    distancia = punto_siguiente['distancia'] - punto_actual['distancia']
                    
                    # Área promedio de la sección
                    area_seccion = ancho_zanja * profundidad_zanja
                    
                    # Volumen del segmento
                    volumen_segmento = area_seccion * distancia
                    volumen_total += volumen_segmento
            
            return volumen_total
            
        except Exception as e:
            print(f"Error calculando volumen de excavación: {str(e)}")
            return None
    
    @staticmethod
    def exportar_perfil_csv(perfil, ruta_archivo):
        """Exporta el perfil longitudinal a un archivo CSV"""
        try:
            import csv
            
            with open(ruta_archivo, 'w', newline='', encoding='utf-8') as archivo:
                writer = csv.writer(archivo)
                
                # Escribir encabezados
                writer.writerow(['Distancia_m', 'X', 'Y', 'Altura_m'])
                
                # Escribir datos
                for punto in perfil:
                    if punto['altura'] is not None:
                        writer.writerow([
                            round(punto['distancia'], 2),
                            round(punto['punto'].x(), 2),
                            round(punto['punto'].y(), 2),
                            round(punto['altura'], 2)
                        ])
            
            return True
            
        except Exception as e:
            print(f"Error exportando perfil a CSV: {str(e)}")
            return False
    
    @staticmethod
    def validar_dem_calidad(dem_layer, muestra_puntos=100):
        """Valida la calidad básica del DEM"""
        try:
            resultado = {
                'valido': True,
                'advertencias': [],
                'estadisticas': {}
            }
            
            # Obtener estadísticas básicas
            stats = dem_layer.dataProvider().bandStatistics(1)
            
            resultado['estadisticas'] = {
                'min': stats.minimumValue,
                'max': stats.maximumValue,
                'media': stats.mean,
                'desviacion': stats.stdDev
            }
            
            # Verificar valores anómalos
            if stats.minimumValue < -500:
                resultado['advertencias'].append("Valores de elevación muy bajos detectados")
            
            if stats.maximumValue > 8000:
                resultado['advertencias'].append("Valores de elevación muy altos detectados")
            
            # Verificar resolución
            pixel_size = dem_layer.rasterUnitsPerPixelX()
            if pixel_size > 100:
                resultado['advertencias'].append(f"Resolución baja del DEM: {pixel_size:.1f}m/pixel")
            
            return resultado
            
        except Exception as e:
            return {
                'valido': False,
                'error': str(e),
                'advertencias': [],
                'estadisticas': {}
            }
    
    @staticmethod
    def crear_reporte_html(estadisticas, ruta_salida):
        """Crea un reporte HTML con los resultados"""
        try:
            html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Reporte de Análisis de Alturas - Red de Riego</title>
    <meta charset="utf-8">
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        .header {{ background-color: #2e7d32; color: white; padding: 15px; border-radius: 5px; }}
        .section {{ margin: 20px 0; padding: 15px; border: 1px solid #ddd; border-radius: 5px; }}
        .stats-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }}
        .stat-item {{ background-color: #f5f5f5; padding: 10px; border-radius: 3px; }}
        .warning {{ background-color: #fff3cd; border: 1px solid #ffeaa7; padding: 10px; border-radius: 3px; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Análisis de Alturas - Red de Riego</h1>
        <p>Reporte generado automáticamente</p>
    </div>
    
    <div class="section">
        <h2>Resumen General</h2>
        <div class="stats-grid">
            <div class="stat-item">
                <strong>Total de Tramos:</strong> {estadisticas.get('total_tramos', 'N/A')}
            </div>
            <div class="stat-item">
                <strong>Tramos Procesados:</strong> {estadisticas.get('alturas_procesadas', 'N/A')}
            </div>
            <div class="stat-item">
                <strong>Altura Mínima Inicial:</strong> {estadisticas.get('altura_min_inicial', 'N/A'):.2f} m
            </div>
            <div class="stat-item">
                <strong>Altura Máxima Inicial:</strong> {estadisticas.get('altura_max_inicial', 'N/A'):.2f} m
            </div>
            <div class="stat-item">
                <strong>Altura Mínima Final:</strong> {estadisticas.get('altura_min_final', 'N/A'):.2f} m
            </div>
            <div class="stat-item">
                <strong>Altura Máxima Final:</strong> {estadisticas.get('altura_max_final', 'N/A'):.2f} m
            </div>
            <div class="stat-item">
                <strong>Pendiente Mínima:</strong> {estadisticas.get('pendiente_min', 'N/A'):.4f}%
            </div>
            <div class="stat-item">
                <strong>Pendiente Máxima:</strong> {estadisticas.get('pendiente_max', 'N/A'):.4f}%
            </div>
        </div>
    </div>
    
    <div class="section">
        <h2>Observaciones</h2>
        <p>Este análisis proporciona información básica sobre las alturas extraídas del DEM para la red de riego.</p>
        <p>Se recomienda revisar los tramos con pendientes extremas o contrapendientes significativas.</p>
    </div>
</body>
</html>
            """
            
            with open(ruta_salida, 'w', encoding='utf-8') as archivo:
                archivo.write(html_content)
            
            return True
            
        except Exception as e:
            print(f"Error creando reporte HTML: {str(e)}")
            return False