# Importación opcional de face_recognition
try:
    import face_recognition
    FACE_RECOGNITION_AVAILABLE = True
except ImportError:
    FACE_RECOGNITION_AVAILABLE = False
    print("⚠️ face_recognition no está disponible. Funcionalidad de reconocimiento facial deshabilitada.")

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
from .roles import RoleManager, professor_required, coordinator_required, get_user_role_context, admin_required
from .reports import ReportManager
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash
from flask_login import current_user
from .facial_recognition import facial_recognition
from .models import db, Profesor, Alumno, Clase, Asistencia

# Crear Blueprint para las rutas
bp = Blueprint('main', __name__, url_prefix='')

UPLOAD_FOLDER = 'app/static/uploads/justificaciones'
ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg'}

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

def serialize_safe(obj):
    """Convertir objetos no serializables a JSON de manera segura"""
    if isinstance(obj, timedelta):
        return timedelta_to_time_string(obj)
    elif isinstance(obj, (date, datetime)):
        return obj.isoformat()
    elif hasattr(obj, '__dict__'):
        return obj.__dict__
    else:
        return str(obj)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@bp.context_processor
def inject_role_context():
    """Inyectar contexto de roles en los templates"""
    if not current_user.is_authenticated:
        return {
            'role_context': {
                'is_admin': False,
                'is_coordinator': False,
                'is_professor': False
            },
            'timedelta_to_time': timedelta_to_time_string,
            'serialize_safe': serialize_safe
        }
    
    return {
        'role_context': {
            'is_admin': current_user.is_admin,
            'is_coordinator': current_user.is_coordinator,
            'is_professor': True
        },
        'timedelta_to_time': timedelta_to_time_string,
        'serialize_safe': serialize_safe
    }

# ---------- RUTAS PÚBLICAS ----------
@bp.route('/inicio')
def inicio_publico():
    """Página de inicio pública"""
    return render_template('inicio_publico.html')

