import face_recognition
import pickle
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
import sqlite3
from PIL import Image
import base64
import io
import os
import hashlib
import numpy as np
from .config import Config

# Crear Blueprint para las rutas
bp = Blueprint('main', __name__)

def get_db():
    """Función helper para obtener conexión a la base de datos"""
    return sqlite3.connect(Config.DATABASE_PATH)

# ---------- LOGIN ----------
@bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        # Convertimos la contraseña a hash
        password_hashed = hashlib.sha256(password.encode()).hexdigest()

        # Consultamos en la base de datos
        with get_db() as conexion:
            cursor = conexion.cursor()
            cursor.execute(
                "SELECT id, nombre FROM profesor WHERE usuario = ? AND password_hash = ?",
                (username, password_hashed)
            )
            profesor = cursor.fetchone()

        if profesor:
            session['usuario'] = username
            return redirect(url_for('main.home'))
        else:
            flash('Usuario o contraseña incorrectos', 'error')
            return render_template('login.html')

    return render_template('login.html')

@bp.route('/logout')
def logout():
    # Limpiar toda la sesión, incluyendo mensajes flash
    session.clear()
    return redirect(url_for('main.login'))

# ---------- VISTA PRINCIPAL ----------
@bp.route('/')
def home():
    if 'usuario' not in session:
        return render_template('inicio_publico.html')

    # Página para profesor autenticado
    usuario = session['usuario']
    with get_db() as conexion:
        cursor = conexion.cursor()
        cursor.execute("SELECT id, nombre FROM profesor WHERE usuario = ?", (usuario,))
        profesor = cursor.fetchone()
        
        if not profesor:
            return redirect(url_for('main.logout'))
            
        profesor_id, nombre_profesor = profesor

        cursor.execute("""
            SELECT clase.id, clase.nombre, clase.fecha
            FROM clase
            JOIN profesor_clase ON clase.id = profesor_clase.clase_id
            WHERE profesor_clase.profesor_id = ?
            ORDER BY clase.fecha DESC
        """, (profesor_id,))
        clases = cursor.fetchall()

    return render_template('index.html', nombre_profesor=nombre_profesor, clases=clases)

# ---------- VER CLASES ----------
@bp.route('/clases')
def ver_clases():
    if 'usuario' not in session:
        return redirect(url_for('main.login'))

    usuario = session['usuario']
    with get_db() as conexion:
        cursor = conexion.cursor()
        cursor.execute("SELECT id, nombre FROM profesor WHERE usuario = ?", (usuario,))
        profesor = cursor.fetchone()
        
        if not profesor:
            return redirect(url_for('main.logout'))

        profesor_id, nombre_profesor = profesor

        cursor.execute("""
            SELECT clase.id, clase.nombre, clase.fecha
            FROM clase
            JOIN profesor_clase ON clase.id = profesor_clase.clase_id
            WHERE profesor_clase.profesor_id = ?
            ORDER BY clase.fecha DESC
        """, (profesor_id,))
        clases = cursor.fetchall()

    return render_template('clases.html', nombre_profesor=nombre_profesor, clases=clases)

# ---------- ASISTENCIA ----------
@bp.route('/asistencia/<int:clase_id>')
def asistencia(clase_id):
    if 'usuario' not in session:
        return redirect(url_for('main.login'))

    with get_db() as conexion:
        cursor = conexion.cursor()
        cursor.execute("""
            SELECT alumno.id, alumno.nombre, alumno.rut
            FROM alumno
            JOIN alumno_clase ON alumno.id = alumno_clase.alumno_id
            WHERE alumno_clase.clase_id = ?
        """, (clase_id,))
        alumnos = [{"id": a[0], "nombre": a[1], "rut": a[2]} for a in cursor.fetchall()]
        
        cursor.execute("SELECT id, nombre FROM clase ORDER BY fecha DESC")
        clases_disponibles = cursor.fetchall()

    return render_template('asistencia.html', clase_id=clase_id, alumnos=alumnos, clases_disponibles=clases_disponibles)

