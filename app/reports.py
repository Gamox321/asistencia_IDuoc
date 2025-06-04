"""
Sistema de Reportes y Dashboard
Sistema de Asistencia DuocUC
"""

from datetime import datetime, timedelta, date
from .database import db
import pandas as pd
from io import BytesIO
import json

class ReportManager:
    """Gestor de reportes del sistema"""
    
    @staticmethod
    def get_dashboard_stats(profesor_id=None):
        """Obtener estadísticas para el dashboard"""
        try:
            with db.get_connection() as conexion:
                cursor = conexion.cursor(dictionary=True)
                
                stats = {}
                
                # Filtro por profesor si se especifica
                profesor_filter = "AND pc.profesor_id = %s" if profesor_id else ""
                profesor_params = (profesor_id,) if profesor_id else ()
                
                # 1. Total de clases
                cursor.execute(f"""
                    SELECT COUNT(*) as total
                    FROM clase c
                    JOIN profesor_clase pc ON c.id = pc.clase_id
                    JOIN periodo_academico pa ON c.periodo_academico_id = pa.id
                    WHERE pa.estado = 'activo' {profesor_filter}
                """, profesor_params)
                stats['total_clases'] = cursor.fetchone()['total']
                
                # 2. Total de estudiantes únicos
                cursor.execute(f"""
                    SELECT COUNT(DISTINCT ac.alumno_id) as total
                    FROM alumno_clase ac
                    JOIN clase c ON ac.clase_id = c.id
                    JOIN profesor_clase pc ON c.id = pc.clase_id
                    JOIN periodo_academico pa ON c.periodo_academico_id = pa.id
                    WHERE ac.estado = 'inscrito' AND pa.estado = 'activo' {profesor_filter}
                """, profesor_params)
                stats['total_estudiantes'] = cursor.fetchone()['total']
                
                # 3. Clases de hoy
                cursor.execute(f"""
                    SELECT COUNT(*) as total
                    FROM clase c
                    JOIN profesor_clase pc ON c.id = pc.clase_id
                    WHERE c.fecha = CURDATE() {profesor_filter}
                """, profesor_params)
                stats['clases_hoy'] = cursor.fetchone()['total']
                
                # 4. Promedio de asistencia general
                cursor.execute(f"""
                    SELECT 
                        AVG(CASE WHEN a.presente = 1 THEN 100.0 ELSE 0.0 END) as promedio
                    FROM asistencia a
                    JOIN clase c ON a.clase_id = c.id
                    JOIN profesor_clase pc ON c.id = pc.clase_id
                    JOIN periodo_academico pa ON c.periodo_academico_id = pa.id
                    WHERE pa.estado = 'activo' {profesor_filter}
                """, profesor_params)
                result = cursor.fetchone()
                stats['promedio_asistencia'] = round(result['promedio'] or 0, 1)
                
                # 5. Asistencia últimos 7 días
                cursor.execute(f"""
                    SELECT 
                        DATE(a.fecha_asistencia) as fecha,
                        COUNT(*) as total_registros,
                        SUM(CASE WHEN a.presente = 1 THEN 1 ELSE 0 END) as presentes
                    FROM asistencia a
                    JOIN clase c ON a.clase_id = c.id
                    JOIN profesor_clase pc ON c.id = pc.clase_id
                    WHERE a.fecha_asistencia >= DATE_SUB(CURDATE(), INTERVAL 7 DAY) {profesor_filter}
                    GROUP BY DATE(a.fecha_asistencia)
                    ORDER BY fecha DESC
                """, profesor_params)
                asistencia_diaria = cursor.fetchall()
                
                stats['asistencia_semanal'] = []
                for dia in asistencia_diaria:
                    porcentaje = (dia['presentes'] / dia['total_registros'] * 100) if dia['total_registros'] > 0 else 0
                    stats['asistencia_semanal'].append({
                        'fecha': dia['fecha'].strftime('%Y-%m-%d'),
                        'porcentaje': round(porcentaje, 1),
                        'presentes': dia['presentes'],
                        'total': dia['total_registros']
                    })
                
                return stats
                
        except Exception as e:
            print(f"Error obteniendo estadísticas: {e}")
            return {
                'total_clases': 0,
                'total_estudiantes': 0,
                'clases_hoy': 0,
                'promedio_asistencia': 0,
                'asistencia_semanal': []
            }
    
    @staticmethod
    def get_attendance_by_class(profesor_id=None, fecha_inicio=None, fecha_fin=None):
        """Obtener reporte de asistencia por clase"""
        try:
            with db.get_connection() as conexion:
                cursor = conexion.cursor(dictionary=True)
                
                # Construir filtros
                filters = ["pa.estado = 'activo'"]
                params = []
                
                if profesor_id:
                    filters.append("pc.profesor_id = %s")
                    params.append(profesor_id)
                
                if fecha_inicio:
                    filters.append("c.fecha >= %s")
                    params.append(fecha_inicio)
                
                if fecha_fin:
                    filters.append("c.fecha <= %s")
                    params.append(fecha_fin)
                
                where_clause = "WHERE " + " AND ".join(filters) if filters else ""
                
                cursor.execute(f"""
                    SELECT 
                        c.id,
                        c.nombre as clase_nombre,
                        c.fecha,
                        c.hora_inicio,
                        c.hora_fin,
                        s.codigo as seccion,
                        COUNT(DISTINCT ac.alumno_id) as total_inscritos,
                        COUNT(DISTINCT CASE WHEN a.presente = 1 THEN a.alumno_id END) as total_presentes,
                        COUNT(DISTINCT a.alumno_id) as total_registros,
                        ROUND(
                            (COUNT(DISTINCT CASE WHEN a.presente = 1 THEN a.alumno_id END) / 
                             COUNT(DISTINCT a.alumno_id) * 100), 1
                        ) as porcentaje_asistencia
                    FROM clase c
                    JOIN profesor_clase pc ON c.id = pc.clase_id
                    JOIN seccion s ON c.seccion_id = s.id
                    JOIN periodo_academico pa ON c.periodo_academico_id = pa.id
                    LEFT JOIN alumno_clase ac ON c.id = ac.clase_id AND ac.estado = 'inscrito'
                    LEFT JOIN asistencia a ON c.id = a.clase_id
                    {where_clause}
                    GROUP BY c.id, c.nombre, c.fecha, c.hora_inicio, c.hora_fin, s.codigo
                    ORDER BY c.fecha DESC, c.hora_inicio DESC
                """, params)
                
                return cursor.fetchall()
                
        except Exception as e:
            print(f"Error generando reporte de asistencia: {e}")
            return []
    
    @staticmethod
    def get_student_attendance_summary(profesor_id=None, clase_id=None):
        """Obtener resumen de asistencia por estudiante"""
        try:
            with db.get_connection() as conexion:
                cursor = conexion.cursor(dictionary=True)
                
                # Construir filtros
                filters = ["pa.estado = 'activo'", "ac.estado = 'inscrito'"]
                params = []
                
                if profesor_id:
                    filters.append("pc.profesor_id = %s")
                    params.append(profesor_id)
                
                if clase_id:
                    filters.append("c.id = %s")
                    params.append(clase_id)
                
                where_clause = "WHERE " + " AND ".join(filters)
                
                cursor.execute(f"""
                    SELECT 
                        al.id,
                        al.rut,
                        CONCAT(al.nombre, ' ', al.apellido_paterno, ' ', COALESCE(al.apellido_materno, '')) as nombre_completo,
                        car.nombre as carrera,
                        COUNT(DISTINCT c.id) as total_clases,
                        COUNT(DISTINCT CASE WHEN a.presente = 1 THEN c.id END) as clases_asistidas,
                        COUNT(DISTINCT CASE WHEN a.presente = 0 THEN c.id END) as clases_ausente,
                        ROUND(
                            (COUNT(DISTINCT CASE WHEN a.presente = 1 THEN c.id END) / 
                             COUNT(DISTINCT c.id) * 100), 1
                        ) as porcentaje_asistencia
                    FROM alumno al
                    JOIN carrera car ON al.carrera_id = car.id
                    JOIN alumno_clase ac ON al.id = ac.alumno_id
                    JOIN clase c ON ac.clase_id = c.id
                    JOIN profesor_clase pc ON c.id = pc.clase_id
                    JOIN periodo_academico pa ON c.periodo_academico_id = pa.id
                    LEFT JOIN asistencia a ON al.id = a.alumno_id AND c.id = a.clase_id
                    {where_clause}
                    GROUP BY al.id, al.rut, al.nombre, al.apellido_paterno, al.apellido_materno, car.nombre
                    ORDER BY porcentaje_asistencia DESC, al.apellido_paterno, al.nombre
                """, params)
                
                return cursor.fetchall()
                
        except Exception as e:
            print(f"Error generando resumen de estudiantes: {e}")
            return []
    
    @staticmethod
    def export_to_excel(data, columns, filename="reporte.xlsx"):
        """Exportar datos a Excel"""
        try:
            # Crear DataFrame
            df = pd.DataFrame(data)
            
            if df.empty:
                return None
            
            # Renombrar columnas si se proporcionan
            if columns:
                df.columns = columns
            
            # Crear archivo Excel en memoria
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='Reporte', index=False)
                
                # Obtener el workbook y worksheet para formatear
                workbook = writer.book
                worksheet = writer.sheets['Reporte']
                
                # Autoajustar ancho de columnas
                for column in worksheet.columns:
                    max_length = 0
                    column_letter = column[0].column_letter
                    for cell in column:
                        try:
                            if len(str(cell.value)) > max_length:
                                max_length = len(str(cell.value))
                        except:
                            pass
                    adjusted_width = min(max_length + 2, 50)
                    worksheet.column_dimensions[column_letter].width = adjusted_width
            
            output.seek(0)
            return output
            
        except Exception as e:
            print(f"Error exportando a Excel: {e}")
            return None
    
    @staticmethod
    def get_low_attendance_alerts(min_percentage=75):
        """Obtener alertas de baja asistencia"""
        try:
            with db.get_connection() as conexion:
                cursor = conexion.cursor(dictionary=True)
                
                cursor.execute("""
                    SELECT 
                        al.id,
                        al.rut,
                        CONCAT(al.nombre, ' ', al.apellido_paterno, ' ', COALESCE(al.apellido_materno, '')) as nombre_completo,
                        c.nombre as clase_nombre,
                        s.codigo as seccion,
                        COUNT(DISTINCT CASE WHEN a.clase_id IS NOT NULL THEN c.id END) as total_clases_registradas,
                        COUNT(DISTINCT CASE WHEN a.presente = 1 THEN c.id END) as clases_asistidas,
                        ROUND(
                            (COUNT(DISTINCT CASE WHEN a.presente = 1 THEN c.id END) / 
                             COUNT(DISTINCT CASE WHEN a.clase_id IS NOT NULL THEN c.id END) * 100), 1
                        ) as porcentaje_asistencia
                    FROM alumno al
                    JOIN alumno_clase ac ON al.id = ac.alumno_id
                    JOIN clase c ON ac.clase_id = c.id
                    JOIN seccion s ON c.seccion_id = s.id
                    JOIN periodo_academico pa ON c.periodo_academico_id = pa.id
                    LEFT JOIN asistencia a ON al.id = a.alumno_id AND c.id = a.clase_id
                    WHERE ac.estado = 'inscrito' AND pa.estado = 'activo'
                    GROUP BY al.id, al.rut, al.nombre, al.apellido_paterno, al.apellido_materno, c.id, c.nombre, s.codigo
                    HAVING COUNT(DISTINCT CASE WHEN a.clase_id IS NOT NULL THEN c.id END) > 0
                    AND porcentaje_asistencia < %s
                    ORDER BY porcentaje_asistencia ASC
                """, (min_percentage,))
                
                return cursor.fetchall()
                
        except Exception as e:
            print(f"Error obteniendo alertas de baja asistencia: {e}")
            return [] 