# ---------- LOGIN MEJORADO ----------
@bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        print(f"DEBUG Login - Intento de inicio de sesión para usuario: {username}")
        
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
                    WHERE p.usuario = %s AND p.estado = 'activo'
                """, (username,))
                usuario_data = cursor.fetchone()

                print(f"DEBUG Login - Datos del usuario encontrado: {usuario_data}")

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
                    session.clear()  # Limpiar sesión anterior
                    session['usuario'] = usuario_data['usuario']
                    session['profesor_id'] = usuario_data['profesor_id']
                    session['nombre_profesor'] = f"{usuario_data['nombre']} {usuario_data['apellido_paterno']}"
                    session['es_admin'] = usuario_data['tipo_usuario'] == 'admin'
                    session['login_time'] = datetime.now().isoformat()
                    session['last_activity'] = datetime.now().isoformat()
                    session.permanent = True
                    
                    print(f"DEBUG Login - Sesión creada: {dict(session)}")
                    print(f"DEBUG Login - Tipo usuario: {usuario_data['tipo_usuario']}")
                    print(f"DEBUG Login - Es admin: {session['es_admin']}")
                    
                    # Actualizar último login
                    try:
                        with get_db() as conexion:
                            cursor = conexion.cursor()
                            cursor.execute("""
                                UPDATE autenticacion 
                                SET ultimo_login = CURRENT_TIMESTAMP 
                                WHERE id = %s
                            """, (usuario_data['id'],))
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

# ---------- HOME MEJORADO ----------
@bp.route('/')
def home():
    if 'usuario' not in session:
        return redirect(url_for('main.inicio_publico'))
        
    try:
        profesor_id = get_current_user_id()
        nombre_profesor = session.get('nombre_profesor')
        
        if not profesor_id:
            return redirect(url_for('main.logout'))

        # Obtener contexto de roles
        role_context = get_user_role_context(profesor_id)

        with get_db() as conexion:
            cursor = conexion.cursor(dictionary=True)
            cursor.execute("""
                SELECT 
                    c.id, c.nombre, c.fecha, c.hora_inicio, c.hora_fin, c.sala,
                    s.codigo as seccion_codigo, 
                    pa.año, pa.semestre,
                    COUNT(DISTINCT ac.alumno_id) as total_alumnos,
                    COUNT(DISTINCT CASE WHEN a.presente = 1 THEN a.alumno_id END) as alumnos_presentes
                FROM clase c
                JOIN seccion s ON c.seccion_id = s.id
                JOIN periodo_academico pa ON c.periodo_academico_id = pa.id
                LEFT JOIN alumno_clase ac ON c.id = ac.clase_id AND ac.estado = 'inscrito'
                LEFT JOIN asistencia a ON c.id = a.clase_id AND a.alumno_id = ac.alumno_id
                WHERE c.profesor_id = %s AND c.estado = 'activa'
                GROUP BY c.id, c.nombre, c.fecha, c.hora_inicio, c.hora_fin, c.sala, s.codigo, pa.año, pa.semestre
                ORDER BY c.fecha DESC, c.hora_inicio DESC
            """, (profesor_id,))
            clases = cursor.fetchall()

        return render_template('index.html', 
                        nombre_profesor=nombre_profesor, 
                        clases=clases,
                        role_context=role_context)

    except Error as e:
        print(f"Error en home: {e}")
        flash('Error cargando las clases', 'error')
        return redirect(url_for('main.logout'))

# ---------- VER CLASES MEJORADO ----------
@bp.route('/clases')
@require_login
def ver_clases():
    try:
        profesor_id = get_current_user_id()
        nombre_profesor = session.get('nombre_profesor')
        
        if not profesor_id:
            flash('Sesión no válida', 'error')
            return redirect(url_for('main.login'))

        # Actualizar timestamp de última actividad
        session['last_activity'] = datetime.now().isoformat()

        # Obtener contexto de roles
        role_context = get_user_role_context(profesor_id)

        with get_db() as conexion:
            cursor = conexion.cursor(dictionary=True)
            cursor.execute("""
                SELECT 
                    c.id, c.nombre, c.fecha, c.hora_inicio, c.hora_fin, c.sala,
                    s.codigo as seccion_codigo, 
                    pa.año, pa.semestre,
                    COUNT(DISTINCT ac.alumno_id) as total_alumnos,
                    COUNT(DISTINCT CASE WHEN a.presente = 1 THEN a.alumno_id END) as alumnos_presentes
                FROM clase c
                JOIN seccion s ON c.seccion_id = s.id
                JOIN periodo_academico pa ON c.periodo_academico_id = pa.id
                LEFT JOIN alumno_clase ac ON c.id = ac.clase_id AND ac.estado = 'inscrito'
                LEFT JOIN asistencia a ON c.id = a.clase_id
                WHERE c.profesor_id = %s AND c.estado = 'activa'
                GROUP BY c.id, c.nombre, c.fecha, c.hora_inicio, c.hora_fin, c.sala, s.codigo, pa.año, pa.semestre
                ORDER BY c.fecha DESC, c.hora_inicio DESC
            """, (profesor_id,))
            clases = cursor.fetchall()

        return render_template('clases.html', 
                            nombre_profesor=nombre_profesor, 
                            clases=clases,
                            role_context=role_context)
    
    except Error as e:
        print(f"Error en ver_clases: {e}")
        flash('Error cargando las clases', 'error')
        return redirect(url_for('main.home'))

# ---------- ASISTENCIA MEJORADA ----------
@bp.route('/asistencia/<int:clase_id>')
@require_login
def asistencia(clase_id):
    try:
        profesor_id = get_current_user_id()
        if not profesor_id:
            flash('Sesión no válida', 'error')
            return redirect(url_for('main.login'))

        # Actualizar timestamp de última actividad
        session['last_activity'] = datetime.now().isoformat()

        # Obtener contexto de roles
        role_context = get_user_role_context(profesor_id)

        with get_db() as conexion:
            cursor = conexion.cursor(dictionary=True)
            
            # Verificar que el profesor tenga acceso a esta clase
            cursor.execute("""
                SELECT 1
                FROM clase c
                WHERE c.id = %s AND c.profesor_id = %s
            """, (clase_id, profesor_id))
            
            if not cursor.fetchone():
                flash('No tienes acceso a esta clase', 'error')
                return redirect(url_for('main.home'))
            
            # Obtener lista de alumnos y su asistencia
            cursor.execute("""
                SELECT 
                    a.id as alumno_id,
                    a.nombre,
                    a.apellido_paterno,
                    a.apellido_materno,
                    a.rut,
                    COALESCE(ast.presente, 0) as presente,
                    ast.id as asistencia_id,
                    ast.fecha_asistencia,
                    ast.timestamp as hora_registro
                FROM alumno a
                JOIN alumno_clase ac ON a.id = ac.alumno_id
                LEFT JOIN asistencia ast ON a.id = ast.alumno_id AND ast.clase_id = %s
                WHERE ac.clase_id = %s AND ac.estado = 'inscrito'
                ORDER BY a.apellido_paterno, a.apellido_materno, a.nombre
            """, (clase_id, clase_id))
            
            alumnos = cursor.fetchall()
            
            # Obtener todas las clases disponibles para el select
            cursor.execute("""
                SELECT c.id, c.nombre
                FROM clase c
                WHERE c.profesor_id = %s AND c.estado = 'activa'
                ORDER BY c.fecha DESC
            """, (profesor_id,))
            clases_disponibles = cursor.fetchall()

        return render_template('asistencia.html', 
                             alumnos=alumnos, 
                             clase_id=clase_id, 
                             clases=clases_disponibles,
                             role_context=role_context,
                             nombre_profesor=session.get('nombre_profesor'))
    
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

    if not FACE_RECOGNITION_AVAILABLE:
        return {"mensaje": "Reconocimiento facial no disponible"}, 503

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
                        if not FACE_RECOGNITION_AVAILABLE:
                            mensaje = "Reconocimiento facial no disponible."
                            continue
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

    if not FACE_RECOGNITION_AVAILABLE:
        return {"mensaje": "Reconocimiento facial no disponible"}, 503

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
    if not FACE_RECOGNITION_AVAILABLE:
        return None
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
@require_login
def historial_asistencia(clase_id):
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
                SELECT 
                    c.nombre,
                    s.codigo as seccion,
                    CONCAT(TIME_FORMAT(c.hora_inicio, '%H:%i'), ' - ', TIME_FORMAT(c.hora_fin, '%H:%i')) as horario,
                    (SELECT COUNT(DISTINCT fecha_asistencia) FROM asistencia WHERE clase_id = c.id) as total_clases,
                    (SELECT COUNT(*) FROM alumno_clase WHERE clase_id = c.id AND estado = 'inscrito') as total_estudiantes,
                    (
                        SELECT ROUND(AVG(presente) * 100, 1)
                        FROM asistencia
                        WHERE clase_id = c.id
                    ) as promedio_asistencia
                FROM clase c
                JOIN seccion s ON c.seccion_id = s.id
                WHERE c.id = %s
            """, (clase_id,))
            clase_info = cursor.fetchone()
            
            if not clase_info:
                flash('Clase no encontrada', 'error')
                return redirect(url_for('main.home'))

            # Obtener lista de estudiantes con sus estadísticas
            cursor.execute("""
                SELECT 
                    a.id,
                    a.nombre,
                    a.apellido_paterno,
                    a.apellido_materno,
                    a.rut,
                    COUNT(ast.id) as clases_asistidas,
                    (
                        SELECT COUNT(DISTINCT fecha_asistencia) 
                        FROM asistencia 
                        WHERE clase_id = %s
                    ) as total_clases,
                    CASE 
                        WHEN COUNT(ast.id) > 0 THEN 
                            ROUND((COUNT(CASE WHEN ast.presente = 1 THEN 1 END) * 100.0 / COUNT(ast.id)), 1)
                        ELSE NULL
                    END as porcentaje_asistencia,
                    MAX(ast.fecha_asistencia) as ultima_asistencia
                FROM alumno a
                JOIN alumno_clase ac ON a.id = ac.alumno_id
                LEFT JOIN asistencia ast ON a.id = ast.alumno_id AND ast.clase_id = %s
                WHERE ac.clase_id = %s AND ac.estado = 'inscrito'
                GROUP BY a.id, a.nombre, a.apellido_paterno, a.apellido_materno, a.rut
                ORDER BY a.apellido_paterno, a.apellido_materno, a.nombre
            """, (clase_id, clase_id, clase_id))
            
            estudiantes = cursor.fetchall()
            
            # Procesar los datos de los estudiantes
            for estudiante in estudiantes:
                estudiante['nombre'] = f"{estudiante['nombre']} {estudiante['apellido_paterno']} {estudiante['apellido_materno']}".strip()
                if estudiante['ultima_asistencia']:
                    estudiante['ultima_asistencia'] = estudiante['ultima_asistencia'].strftime('%d/%m/%Y')

            return render_template('historial_asistencia.html',
                                 clase=clase_info,
                                 estudiantes=estudiantes,
                                 stats={
                                     'total_clases': clase_info['total_clases'] or 0,
                                     'total_estudiantes': clase_info['total_estudiantes'] or 0,
                                     'promedio_asistencia': clase_info['promedio_asistencia'] or 0
                                 })
    
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