# ---------- CONFIRMAR ASISTENCIA ----------
@bp.route('/confirmar_asistencia/<int:clase_id>', methods=['POST'])
def confirmar_asistencia(clase_id):
    if 'usuario' not in session:
        flash("Debes iniciar sesión para confirmar la asistencia.", "error")
        return redirect(url_for('main.login'))

    try:
        with get_db() as conexion:
            cursor = conexion.cursor()

            # Obtener todos los alumnos inscritos en la clase
            cursor.execute("""
                SELECT alumno.id
                FROM alumno
                JOIN alumno_clase ON alumno.id = alumno_clase.alumno_id
                WHERE alumno_clase.clase_id = ?
            """, (clase_id,))
            alumnos_en_clase = cursor.fetchall()

            if not alumnos_en_clase:
                flash(f"No hay alumnos inscritos en la clase ID {clase_id} para registrar asistencia.", "info")
                return redirect(url_for('main.asistencia', clase_id=clase_id))

            presentes = 0
            ausentes = 0

            # Registrar asistencia para cada alumno según su estado final
            for alumno_tuple in alumnos_en_clase:
                alumno_id = alumno_tuple[0]
                estado = request.form.get(f'estado_{alumno_id}', 'no-detectado')
                # Solo marcar como presente si alcanzó el estado "presente" (5 detecciones)
                presente = estado == 'presente'

                # Verificar si ya existe un registro para este alumno en esta clase y día
                cursor.execute("""
                    SELECT id FROM asistencia 
                    WHERE clase_id = ? AND alumno_id = ? AND DATE(timestamp) = DATE('now')
                """, (clase_id, alumno_id))
                asistencia_existente = cursor.fetchone()

                if not asistencia_existente:
                    cursor.execute("""
                        INSERT INTO asistencia (clase_id, alumno_id, presente)
                        VALUES (?, ?, ?)
                    """, (clase_id, alumno_id, presente))
                    
                    if presente:
                        presentes += 1
                    else:
                        ausentes += 1

            conexion.commit()
            flash(f"Asistencia registrada correctamente: {presentes} presente(s), {ausentes} ausente(s).", "success")

    except sqlite3.Error as e:
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
        
        # Obtener los datos de los alumnos de la base de datos
        with get_db() as conexion:
            cursor = conexion.cursor()
            cursor.execute("""
                SELECT alumno.id, alumno.datos_rostro
                FROM alumno
                JOIN alumno_clase ON alumno.id = alumno_clase.alumno_id
                WHERE alumno_clase.clase_id = ? AND alumno.datos_rostro IS NOT NULL
            """, (clase_id,))
            alumnos = cursor.fetchall()

        if not alumnos:
            return {"mensaje": "No hay alumnos registrados con datos faciales"}, 400

        # Preparar los datos de los alumnos
        alumnos_ids = []
        alumnos_encodings = []
        for alumno_id, datos_rostro in alumnos:
            if datos_rostro:
                alumnos_ids.append(alumno_id)
                alumnos_encodings.append(pickle.loads(datos_rostro))

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
                            # Registrar el intento fallido
                            with get_db() as conexion:
                                cursor = conexion.cursor()
                                cursor.execute("""
                                    INSERT INTO registro_facial (alumno_id, estado)
                                    VALUES (?, 'fallido')
                                    ON CONFLICT(alumno_id) DO UPDATE SET 
                                    estado = 'fallido',
                                    intentos = intentos + 1
                                """, (alumno_id,))
                                conexion.commit()
                        else:
                            guardar_datos_faciales(alumno_id, datos_rostro)
                            mensaje = f"Datos faciales registrados correctamente para el alumno ID {alumno_id}."
                    except Exception as e:
                        mensaje = f"Error al procesar la imagen: {str(e)}"

    # Obtener la lista de alumnos con su estado de registro
    with get_db() as conexion:
        cursor = conexion.cursor()
        cursor.execute("""
            SELECT 
                alumno.id, 
                alumno.nombre, 
                alumno.rut,
                CASE 
                    WHEN alumno.datos_rostro IS NOT NULL THEN 'registrado'
                    WHEN rf.estado = 'fallido' THEN 'fallido'
                    ELSE 'pendiente'
                END as estado_registro,
                COALESCE(rf.intentos, 0) as intentos,
                rf.fecha_registro
            FROM alumno
            JOIN alumno_clase ON alumno.id = alumno_clase.alumno_id
            LEFT JOIN registro_facial rf ON alumno.id = rf.alumno_id
            WHERE alumno_clase.clase_id = ?
            ORDER BY alumno.nombre
        """, (clase_id,))
        
        alumnos = [{
            "id": row[0],
            "nombre": row[1],
            "rut": row[2],
            "estado_registro": row[3],
            "intentos": row[4],
            "fecha_registro": row[5]
        } for row in cursor.fetchall()]

    return render_template('ingresar_alumno.html', clase_id=clase_id, alumnos=alumnos, mensaje=mensaje)

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
        print(f"Error en capturar_foto: {str(e)}")  # Agregar log para debugging
        return {"mensaje": f"Error al procesar la imagen: {str(e)}"}, 400

# ---------- FUNCIONES AUXILIARES ----------
def procesar_imagen(imagen):
    encodings = face_recognition.face_encodings(imagen)
    if len(encodings) == 0:
        return None
    return pickle.dumps(encodings[0])

def guardar_datos_faciales(alumno_id, datos_rostro):
    with get_db() as conexion:
        cursor = conexion.cursor()
        try:
            # Actualizar los datos faciales del alumno
            cursor.execute("UPDATE alumno SET datos_rostro = ? WHERE id = ?", (datos_rostro, alumno_id))
            
            # Verificar si ya existe un registro en la tabla registro_facial
            cursor.execute("SELECT id, intentos FROM registro_facial WHERE alumno_id = ?", (alumno_id,))
            registro_existente = cursor.fetchone()
            
            if registro_existente:
                # Actualizar registro existente
                cursor.execute("""
                    UPDATE registro_facial 
                    SET estado = 'registrado',
                        fecha_registro = CURRENT_TIMESTAMP,
                        intentos = intentos + 1
                    WHERE alumno_id = ?
                """, (alumno_id,))
            else:
                # Crear nuevo registro
                cursor.execute("""
                    INSERT INTO registro_facial (alumno_id, estado)
                    VALUES (?, 'registrado')
                """, (alumno_id,))
            
            conexion.commit()
        except sqlite3.Error as e:
            print(f"Error al guardar datos faciales: {e}")
            conexion.rollback()
            raise

# ---------- RUTA RESERVADA PARA FUTURO USO ----------
@bp.route('/listar_alumnos/<int:clase_id>', methods=['GET'])
def listar_alumnos(clase_id):
    pass



