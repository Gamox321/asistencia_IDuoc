from flask import Blueprint, jsonify
from app.db import get_db
from app.auth import admin_required

bp = Blueprint('api', __name__, url_prefix='/api')

@bp.route('/alumnos_clase/<int:clase_id>')
@admin_required
def alumnos_clase(clase_id):
    """Obtener lista de alumnos de una clase"""
    try:
        with get_db() as conexion:
            cursor = conexion.cursor(dictionary=True)
            
            cursor.execute("""
                SELECT a.id, a.nombre, a.apellido_paterno
                FROM alumno a
                JOIN alumno_clase ac ON a.id = ac.alumno_id
                WHERE ac.clase_id = %s
                ORDER BY a.apellido_paterno, a.nombre
            """, (clase_id,))
            alumnos = cursor.fetchall()
            
            return jsonify(alumnos)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500 