# ---------- RUTAS ADMINISTRATIVAS ----------
@bp.route('/admin')
def admin():
    """Panel principal de administración"""
    print("DEBUG: Intentando acceder al panel de administración")
    print(f"DEBUG: Session actual: {dict(session)}")
    
    if 'usuario' not in session:
        print("DEBUG: No hay usuario en la sesión")
        flash('Por favor inicie sesión', 'warning')
        return redirect(url_for('main.login'))
    
    print(f"DEBUG: Usuario en sesión: {session.get('usuario')}")
    print(f"DEBUG: Es admin?: {session.get('es_admin')}")
    
    try:
        with get_db() as conexion:
            cursor = conexion.cursor(dictionary=True)
            
            # Verificar si el usuario es realmente admin
            cursor.execute("""
                SELECT a.tipo_usuario, p.nombre
                FROM autenticacion a
                JOIN profesor p ON a.profesor_id = p.id
                WHERE p.id = %s
            """, (session.get('profesor_id'),))
            
            user_data = cursor.fetchone()
            print(f"DEBUG: Datos del usuario desde DB: {user_data}")
            
            if user_data and user_data['tipo_usuario'] == 'admin':
                # Estadísticas generales
                cursor.execute("""
                    SELECT 
                        (SELECT COUNT(*) FROM profesor) as total_profesores,
                        (SELECT COUNT(*) FROM alumno) as total_alumnos,
                        (SELECT COUNT(*) FROM clase) as total_clases,
                        (SELECT COUNT(*) FROM asistencia) as total_registros
                """)
                stats = cursor.fetchone()
                
                # Actividad reciente - Solo clases y profesores
                cursor.execute("""
                    SELECT 
                        c.fecha, 
                        c.nombre as clase_nombre, 
                        s.codigo as seccion_codigo,
                        p.nombre as profesor_nombre, 
                        p.apellido_paterno as profesor_apellido,
                        (SELECT COUNT(*) FROM alumno_clase ac WHERE ac.clase_id = c.id AND ac.estado = 'inscrito') as total_alumnos,
                        (SELECT COUNT(*) FROM asistencia a WHERE a.clase_id = c.id AND a.presente = 1) as alumnos_presentes
                    FROM clase c
                    JOIN seccion s ON c.seccion_id = s.id
                    JOIN profesor p ON c.profesor_id = p.id
                    WHERE c.estado = 'activa'
                    ORDER BY c.fecha DESC, c.hora_inicio DESC
                    LIMIT 5
                """)
                actividad_reciente = cursor.fetchall()
                
                return render_template('admin/dashboard.html',
                                     stats=stats,
                                     actividad_reciente=actividad_reciente)
            else:
                flash('No tienes permisos de administrador', 'error')
                return redirect(url_for('main.home'))
    
    except Exception as e:
        print(f"ERROR: Error en el panel admin: {str(e)}")
        flash(f'Error cargando el dashboard: {str(e)}', 'error')
        return redirect(url_for('main.home'))

