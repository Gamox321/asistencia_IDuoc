import face_recognition
import pickle
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify, send_file
import mysql.connector
from mysql.connector import Error
from PIL import Image
import base64
import io
import os
import hashlib
import numpy as np
from datetime import datetime, date, timedelta
from .config import Config
from .database import db
from .auth import SecurityManager, PasswordMigrator, require_login, get_current_user_id
from .roles import RoleManager, professor_required, coordinator_required, get_user_role_context
from .reports import ReportManager

# Crear Blueprint para las rutas
bp = Blueprint('main', __name__)

def get_db():
    """Función helper para obtener conexión a la base de datos MySQL"""
    return db.get_connection()

def timedelta_to_time_string(td):
    """Convertir timedelta a string de tiempo HH:MM"""
    if td is None:
        return ""
    if isinstance(td, timedelta):
        total_seconds = int(td.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        return f"{hours:02d}:{minutes:02d}"
    else:
        # Si ya es un string o tiene strftime, usarlo directamente
        try:
            return td.strftime('%H:%M')
        except:
            return str(td)

# ---------- LOGIN MEJORADO ----------
@bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        # Obtener información del cliente
        ip_address, user_agent = SecurityManager.get_client_info()

        # Verificar si la cuenta está bloqueada
        if SecurityManager.is_account_locked(username):
            flash('Cuenta bloqueada por múltiples intentos fallidos. Intenta en 15 minutos.', 'error')
            SecurityManager.log_login_attempt(username, False, ip_address, user_agent)
            return render_template('login.html')

        try:
            with get_db() as conexion:
                cursor = conexion.cursor(dictionary=True)
                cursor.execute("""
                    SELECT a.id, a.password_hash, a.tipo_usuario,
                           p.id as profesor_id, p.nombre, p.apellido_paterno, p.apellido_materno, p.usuario
                    FROM autenticacion a
                    JOIN profesor p ON a.profesor_id = p.id
                    WHERE a.usuario = %s AND p.estado = 'activo'
                """, (username,))
                usuario_data = cursor.fetchone()

            if usuario_data:
                password_hash = usuario_data['password_hash']
                
                # Verificar si necesita migración de contraseña
                if not PasswordMigrator.is_bcrypt_hash(password_hash):
                    # Es hash SHA256, verificar con método anterior
                    password_hashed_sha = hashlib.sha256(password.encode()).hexdigest()
                    password_valid = password_hash == password_hashed_sha
                    
                    # Si es válido, migrar a bcrypt
                    if password_valid:
                        new_hash = SecurityManager.hash_password(password)
                        try:
                            with get_db() as conexion:
                                cursor = conexion.cursor()
                                cursor.execute("""
                                    UPDATE autenticacion 
                                    SET password_hash = %s 
                                    WHERE id = %s
                                """, (new_hash, usuario_data['id']))
                                conexion.commit()
                                print(f"✅ Contraseña migrada para usuario: {username}")
                        except Error as e:
                            print(f"Error migrando contraseña: {e}")
                else:
                    # Es hash bcrypt
                    password_valid = SecurityManager.check_password(password, password_hash)
                
                if password_valid:
                    # Login exitoso
                    SecurityManager.clear_failed_attempts(username)
                    SecurityManager.log_login_attempt(username, True, ip_address, user_agent)
                    
                    # Crear sesión segura
                    SecurityManager.create_session(usuario_data['profesor_id'], usuario_data)
                    
                    # Actualizar último login
                    try:
                        with get_db() as conexion:
                            cursor = conexion.cursor()
                            cursor.execute("""
                                UPDATE autenticacion 
                                SET ultimo_login = CURRENT_TIMESTAMP 
                                WHERE usuario = %s
                            """, (username,))
                            conexion.commit()
                    except Error as e:
                        print(f"Error actualizando último login: {e}")
                    
                    flash(f'Bienvenido, {usuario_data["nombre"]}!', 'success')
                    return redirect(url_for('main.home'))
                else:
                    # Contraseña incorrecta
                    SecurityManager.log_login_attempt(username, False, ip_address, user_agent)
                    flash('Usuario o contraseña incorrectos', 'error')
            else:
                # Usuario no encontrado
                SecurityManager.log_login_attempt(username, False, ip_address, user_agent)
                flash('Usuario o contraseña incorrectos', 'error')
        
        except Error as e:
            print(f"Error en login: {e}")
            SecurityManager.log_login_attempt(username, False, ip_address, user_agent)
            flash('Error de conexión a la base de datos', 'error')

    return render_template('login.html')

@bp.route('/logout')
def logout():
    # Logout seguro
    SecurityManager.logout_user()
    flash('Sesión cerrada correctamente', 'info')
    return redirect(url_for('main.login'))

# ---------- VISTA PRINCIPAL MEJORADA ----------
@bp.route('/')
def home():
    if not require_login():
        return render_template('inicio_publico.html')
    
    # Verificar timeout de sesión
    if SecurityManager.check_session_timeout():
        flash('Tu sesión ha expirado', 'warning')
        return redirect(url_for('main.logout'))

    # Página para profesor autenticado
    try:
        profesor_id = get_current_user_id()
        nombre_profesor = session.get('nombre_profesor')
        
        if not profesor_id:
            return redirect(url_for('main.logout'))

        with get_db() as conexion:
            cursor = conexion.cursor(dictionary=True)
            cursor.execute("""
                SELECT c.id, c.nombre, c.fecha, c.hora_inicio, c.hora_fin, c.sala,
                       s.codigo as seccion_codigo, pa.año, pa.semestre
                FROM clase c
                JOIN profesor_clase pc ON c.id = pc.clase_id
                JOIN seccion s ON c.seccion_id = s.id
                JOIN periodo_academico pa ON c.periodo_academico_id = pa.id
                WHERE pc.profesor_id = %s AND pa.estado = 'activo'
                ORDER BY c.fecha DESC, c.hora_inicio DESC
            """, (profesor_id,))
            clases = cursor.fetchall()

        return render_template('index.html', nombre_profesor=nombre_profesor, clases=clases)
    
    except Error as e:
        print(f"Error en home: {e}")
        flash('Error cargando las clases', 'error')
        return redirect(url_for('main.logout'))

# ---------- VER CLASES MEJORADO ----------
@bp.route('/clases')
def ver_clases():
    if not require_login():
        return redirect(url_for('main.login'))
    
    # Verificar timeout de sesión
    if SecurityManager.check_session_timeout():
        flash('Tu sesión ha expirado', 'warning')
        return redirect(url_for('main.logout'))

    try:
        profesor_id = get_current_user_id()
        nombre_profesor = session.get('nombre_profesor')
        
        if not profesor_id:
            return redirect(url_for('main.logout'))

        with get_db() as conexion:
            cursor = conexion.cursor(dictionary=True)
            cursor.execute("""
                SELECT c.id, c.nombre, c.fecha, c.hora_inicio, c.hora_fin, c.sala,
                       s.codigo as seccion_codigo, pa.año, pa.semestre,
                       COUNT(ac.alumno_id) as total_alumnos
                FROM clase c
                JOIN profesor_clase pc ON c.id = pc.clase_id
                JOIN seccion s ON c.seccion_id = s.id
                JOIN periodo_academico pa ON c.periodo_academico_id = pa.id
                LEFT JOIN alumno_clase ac ON c.id = ac.clase_id AND ac.estado = 'inscrito'
                WHERE pc.profesor_id = %s AND pa.estado = 'activo'
                GROUP BY c.id, c.nombre, c.fecha, c.hora_inicio, c.hora_fin, c.sala, s.codigo, pa.año, pa.semestre
                ORDER BY c.fecha DESC, c.hora_inicio DESC
            """, (profesor_id,))
            clases = cursor.fetchall()

        return render_template('clases.html', nombre_profesor=nombre_profesor, clases=clases)
    
    except Error as e:
        print(f"Error en ver_clases: {e}")
        flash('Error cargando las clases', 'error')
        return redirect(url_for('main.home'))

# ---------- ASISTENCIA MEJORADA ----------
@bp.route('/asistencia/<int:clase_id>')
def asistencia(clase_id):
    if not require_login():
        return redirect(url_for('main.login'))
    
    # Verificar timeout de sesión
    if SecurityManager.check_session_timeout():
        flash('Tu sesión ha expirado', 'warning')
        return redirect(url_for('main.logout'))

    try:
        with get_db() as conexion:
            cursor = conexion.cursor(dictionary=True)
            
            # Verificar que el profesor tiene acceso a esta clase
            profesor_id = get_current_user_id()
            cursor.execute("""
                SELECT 1 FROM profesor_clase 
                WHERE profesor_id = %s AND clase_id = %s
            """, (profesor_id, clase_id))
            
            if not cursor.fetchone():
                flash('No tienes acceso a esta clase', 'error')
                return redirect(url_for('main.home'))
            
            # Obtener alumnos inscritos en la clase
            cursor.execute("""
                SELECT a.id, a.nombre, a.apellido_paterno, a.apellido_materno, a.rut
                FROM alumno a
                JOIN alumno_clase ac ON a.id = ac.alumno_id
                WHERE ac.clase_id = %s AND ac.estado = 'inscrito'
                ORDER BY a.apellido_paterno, a.apellido_materno, a.nombre
            """, (clase_id,))
            alumnos_raw = cursor.fetchall()
            
            # Formatear alumnos para compatibilidad con el template
            alumnos = []
            for a in alumnos_raw:
                alumnos.append({
                    "id": a['id'],
                    "nombre": f"{a['nombre']} {a['apellido_paterno']} {a['apellido_materno'] or ''}".strip(),
                    "rut": a['rut']
                })
            
            # Obtener todas las clases disponibles para el select
            cursor.execute("""
                SELECT c.id, c.nombre
                FROM clase c
                JOIN profesor_clase pc ON c.id = pc.clase_id
                WHERE pc.profesor_id = %s
                ORDER BY c.fecha DESC
            """, (profesor_id,))
            clases_disponibles = cursor.fetchall()

        return render_template('asistencia.html', 
                             alumnos=alumnos, 
                             clase_id=clase_id, 
                             clases=clases_disponibles)
    
    except Error as e:
        print(f"Error en asistencia: {e}")
        flash('Error cargando la información de asistencia', 'error')
        return redirect(url_for('main.home'))

# ---------- CONFIRMAR ASISTENCIA ----------
@bp.route('/confirmar_asistencia/<int:clase_id>', methods=['POST'])
def confirmar_asistencia(clase_id):
    if 'usuario' not in session:
        flash("Debes iniciar sesión para confirmar la asistencia.", "error")
        return redirect(url_for('main.login'))

    try:
        with get_db() as conexion:
            cursor = conexion.cursor(dictionary=True)

            # Verificar acceso del profesor
            profesor_id = session.get('profesor_id')
            cursor.execute("""
                SELECT 1 FROM profesor_clase 
                WHERE profesor_id = %s AND clase_id = %s
            """, (profesor_id, clase_id))
            
            if not cursor.fetchone():
                flash('No tienes acceso a esta clase', 'error')
                return redirect(url_for('main.home'))

            # Obtener la fecha de la clase
            cursor.execute("SELECT fecha FROM clase WHERE id = %s", (clase_id,))
            fecha_clase = cursor.fetchone()
            if not fecha_clase:
                flash("La clase especificada no existe.", "error")
                return redirect(url_for('main.home'))

            # Obtener todos los alumnos inscritos en la clase
            cursor.execute("""
                SELECT a.id
                FROM alumno a
                JOIN alumno_clase ac ON a.id = ac.alumno_id
                WHERE ac.clase_id = %s AND ac.estado = 'inscrito'
            """, (clase_id,))
            alumnos_en_clase = cursor.fetchall()

            if not alumnos_en_clase:
                flash(f"No hay alumnos inscritos en la clase para registrar asistencia.", "info")
                return redirect(url_for('main.asistencia', clase_id=clase_id))

            presentes = 0
            ausentes = 0

            # Registrar asistencia para cada alumno según su estado final
            for alumno in alumnos_en_clase:
                alumno_id = alumno['id']
                estado = request.form.get(f'estado_{alumno_id}', 'no-detectado')
                # Solo marcar como presente si alcanzó el estado "presente" (5 detecciones)
                presente = estado == 'presente'

                # Verificar si ya existe un registro para este alumno en esta clase y fecha
                cursor.execute("""
                    SELECT id FROM asistencia 
                    WHERE clase_id = %s AND alumno_id = %s AND fecha_asistencia = %s
                """, (clase_id, alumno_id, fecha_clase['fecha']))
                asistencia_existente = cursor.fetchone()

                if not asistencia_existente:
                    cursor.execute("""
                        INSERT INTO asistencia (clase_id, alumno_id, presente, fecha_asistencia, timestamp)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (clase_id, alumno_id, presente, fecha_clase['fecha'], fecha_clase['fecha']))
                    
                    if presente:
                        presentes += 1
                    else:
                        ausentes += 1

            conexion.commit()
            flash(f"Asistencia registrada correctamente: {presentes} presente(s), {ausentes} ausente(s).", "success")

    except Error as e:
        print(f"Error al registrar asistencia: {e}")
        flash(f"Error al registrar la asistencia: {str(e)}", "error")
        return redirect(url_for('main.asistencia', clase_id=clase_id))

    return redirect(url_for('main.asistencia', clase_id=clase_id))

# ---------- PROCESAR FOTOGRAMA ----------
@bp.route('/procesar_fotograma/<int:clase_id>', methods=['POST'])
def procesar_fotograma(clase_id):
    if 'usuario' not in session:
        return {"mensaje": "No autorizado"}, 401

    data = request.get_json()
    imagen_base64 = data.get('imagen')

    if not imagen_base64:
        return {"mensaje": "No se recibió ninguna imagen"}, 400

    try:
        # Decodificar y cargar la imagen
        header, encoded = imagen_base64.split(',', 1)
        imagen_bytes = base64.b64decode(encoded)
        imagen = face_recognition.load_image_file(io.BytesIO(imagen_bytes))
        
        # Detectar las ubicaciones de todos los rostros en la imagen
        face_locations = face_recognition.face_locations(imagen)
        if not face_locations:
            return {"mensaje": "No se detectó ningún rostro en la imagen"}, 400

        # Obtener los encodings de todos los rostros detectados
        encodings_capturados = face_recognition.face_encodings(imagen, face_locations)
        
        # Obtener los datos de los alumnos de la base de datos MySQL
        with get_db() as conexion:
            cursor = conexion.cursor(dictionary=True)
            cursor.execute("""
                SELECT a.id, a.datos_rostro
                FROM alumno a
                JOIN alumno_clase ac ON a.id = ac.alumno_id
                WHERE ac.clase_id = %s AND a.datos_rostro IS NOT NULL AND ac.estado = 'inscrito'
            """, (clase_id,))
            alumnos = cursor.fetchall()

        if not alumnos:
            return {"mensaje": "No hay alumnos registrados con datos faciales"}, 400

        # Preparar los datos de los alumnos
        alumnos_ids = []
        alumnos_encodings = []
        for alumno in alumnos:
            if alumno['datos_rostro']:
                alumnos_ids.append(alumno['id'])
                alumnos_encodings.append(pickle.loads(alumno['datos_rostro']))

        # Convertir a array de NumPy para procesamiento más eficiente
        alumnos_encodings = np.array(alumnos_encodings)
        
        # Inicializar diccionario para tracking de detecciones
        alumnos_detectados = {alumno_id: False for alumno_id in alumnos_ids}
        
        # Procesar cada rostro detectado
        for encoding_capturado in encodings_capturados:
            # Comparar con todos los alumnos de una vez usando NumPy
            coincidencias = face_recognition.compare_faces(alumnos_encodings, encoding_capturado, tolerance=0.5)
            
            # Actualizar el estado de detección para cada alumno que coincida
            for idx, coincide in enumerate(coincidencias):
                if coincide:
                    alumnos_detectados[alumnos_ids[idx]] = True

        # Formatear resultados para la respuesta
        resultados = [{"id": alumno_id, "detectado": detectado} 
                     for alumno_id, detectado in alumnos_detectados.items()]

        return {
            "alumnos": resultados,
            "rostros_detectados": len(face_locations),
            "coincidencias_encontradas": sum(1 for r in resultados if r["detectado"])
        }

    except Exception as e:
        return {"mensaje": f"Error al procesar la imagen: {str(e)}"}, 400

# ---------- INGRESAR DATOS FACIALES ----------
@bp.route('/ingresar_alumno/<int:clase_id>', methods=['GET', 'POST'])
def ingresar_alumno(clase_id):
    if 'usuario' not in session:
        return redirect(url_for('main.login'))

    mensaje = None

    if request.method == 'POST':
        for key in request.files:
            if key.startswith('foto_'):
                alumno_id = int(key.split('_')[1])
                imagen_file = request.files[key]
                if imagen_file and imagen_file.filename != '':
                    try:
                        imagen = face_recognition.load_image_file(imagen_file)
                        datos_rostro = procesar_imagen(imagen)
                        if datos_rostro is None:
                            mensaje = f"No se detectó rostro en la imagen para el alumno ID {alumno_id}."
                            # Registrar el intento fallido en MySQL
                            with get_db() as conexion:
                                cursor = conexion.cursor()
                                cursor.execute("""
                                    INSERT INTO registro_facial (alumno_id, estado, intentos)
                                    VALUES (%s, 'fallido', 1)
                                    ON DUPLICATE KEY UPDATE 
                                    estado = 'fallido',
                                    intentos = intentos + 1,
                                    updated_at = CURRENT_TIMESTAMP
                                """, (alumno_id,))
                                conexion.commit()
                        else:
                            guardar_datos_faciales(alumno_id, datos_rostro)
                            mensaje = f"Datos faciales registrados correctamente para el alumno ID {alumno_id}."
                    except Exception as e:
                        mensaje = f"Error al procesar la imagen: {str(e)}"

    # Obtener la lista de alumnos con su estado de registro
    try:
        with get_db() as conexion:
            cursor = conexion.cursor(dictionary=True)
            cursor.execute("""
                SELECT 
                    a.id, 
                    a.nombre, 
                    a.apellido_paterno,
                    a.apellido_materno,
                    a.rut,
                    CASE 
                        WHEN a.datos_rostro IS NOT NULL THEN 'registrado'
                        WHEN rf.estado = 'fallido' THEN 'fallido'
                        ELSE 'pendiente'
                    END as estado_registro,
                    COALESCE(rf.intentos, 0) as intentos,
                    rf.fecha_registro
                FROM alumno a
                JOIN alumno_clase ac ON a.id = ac.alumno_id
                LEFT JOIN registro_facial rf ON a.id = rf.alumno_id
                WHERE ac.clase_id = %s AND ac.estado = 'inscrito'
                ORDER BY a.apellido_paterno, a.apellido_materno, a.nombre
            """, (clase_id,))
            
            alumnos = cursor.fetchall()

        return render_template('ingresar_alumno.html', clase_id=clase_id, alumnos=alumnos, mensaje=mensaje)
    
    except Error as e:
        print(f"Error en ingresar_alumno: {e}")
        flash('Error cargando los alumnos', 'error')
        return redirect(url_for('main.home'))

# ---------- CAPTURAR FOTO ----------
@bp.route('/capturar_foto/<int:alumno_id>', methods=['POST'])
def capturar_foto(alumno_id):
    if 'usuario' not in session:
        return {"mensaje": "No autorizado"}, 401

    data = request.get_json()
    imagen_base64 = data.get('imagen')

    if not imagen_base64:
        return {"mensaje": "No se recibió ninguna imagen"}, 400

    try:
        # Decodificar la imagen base64
        header, encoded = imagen_base64.split(',', 1)
        imagen_bytes = base64.b64decode(encoded)
        imagen_stream = io.BytesIO(imagen_bytes)
        
        # Procesar la imagen para reconocimiento facial
        imagen_array = face_recognition.load_image_file(imagen_stream)
        datos_rostro = procesar_imagen(imagen_array)
        
        if datos_rostro is None:
            return {"mensaje": "No se detectó ningún rostro en la imagen"}, 400
            
        # Volver al inicio del stream para guardar la imagen
        imagen_stream.seek(0)
        imagen = Image.open(imagen_stream)
        
        # Convertir a RGB si la imagen está en modo RGBA
        if imagen.mode in ('RGBA', 'LA'):
            imagen = imagen.convert('RGB')
        
        # Guardar la imagen en el directorio de uploads
        imagen_path = os.path.join(Config.UPLOAD_FOLDER, f'alumno_{alumno_id}.jpg')
        imagen.save(imagen_path, 'JPEG')

        # Guardar los datos faciales en la base de datos
        guardar_datos_faciales(alumno_id, datos_rostro)
        return {"mensaje": "Datos faciales registrados correctamente"}

    except Exception as e:
        print(f"Error en capturar_foto: {str(e)}")
        return {"mensaje": f"Error al procesar la imagen: {str(e)}"}, 400

def procesar_imagen(imagen):
    """Procesar imagen y extraer datos faciales"""
    try:
        encodings = face_recognition.face_encodings(imagen)
        return pickle.dumps(encodings[0]) if encodings else None
    except Exception:
        return None

def guardar_datos_faciales(alumno_id, datos_rostro):
    """Guardar datos faciales en MySQL"""
    with get_db() as conexion:
        cursor = conexion.cursor()
        try:
            # Actualizar los datos faciales del alumno
            cursor.execute("UPDATE alumno SET datos_rostro = %s WHERE id = %s", (datos_rostro, alumno_id))
            
            # Insertar o actualizar registro en tabla registro_facial
            cursor.execute("""
                INSERT INTO registro_facial (alumno_id, estado, intentos)
                VALUES (%s, 'registrado', 1)
                ON DUPLICATE KEY UPDATE 
                estado = 'registrado',
                fecha_registro = CURRENT_TIMESTAMP,
                intentos = intentos + 1,
                updated_at = CURRENT_TIMESTAMP
            """, (alumno_id,))
            
            conexion.commit()
        except Error as e:
            print(f"Error al guardar datos faciales: {e}")
            conexion.rollback()
            raise

# ---------- HISTORIAL ASISTENCIA ----------
@bp.route('/historial_asistencia/<int:clase_id>')
def historial_asistencia(clase_id):
    if 'usuario' not in session:
        return redirect(url_for('main.login'))

    try:
        with get_db() as conexion:
            cursor = conexion.cursor(dictionary=True)
            
            # Verificar acceso del profesor
            profesor_id = session.get('profesor_id')
            cursor.execute("""
                SELECT 1 FROM profesor_clase 
                WHERE profesor_id = %s AND clase_id = %s
            """, (profesor_id, clase_id))
            
            if not cursor.fetchone():
                flash('No tienes acceso a esta clase', 'error')
                return redirect(url_for('main.home'))

            # Obtener información de la clase
            cursor.execute("""
                SELECT c.nombre, s.codigo as seccion_codigo
                FROM clase c
                JOIN seccion s ON c.seccion_id = s.id
                WHERE c.id = %s
            """, (clase_id,))
            clase_info = cursor.fetchone()
            
            if not clase_info:
                flash('Clase no encontrada', 'error')
                return redirect(url_for('main.home'))
                
            nombre_clase = f"{clase_info['nombre']} - {clase_info['seccion_codigo']}"

            # Obtener registros de asistencia agrupados por fecha
            cursor.execute("""
                SELECT 
                    a.fecha_asistencia as fecha,
                    COUNT(*) as total_alumnos,
                    SUM(a.presente) as asistentes,
                    ROUND((SUM(a.presente) * 100.0 / COUNT(*)), 1) as porcentaje
                FROM asistencia a
                WHERE a.clase_id = %s
                GROUP BY a.fecha_asistencia
                ORDER BY a.fecha_asistencia DESC
            """, (clase_id,))
            
            registros = cursor.fetchall()
            
            # Obtener detalles de cada fecha para el modal
            detalles_por_fecha = {}
            for registro in registros:
                fecha = registro['fecha']
                cursor.execute("""
                    SELECT 
                        a.nombre,
                        a.apellido_paterno,
                        a.apellido_materno,
                        a.rut,
                        ast.presente,
                        ast.timestamp
                    FROM asistencia ast
                    JOIN alumno a ON ast.alumno_id = a.id
                    WHERE ast.clase_id = %s AND ast.fecha_asistencia = %s
                    ORDER BY a.apellido_paterno, a.apellido_materno, a.nombre
                """, (clase_id, fecha))
                
                alumnos_fecha = cursor.fetchall()
                detalles_por_fecha[str(fecha)] = alumnos_fecha

            return render_template('historial_asistencia.html',
                                 registros=registros,
                                 detalles_por_fecha=detalles_por_fecha,
                                 clase_id=clase_id,
                                 nombre_clase=nombre_clase)
    
    except Error as e:
        print(f"Error en historial_asistencia: {e}")
        flash('Error cargando el historial', 'error')
        return redirect(url_for('main.home'))

# ---------- DETALLE ASISTENCIA ----------
@bp.route('/detalle_asistencia/<int:clase_id>/<fecha>')
def detalle_asistencia(clase_id, fecha):
    if 'usuario' not in session:
        return {"error": "No autorizado"}, 401

    try:
        with get_db() as conexion:
            cursor = conexion.cursor(dictionary=True)
            
            # Verificar acceso del profesor
            profesor_id = session.get('profesor_id')
            cursor.execute("""
                SELECT 1 FROM profesor_clase 
                WHERE profesor_id = %s AND clase_id = %s
            """, (profesor_id, clase_id))
            
            if not cursor.fetchone():
                return {"error": "No tienes acceso a esta clase"}, 403

            cursor.execute("""
                SELECT 
                    a.nombre,
                    a.apellido_paterno,
                    a.apellido_materno,
                    a.rut,
                    ast.presente,
                    TIME(ast.timestamp) as hora
                FROM asistencia ast
                JOIN alumno a ON ast.alumno_id = a.id
                WHERE ast.clase_id = %s AND ast.fecha_asistencia = %s
                ORDER BY a.apellido_paterno, a.apellido_materno, a.nombre
            """, (clase_id, fecha))
            
            alumnos = cursor.fetchall()
            
            return {
                "fecha": fecha,
                "alumnos": [
                    {
                        "nombre": f"{a['nombre']} {a['apellido_paterno']} {a['apellido_materno'] or ''}".strip(),
                        "rut": a['rut'],
                        "presente": bool(a['presente']),
                        "hora": str(a['hora']) if a['hora'] else None
                    }
                    for a in alumnos
                ]
            }
    
    except Error as e:
        print(f"Error en detalle_asistencia: {e}")
        return {"error": str(e)}, 500

# ---------- LISTAR ALUMNOS ----------
@bp.route('/listar_alumnos/<int:clase_id>', methods=['GET'])
def listar_alumnos(clase_id):
    if 'usuario' not in session:
        return {"error": "No autorizado"}, 401

    try:
        with get_db() as conexion:
            cursor = conexion.cursor(dictionary=True)
            
            # Verificar acceso del profesor
            profesor_id = session.get('profesor_id')
            cursor.execute("""
                SELECT 1 FROM profesor_clase 
                WHERE profesor_id = %s AND clase_id = %s
            """, (profesor_id, clase_id))
            
            if not cursor.fetchone():
                return {"error": "No tienes acceso a esta clase"}, 403

            cursor.execute("""
                SELECT 
                    a.id,
                    a.nombre,
                    a.apellido_paterno,
                    a.apellido_materno,
                    a.rut,
                    CASE WHEN a.datos_rostro IS NOT NULL THEN 1 ELSE 0 END as tiene_datos_faciales
                FROM alumno a
                JOIN alumno_clase ac ON a.id = ac.alumno_id
                WHERE ac.clase_id = %s AND ac.estado = 'inscrito'
                ORDER BY a.apellido_paterno, a.apellido_materno, a.nombre
            """, (clase_id,))
            
            alumnos = cursor.fetchall()
            
            return {
                "alumnos": [
                    {
                        "id": a['id'],
                        "nombre": f"{a['nombre']} {a['apellido_paterno']} {a['apellido_materno'] or ''}".strip(),
                        "rut": a['rut'],
                        "tiene_datos_faciales": bool(a['tiene_datos_faciales'])
                    }
                    for a in alumnos
                ]
            }
    
    except Error as e:
        print(f"Error en listar_alumnos: {e}")
        return {"error": str(e)}, 500

# ---------- DASHBOARD Y REPORTES ----------
@bp.route('/dashboard')
@professor_required
def dashboard():
    """Dashboard principal con estadísticas"""
    usuario_id = get_current_user_id()
    
    # Obtener contexto de roles
    role_context = get_user_role_context(usuario_id)
    
    # Si es profesor, filtrar por sus clases. Si es coordinador/admin, ver todo
    profesor_filter = usuario_id if role_context['is_professor'] and not (role_context['is_coordinator'] or role_context['is_admin']) else None
    
    # Obtener estadísticas
    stats = ReportManager.get_dashboard_stats(profesor_filter)
    
    # Obtener alertas de baja asistencia
    alerts = ReportManager.get_low_attendance_alerts()
    
    return render_template('dashboard.html', 
                         stats=stats, 
                         alerts=alerts[:5],  # Solo primeras 5
                         role_context=role_context,
                         nombre_profesor=session.get('nombre_profesor'))

@bp.route('/reportes')
@professor_required
def reportes():
    """Página principal de reportes"""
    usuario_id = get_current_user_id()
    role_context = get_user_role_context(usuario_id)
    
    return render_template('reportes.html', 
                         role_context=role_context,
                         nombre_profesor=session.get('nombre_profesor'))

@bp.route('/reporte/asistencia-por-clase')
@professor_required
def reporte_asistencia_clase():
    """Reporte de asistencia por clase"""
    usuario_id = get_current_user_id()
    role_context = get_user_role_context(usuario_id)
    
    # Obtener parámetros de filtro
    fecha_inicio = request.args.get('fecha_inicio')
    fecha_fin = request.args.get('fecha_fin')
    
    # Si es profesor, filtrar por sus clases
    profesor_filter = usuario_id if role_context['is_professor'] and not (role_context['is_coordinator'] or role_context['is_admin']) else None
    
    # Obtener datos del reporte
    reporte_data = ReportManager.get_attendance_by_class(profesor_filter, fecha_inicio, fecha_fin)
    
    return render_template('reporte_asistencia_clase.html',
                         reporte_data=reporte_data,
                         fecha_inicio=fecha_inicio,
                         fecha_fin=fecha_fin,
                         role_context=role_context,
                         nombre_profesor=session.get('nombre_profesor'))

@bp.route('/reporte/estudiantes')
@professor_required
def reporte_estudiantes():
    """Reporte resumen de estudiantes"""
    usuario_id = get_current_user_id()
    role_context = get_user_role_context(usuario_id)
    
    # Obtener parámetros
    clase_id = request.args.get('clase_id', type=int)
    
    # Si es profesor, filtrar por sus clases
    profesor_filter = usuario_id if role_context['is_professor'] and not (role_context['is_coordinator'] or role_context['is_admin']) else None
    
    # Obtener datos del reporte
    estudiantes_data = ReportManager.get_student_attendance_summary(profesor_filter, clase_id)
    
    # Obtener lista de clases para el filtro
    try:
        with db.get_connection() as conexion:
            cursor = conexion.cursor(dictionary=True)
            if profesor_filter:
                cursor.execute("""
                    SELECT c.id, c.nombre, s.codigo as seccion
                    FROM clase c
                    JOIN profesor_clase pc ON c.id = pc.clase_id
                    JOIN seccion s ON c.seccion_id = s.id
                    JOIN periodo_academico pa ON c.periodo_academico_id = pa.id
                    WHERE pc.profesor_id = %s AND pa.estado = 'activo'
                    ORDER BY c.nombre, s.codigo
                """, (profesor_filter,))
            else:
                cursor.execute("""
                    SELECT c.id, c.nombre, s.codigo as seccion
                    FROM clase c
                    JOIN seccion s ON c.seccion_id = s.id
                    JOIN periodo_academico pa ON c.periodo_academico_id = pa.id
                    WHERE pa.estado = 'activo'
                    ORDER BY c.nombre, s.codigo
                """)
            clases_disponibles = cursor.fetchall()
    except Exception as e:
        print(f"Error obteniendo clases: {e}")
        clases_disponibles = []
    
    return render_template('reporte_estudiantes.html',
                         estudiantes_data=estudiantes_data,
                         clases_disponibles=clases_disponibles,
                         clase_id=clase_id,
                         role_context=role_context,
                         nombre_profesor=session.get('nombre_profesor'))

@bp.route('/export/asistencia-clase')
@professor_required
def export_asistencia_clase():
    """Exportar reporte de asistencia por clase a Excel"""
    usuario_id = get_current_user_id()
    role_context = get_user_role_context(usuario_id)
    
    # Obtener parámetros
    fecha_inicio = request.args.get('fecha_inicio')
    fecha_fin = request.args.get('fecha_fin')
    
    # Si es profesor, filtrar por sus clases
    profesor_filter = usuario_id if role_context['is_professor'] and not (role_context['is_coordinator'] or role_context['is_admin']) else None
    
    # Obtener datos
    data = ReportManager.get_attendance_by_class(profesor_filter, fecha_inicio, fecha_fin)
    
    if not data:
        flash('No hay datos para exportar', 'warning')
        return redirect(url_for('main.reporte_asistencia_clase'))
    
    # Preparar datos para Excel
    excel_data = []
    for row in data:
        excel_data.append([
            row['clase_nombre'],
            row['fecha'].strftime('%d/%m/%Y'),
            timedelta_to_time_string(row['hora_inicio']),
            timedelta_to_time_string(row['hora_fin']),
            row['seccion'],
            row['total_inscritos'],
            row['total_presentes'],
            row['total_registros'],
            f"{row['porcentaje_asistencia']}%"
        ])
    
    columns = [
        'Clase', 'Fecha', 'Hora Inicio', 'Hora Fin', 'Sección',
        'Total Inscritos', 'Total Presentes', 'Total Registros', 'Porcentaje Asistencia'
    ]
    
    # Exportar a Excel
    excel_file = ReportManager.export_to_excel(excel_data, columns)
    
    if excel_file:
        filename = f"reporte_asistencia_clases_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        return send_file(
            excel_file,
            as_attachment=True,
            download_name=filename,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
    else:
        flash('Error generando el archivo Excel', 'error')
        return redirect(url_for('main.reporte_asistencia_clase'))

@bp.route('/export/estudiantes')
@professor_required
def export_estudiantes():
    """Exportar reporte de estudiantes a Excel"""
    usuario_id = get_current_user_id()
    role_context = get_user_role_context(usuario_id)
    
    # Obtener parámetros
    clase_id = request.args.get('clase_id', type=int)
    
    # Si es profesor, filtrar por sus clases
    profesor_filter = usuario_id if role_context['is_professor'] and not (role_context['is_coordinator'] or role_context['is_admin']) else None
    
    # Obtener datos
    data = ReportManager.get_student_attendance_summary(profesor_filter, clase_id)
    
    if not data:
        flash('No hay datos para exportar', 'warning')
        return redirect(url_for('main.reporte_estudiantes'))
    
    # Preparar datos para Excel
    excel_data = []
    for row in data:
        excel_data.append([
            row['rut'],
            row['nombre_completo'],
            row['carrera'],
            row['total_clases'],
            row['clases_asistidas'],
            row['clases_ausente'],
            f"{row['porcentaje_asistencia']}%"
        ])
    
    columns = [
        'RUT', 'Nombre Completo', 'Carrera', 'Total Clases',
        'Clases Asistidas', 'Clases Ausente', 'Porcentaje Asistencia'
    ]
    
    # Exportar a Excel
    excel_file = ReportManager.export_to_excel(excel_data, columns)
    
    if excel_file:
        filename = f"reporte_estudiantes_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        return send_file(
            excel_file,
            as_attachment=True,
            download_name=filename,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
    else:
        flash('Error generando el archivo Excel', 'error')
        return redirect(url_for('main.reporte_estudiantes'))

@bp.route('/api/dashboard-stats')
@professor_required
def api_dashboard_stats():
    """API para obtener estadísticas del dashboard (para gráficos)"""
    usuario_id = get_current_user_id()
    role_context = get_user_role_context(usuario_id)
    
    # Si es profesor, filtrar por sus clases
    profesor_filter = usuario_id if role_context['is_professor'] and not (role_context['is_coordinator'] or role_context['is_admin']) else None
    
    stats = ReportManager.get_dashboard_stats(profesor_filter)
    return jsonify(stats)