@bp.route('/admin/clases', methods=['GET', 'POST'])
@admin_required
def admin_clases():
    """Gestión de clases"""
    try:
        with get_db() as conexion:
            cursor = conexion.cursor(dictionary=True)
            
            if request.method == 'POST':
                accion = request.form.get('accion')
                
                if accion == 'crear':
                    # Crear nueva clase
                    cursor.execute("""
                        INSERT INTO clase (nombre, seccion_id, periodo_academico_id, profesor_id, 
                                        sala, fecha, hora_inicio, hora_fin)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        request.form['nombre'],
                        request.form['seccion_id'],
                        request.form['periodo_id'],
                        request.form.get('profesor_id'),
                        request.form['sala'],
                        request.form['fecha'],
                        request.form['hora_inicio'],
                        request.form['hora_fin']
                    ))
                    conexion.commit()
                    flash('Clase creada exitosamente', 'success')
                
                elif accion == 'editar':
                    # Editar clase existente
                    cursor.execute("""
                        UPDATE clase 
                        SET nombre = %s, seccion_id = %s, periodo_academico_id = %s,
                            profesor_id = %s, sala = %s, fecha = %s,
                            hora_inicio = %s, hora_fin = %s
                        WHERE id = %s
                    """, (
                        request.form['nombre'],
                        request.form['seccion_id'],
                        request.form['periodo_id'],
                        request.form.get('profesor_id'),
                        request.form['sala'],
                        request.form['fecha'],
                        request.form['hora_inicio'],
                        request.form['hora_fin'],
                        request.form['clase_id']
                    ))
                    conexion.commit()
                    flash('Clase actualizada exitosamente', 'success')
                
                elif accion == 'eliminar':
                    # Eliminar clase
                    cursor.execute("DELETE FROM clase WHERE id = %s", (request.form['clase_id'],))
                    conexion.commit()
                    flash('Clase eliminada exitosamente', 'success')
            
            # Obtener lista de clases
            cursor.execute("""
                SELECT c.*, s.codigo as seccion_codigo,
                       p.nombre as profesor_nombre, p.apellido_paterno as profesor_apellido,
                       pa.año, pa.semestre,
                       COUNT(DISTINCT ac.alumno_id) as total_alumnos
                FROM clase c
                JOIN seccion s ON c.seccion_id = s.id
                LEFT JOIN profesor p ON c.profesor_id = p.id
                JOIN periodo_academico pa ON c.periodo_academico_id = pa.id
                LEFT JOIN alumno_clase ac ON c.id = ac.clase_id
                GROUP BY c.id
                ORDER BY c.fecha DESC, c.hora_inicio
            """)
            clases = cursor.fetchall()
            
            # Obtener secciones y periodos para los formularios
            cursor.execute("SELECT * FROM seccion ORDER BY codigo")
            secciones = cursor.fetchall()
            
            cursor.execute("SELECT * FROM periodo_academico ORDER BY año DESC, semestre DESC")
            periodos = cursor.fetchall()
            
            cursor.execute("SELECT id, nombre, apellido_paterno FROM profesor ORDER BY apellido_paterno, nombre")
            profesores = cursor.fetchall()
            
            return render_template('admin/clases.html',
                                 clases=clases,
                                 secciones=secciones,
                                 periodos=periodos,
                                 profesores=profesores)
    
    except Exception as e:
        flash(f'Error en la gestión de clases: {str(e)}', 'error')
        return redirect(url_for('main.admin'))

@bp.route('/admin/alumnos', methods=['GET', 'POST'])
@admin_required
def admin_alumnos():
    """Gestión de alumnos"""
    try:
        with get_db() as conexion:
            cursor = conexion.cursor(dictionary=True)
            
            if request.method == 'POST':
                accion = request.form.get('accion')
                
                if accion == 'crear':
                    # Crear nuevo alumno
                    cursor.execute("""
                        INSERT INTO alumno (nombre, apellido_paterno, apellido_materno, rut, email)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (
                        request.form['nombre'],
                        request.form['apellido_paterno'],
                        request.form['apellido_materno'],
                        request.form['rut'],
                        request.form['email']
                    ))
                    conexion.commit()
                    flash('Alumno creado exitosamente', 'success')
                
                elif accion == 'editar':
                    # Editar alumno existente
                    cursor.execute("""
                        UPDATE alumno 
                        SET nombre = %s, apellido_paterno = %s, apellido_materno = %s,
                            rut = %s, email = %s
                        WHERE id = %s
                    """, (
                        request.form['nombre'],
                        request.form['apellido_paterno'],
                        request.form['apellido_materno'],
                        request.form['rut'],
                        request.form['email'],
                        request.form['alumno_id']
                    ))
                    conexion.commit()
                    flash('Alumno actualizado exitosamente', 'success')
                
                elif accion == 'eliminar':
                    # Eliminar alumno
                    cursor.execute("DELETE FROM alumno WHERE id = %s", (request.form['alumno_id'],))
                    conexion.commit()
                    flash('Alumno eliminado exitosamente', 'success')
            
            # Obtener lista de alumnos
            cursor.execute("""
                SELECT a.*, 
                       GROUP_CONCAT(DISTINCT CONCAT(c.nombre, ' (', s.codigo, ')') SEPARATOR ', ') as clases,
                       COUNT(DISTINCT ac.clase_id) as total_clases
                FROM alumno a
                LEFT JOIN alumno_clase ac ON a.id = ac.alumno_id
                LEFT JOIN clase c ON ac.clase_id = c.id
                LEFT JOIN seccion s ON c.seccion_id = s.id
                GROUP BY a.id
                ORDER BY a.apellido_paterno, a.nombre
            """)
            alumnos = cursor.fetchall()
            
            return render_template('admin/alumnos.html',
                                 alumnos=alumnos)
    
    except Exception as e:
        flash(f'Error en la gestión de alumnos: {str(e)}', 'error')
        return redirect(url_for('main.admin'))

@bp.route('/admin/profesores', methods=['GET', 'POST'])
@admin_required
def admin_profesores():
    """Gestión de profesores"""
    try:
        with get_db() as conexion:
            cursor = conexion.cursor(dictionary=True)
            
            if request.method == 'POST':
                accion = request.form.get('accion')
                
                if accion == 'crear':
                    # Crear nuevo profesor - primero el registro de profesor
                    cursor.execute("""
                        INSERT INTO profesor (rut, nombre, apellido_paterno, apellido_materno, 
                                           usuario, estado)
                        VALUES (%s, %s, %s, %s, %s, 'activo')
                    """, (
                        request.form['rut'],
                        request.form['nombre'],
                        request.form['apellido_paterno'],
                        request.form['apellido_materno'],
                        request.form['username']
                    ))
                    profesor_id = cursor.lastrowid
                    
                    # Crear credenciales de autenticación
                    cursor.execute("""
                        INSERT INTO autenticacion (usuario, password_hash, tipo_usuario, profesor_id)
                        VALUES (%s, %s, %s, %s)
                    """, (
                        request.form['username'],
                        generate_password_hash(request.form['password']),
                        request.form.get('tipo_usuario', 'profesor'),
                        profesor_id
                    ))
                    
                    # Asignar roles si se especifican
                    if 'roles' in request.form:
                        rol_ids = request.form.getlist('roles')
                        for rol_id in rol_ids:
                            cursor.execute("""
                                INSERT INTO usuario_roles (usuario_id, rol_id, assigned_by)
                                VALUES (%s, %s, %s)
                            """, (profesor_id, rol_id, session.get('profesor_id')))
                    
                    conexion.commit()
                    flash('Profesor creado exitosamente', 'success')
                
                elif accion == 'editar':
                    # Editar profesor existente
                    cursor.execute("""
                        UPDATE profesor 
                        SET nombre = %s, apellido_paterno = %s, apellido_materno = %s,
                            rut = %s, email = %s
                        WHERE id = %s
                    """, (
                        request.form['nombre'],
                        request.form['apellido_paterno'],
                        request.form['apellido_materno'],
                        request.form['rut'],
                        request.form['email'],
                        request.form['profesor_id']
                    ))
                    
                    # Actualizar roles si se proporcionaron
                    if 'roles' in request.form:
                        cursor.execute("SELECT usuario_id FROM profesor WHERE id = %s", 
                                     (request.form['profesor_id'],))
                        usuario_id = cursor.fetchone()['usuario_id']
                        
                        # Eliminar roles actuales
                        cursor.execute("DELETE FROM usuario_rol WHERE usuario_id = %s", (usuario_id,))
                        
                        # Asignar nuevos roles
                        rol_ids = request.form.getlist('roles')
                        for rol_id in rol_ids:
                            cursor.execute("""
                                INSERT INTO usuario_rol (usuario_id, rol_id)
                                VALUES (%s, %s)
                            """, (usuario_id, rol_id))
                    
                    conexion.commit()
                    flash('Profesor actualizado exitosamente', 'success')
                
                elif accion == 'eliminar':
                    # Eliminar profesor y autenticación asociada
                    profesor_id = request.form['profesor_id']
                    
                    # Eliminar autenticación
                    cursor.execute("DELETE FROM autenticacion WHERE profesor_id = %s", (profesor_id,))
                    # Eliminar roles asignados
                    cursor.execute("DELETE FROM usuario_roles WHERE usuario_id = %s", (profesor_id,))
                    # Eliminar profesor
                    cursor.execute("DELETE FROM profesor WHERE id = %s", (profesor_id,))
                    
                    conexion.commit()
                    flash('Profesor eliminado exitosamente', 'success')
            
            # Obtener lista de profesores con la estructura correcta
            cursor.execute("""
                SELECT p.*, a.usuario as username, a.tipo_usuario,
                       GROUP_CONCAT(DISTINCT r.nombre ORDER BY r.nombre SEPARATOR ',') as roles,
                       COUNT(DISTINCT c.id) as total_clases
                FROM profesor p
                LEFT JOIN autenticacion a ON p.id = a.profesor_id
                LEFT JOIN usuario_roles ur ON p.id = ur.usuario_id
                LEFT JOIN roles r ON ur.rol_id = r.id
                LEFT JOIN clase c ON p.id = c.profesor_id
                GROUP BY p.id
                ORDER BY p.apellido_paterno, p.nombre
            """)
            profesores = cursor.fetchall()
            
            # Obtener roles para el formulario
            cursor.execute("SELECT * FROM roles ORDER BY nombre")
            roles = cursor.fetchall()
            
            return render_template('admin/profesores.html',
                                 profesores=profesores,
                                 roles=roles)
    
    except Exception as e:
        flash(f'Error en la gestión de profesores: {str(e)}', 'error')
        return redirect(url_for('main.admin'))

@bp.route('/admin/asistencia', methods=['GET', 'POST'])
@admin_required
def admin_asistencia():
    """Gestión de asistencia"""
    try:
        with get_db() as conexion:
            cursor = conexion.cursor(dictionary=True)
            
            if request.method == 'POST':
                accion = request.form.get('accion')
                
                if accion == 'registrar':
                    # Registrar nueva asistencia - usando las columnas correctas de la tabla asistencia
                    cursor.execute("""
                        INSERT INTO asistencia (clase_id, alumno_id, fecha_asistencia, presente, timestamp)
                        VALUES (%s, %s, %s, %s, NOW())
                    """, (
                        request.form['clase_id'],
                        request.form['alumno_id'],
                        request.form['fecha'],
                        1  # presente por defecto
                    ))
                    asistencia_id = cursor.lastrowid
                    
                    # En este modelo simple, cada registro de asistencia ya tiene alumno_id
                    # No necesitamos tabla intermedia alumno_asistencia
                    
                    conexion.commit()
                    flash('Asistencia registrada exitosamente', 'success')
                
                elif accion == 'editar':
                    # Editar registro de asistencia
                    cursor.execute("""
                        UPDATE asistencia 
                        SET fecha_asistencia = %s, presente = %s
                        WHERE id = %s
                    """, (
                        request.form['fecha'],
                        1 if request.form.get('presente') == '1' else 0,
                        request.form['asistencia_id']
                    ))
                    
                    # Nota: El modelo de asistencia en esta base de datos es simple
                    # No necesitamos actualizar tabla alumno_asistencia porque
                    # asistencia ya tiene alumno_id directamente
                    
                    conexion.commit()
                    flash('Asistencia actualizada exitosamente', 'success')
                
                elif accion == 'eliminar':
                    # Eliminar registro de asistencia
                    cursor.execute("DELETE FROM asistencia WHERE id = %s", 
                                 (request.form['asistencia_id'],))
                    conexion.commit()
                    flash('Registro de asistencia eliminado exitosamente', 'success')
            
            # Aplicar filtros si existen
            where_clauses = []
            params = []
            
            if request.args.get('clase_id'):
                where_clauses.append("a.clase_id = %s")
                params.append(request.args.get('clase_id'))
            
            if request.args.get('profesor_id'):
                where_clauses.append("c.profesor_id = %s")
                params.append(request.args.get('profesor_id'))
            
            if request.args.get('fecha_desde'):
                where_clauses.append("a.fecha_asistencia >= %s")
                params.append(request.args.get('fecha_desde'))
            
            if request.args.get('fecha_hasta'):
                where_clauses.append("a.fecha_asistencia <= %s")
                params.append(request.args.get('fecha_hasta'))
            
            where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"
            
            # Obtener lista de asistencias con las columnas correctas
            cursor.execute(f"""
                SELECT a.*, c.nombre as clase_nombre, s.codigo as seccion_codigo,
                       p.nombre as profesor_nombre, p.apellido_paterno as profesor_apellido,
                       al.nombre as alumno_nombre, al.apellido_paterno as alumno_apellido,
                       a.presente,
                       CASE 
                           WHEN a.fecha_asistencia > CURDATE() THEN 'Pendiente'
                           WHEN a.fecha_asistencia = CURDATE() THEN 'En Curso'
                           ELSE 'Completada'
                       END as estado
                FROM asistencia a
                JOIN clase c ON a.clase_id = c.id
                JOIN seccion s ON c.seccion_id = s.id
                JOIN profesor p ON c.profesor_id = p.id
                JOIN alumno al ON a.alumno_id = al.id
                WHERE {where_sql}
                ORDER BY a.fecha_asistencia DESC, a.timestamp DESC
            """, params)
            asistencias = cursor.fetchall()
            
            # Obtener clases y profesores para los filtros
            cursor.execute("""
                SELECT c.id, c.nombre, s.codigo as seccion_codigo
                FROM clase c
                JOIN seccion s ON c.seccion_id = s.id
                ORDER BY c.fecha DESC
            """)
            clases = cursor.fetchall()
            
            cursor.execute("""
                SELECT id, nombre, apellido_paterno
                FROM profesor
                ORDER BY apellido_paterno, nombre
            """)
            profesores = cursor.fetchall()
            
            return render_template('admin/asistencia.html',
                                 asistencias=asistencias,
                                 clases=clases,
                                 profesores=profesores)
    
    except Exception as e:
        flash(f'Error en la gestión de asistencia: {str(e)}', 'error')
        return redirect(url_for('main.admin'))

@bp.route('/api/alumnos_clase/<int:clase_id>')
@admin_required
def api_alumnos_clase(clase_id):
    """API para obtener los alumnos de una clase"""
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

@bp.route('/reconocer_alumno', methods=['POST'])
@require_login
def reconocer_alumno():
    """
    Endpoint para reconocer un alumno mediante reconocimiento facial
    """
    if not request.is_json:
        return jsonify({'success': False, 'message': 'Se requiere JSON'}), 400

    data = request.get_json()
    image_data = data.get('image_data')
    clase_id = data.get('clase_id')

    if not image_data or not clase_id:
        return jsonify({'success': False, 'message': 'Faltan datos requeridos'}), 400

    try:
        # Intentar reconocer al alumno
        alumno_id = facial_recognition.recognize_face(image_data)
        
        if alumno_id:
            # Verificar si el alumno está en la clase
            alumno = Alumno.query.get(alumno_id)
            if alumno and alumno in get_alumnos_clase(clase_id):
                return jsonify({
                    'success': True,
                    'alumno_id': alumno_id,
                    'message': f'Alumno reconocido: {alumno.nombre} {alumno.apellido_paterno}'
                })
            else:
                return jsonify({
                    'success': False,
                    'message': 'Alumno no pertenece a esta clase'
                })
        else:
            return jsonify({
                'success': False,
                'message': 'No se reconoció ningún alumno'
            })

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error en el reconocimiento facial: {str(e)}'
        }), 500

@bp.route('/marcar_asistencia', methods=['POST'])
@require_login
def marcar_asistencia():
    """
    Endpoint para marcar la asistencia de un alumno
    """
    if not request.is_json:
        return jsonify({'success': False, 'message': 'Se requiere JSON'}), 400

    data = request.get_json()
    alumno_id = data.get('alumno_id')
    clase_id = data.get('clase_id')

    if not alumno_id or not clase_id:
        return jsonify({'success': False, 'message': 'Faltan datos requeridos'}), 400

    try:
        # Marcar asistencia
        asistencia = Asistencia.query.filter_by(
            alumno_id=alumno_id,
            clase_id=clase_id,
            fecha=datetime.now().date()
        ).first()

        if not asistencia:
            asistencia = Asistencia(
                alumno_id=alumno_id,
                clase_id=clase_id,
                fecha=datetime.now().date(),
                hora=datetime.now().time(),
                presente=True
            )
            db.session.add(asistencia)
        else:
            asistencia.presente = True
            asistencia.hora = datetime.now().time()

        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Asistencia registrada correctamente'
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Error al registrar asistencia: {str(e)}'
        }), 500

@bp.route('/registrar_imagen_alumno', methods=['POST'])
@require_login
def registrar_imagen_alumno():
    """
    Endpoint para registrar la imagen de referencia de un alumno
    """
    if not request.is_json:
        return jsonify({'success': False, 'message': 'Se requiere JSON'}), 400

    data = request.get_json()
    image_data = data.get('image_data')
    alumno_id = data.get('alumno_id')

    if not image_data or not alumno_id:
        return jsonify({'success': False, 'message': 'Faltan datos requeridos'}), 400

    try:
        # Verificar que el alumno existe
        alumno = Alumno.query.get_or_404(alumno_id)

        # Registrar la imagen en el sistema de reconocimiento facial
        success = facial_recognition.add_face(image_data, str(alumno_id))
        
        if success:
            return jsonify({
                'success': True,
                'message': 'Imagen registrada correctamente'
            })
        else:
            return jsonify({
                'success': False,
                'message': 'No se detectó una cara clara en la imagen'
            })

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error al registrar imagen: {str(e)}'
        }), 500

@bp.route('/registro_imagen/<int:alumno_id>')
@require_login
def registro_imagen(alumno_id):
    """
    Vista para registrar la imagen de un alumno
    """
    try:
        alumno = Alumno.query.get_or_404(alumno_id)
        return render_template('registro_imagen.html', alumno=alumno)
    except Exception as e:
        flash('Error al cargar la página de registro de imagen', 'error')
        return redirect(url_for('main.dashboard'))



