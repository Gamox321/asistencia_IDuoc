import face_recognition
import pickle
from flask import Flask, render_template, request, redirect, url_for, flash, session
import sqlite3
from PIL import Image
import base64
import io
import os
import hashlib



app = Flask(__name__)
app.secret_key = 'clave-secreta'

password = "contraseña123"
print(hashlib.sha256(password.encode()).hexdigest())


# ---------- LOGIN ----------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        # Convertimos la contraseña a hash
        password_hashed = hashlib.sha256(password.encode()).hexdigest()
        print(f"Login: {username=} {password_hashed=}")

        # Consultamos en la base de datos
        conexion = sqlite3.connect("asistencia.db")
        cursor = conexion.cursor()
        cursor.execute(
            "SELECT id, nombre FROM profesor WHERE usuario = ? AND password_hash = ?",
            (username, password_hashed)
        )
        profesor = cursor.fetchone()
        conexion.close()

        if profesor:
            session['usuario'] = username
            return redirect(url_for('home'))
        else:
            flash('Usuario o contraseña incorrectos')
            return render_template('login.html')

    return render_template('login.html')



@app.route('/logout')
def logout():
    session.pop('usuario', None)
    return redirect(url_for('login'))

# ---------- VISTA PRINCIPAL ----------
@app.route('/')
def home():
    if 'usuario' not in session:
        return render_template('inicio_publico.html')  # Muestra página pública

    # Página para profesor autenticado
    usuario = session['usuario']
    conexion = sqlite3.connect("asistencia.db")
    cursor = conexion.cursor()
    cursor.execute("SELECT id, nombre FROM profesor WHERE usuario = ?", (usuario,))
    profesor = cursor.fetchone()
    if not profesor:
        conexion.close()
        return redirect(url_for('logout'))
    profesor_id, nombre_profesor = profesor

    cursor.execute("""
        SELECT clase.id, clase.nombre, clase.fecha
        FROM clase
        JOIN profesor_clase ON clase.id = profesor_clase.clase_id
        WHERE profesor_clase.profesor_id = ?
        ORDER BY clase.fecha DESC
    """, (profesor_id,))
    clases = cursor.fetchall()
    conexion.close()
    return render_template('index.html', nombre_profesor=nombre_profesor, clases=clases)


# ---------- VER CLASES ----------
@app.route('/clases')
def ver_clases():
    if 'usuario' not in session:
        return redirect(url_for('login'))

    usuario = session['usuario']
    conexion = sqlite3.connect("asistencia.db")
    cursor = conexion.cursor()
    cursor.execute("SELECT id, nombre FROM profesor WHERE usuario = ?", (usuario,))
    profesor = cursor.fetchone()
    if not profesor:
        conexion.close()
        return redirect(url_for('logout'))

    profesor_id, nombre_profesor = profesor

    cursor.execute("""
        SELECT clase.id, clase.nombre, clase.fecha
        FROM clase
        JOIN profesor_clase ON clase.id = profesor_clase.clase_id
        WHERE profesor_clase.profesor_id = ?
        ORDER BY clase.fecha DESC
    """, (profesor_id,))
    clases = cursor.fetchall()
    conexion.close()

    return render_template('clases.html', nombre_profesor=nombre_profesor, clases=clases)

# ---------- ASISTENCIA ----------
@app.route('/asistencia/<int:clase_id>')
def asistencia(clase_id):
    if 'usuario' not in session:
        return redirect(url_for('login'))

    conexion = sqlite3.connect("asistencia.db")
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
    conexion.close()

    return render_template('asistencia.html', clase_id=clase_id, alumnos=alumnos, clases_disponibles=clases_disponibles)

# ---------- PROCESAR FOTOGRAMA ----------
@app.route('/procesar_fotograma/<int:clase_id>', methods=['POST'])
def procesar_fotograma(clase_id):
    if 'usuario' not in session:
        return {"mensaje": "No autorizado"}, 401

    data = request.get_json()
    imagen_base64 = data.get('imagen')

    if not imagen_base64:
        return {"mensaje": "No se recibió ninguna imagen"}, 400

    try:
        header, encoded = imagen_base64.split(',', 1)
        imagen_bytes = base64.b64decode(encoded)
        imagen = face_recognition.load_image_file(io.BytesIO(imagen_bytes))
    except Exception as e:
        return {"mensaje": f"Error al procesar la imagen: {str(e)}"}, 400

    encodings_capturados = face_recognition.face_encodings(imagen)
    if len(encodings_capturados) == 0:
        return {"mensaje": "No se detectó ningún rostro en la imagen"}, 400

    conexion = sqlite3.connect("asistencia.db")
    cursor = conexion.cursor()
    cursor.execute("""
        SELECT alumno.id, alumno.datos_rostro
        FROM alumno
        JOIN alumno_clase ON alumno.id = alumno_clase.alumno_id
        WHERE alumno_clase.clase_id = ?
    """, (clase_id,))
    alumnos = cursor.fetchall()
    conexion.close()

    alumnos_detectados = []
    for alumno_id, datos_rostro in alumnos:
        if datos_rostro:
            datos_rostro_almacenados = pickle.loads(datos_rostro)
            coincidencias = face_recognition.compare_faces([datos_rostro_almacenados], encodings_capturados[0], tolerance=0.5)
            alumnos_detectados.append({"id": alumno_id, "detectado": bool(coincidencias[0])})

    return {"alumnos": alumnos_detectados}

# ---------- INGRESAR DATOS FACIALES ----------
@app.route('/ingresar_alumno/<int:clase_id>', methods=['GET', 'POST'])
def ingresar_alumno(clase_id):
    if 'usuario' not in session:
        return redirect(url_for('login'))

    mensaje = None

    if request.method == 'POST':
        for key in request.files:
            if key.startswith('foto_'):
                alumno_id = int(key.split('_')[1])
                imagen_file = request.files[key]
                if imagen_file and imagen_file.filename != '':
                    imagen = face_recognition.load_image_file(imagen_file)
                    datos_rostro = procesar_imagen(imagen)
                    if datos_rostro is None:
                        mensaje = f"No se detectó rostro en la imagen para el alumno ID {alumno_id}."
                    else:
                        guardar_datos_faciales(alumno_id, datos_rostro)
                        mensaje = f"Datos faciales registrados correctamente para el alumno ID {alumno_id}."

    conexion = sqlite3.connect("asistencia.db")
    cursor = conexion.cursor()
    cursor.execute("""
        SELECT alumno.id, alumno.nombre, alumno.rut
        FROM alumno
        JOIN alumno_clase ON alumno.id = alumno_clase.alumno_id
        WHERE alumno_clase.clase_id = ?
        ORDER BY alumno.nombre
    """, (clase_id,))
    alumnos = [{"id": a[0], "nombre": a[1], "rut": a[2]} for a in cursor.fetchall()]
    conexion.close()
    return render_template('ingresar_alumno.html', clase_id=clase_id, alumnos=alumnos, mensaje=mensaje)

# ---------- CAPTURAR FOTO ----------
@app.route('/capturar_foto/<int:alumno_id>', methods=['POST'])
def capturar_foto(alumno_id):
    if 'usuario' not in session:
        return {"mensaje": "No autorizado"}, 401

    data = request.get_json()
    imagen_base64 = data.get('imagen')

    if not imagen_base64:
        return {"mensaje": "No se recibió ninguna imagen"}, 400

    try:
        header, encoded = imagen_base64.split(',', 1)
        imagen_bytes = base64.b64decode(encoded)
        imagen = Image.open(io.BytesIO(imagen_bytes))
    except Exception as e:
        return {"mensaje": f"Error al procesar la imagen: {str(e)}"}, 400

    imagen_array = face_recognition.load_image_file(io.BytesIO(imagen_bytes))
    datos_rostro = procesar_imagen(imagen_array)
    if datos_rostro is None:
        return {"mensaje": "No se detectó ningún rostro en la imagen"}, 400

    guardar_datos_faciales(alumno_id, datos_rostro)
    return {"mensaje": "Datos faciales registrados correctamente"}

# ---------- FUNCIONES AUXILIARES ----------
def procesar_imagen(imagen):
    encodings = face_recognition.face_encodings(imagen)
    if len(encodings) == 0:
        return None
    return pickle.dumps(encodings[0])

def guardar_datos_faciales(alumno_id, datos_rostro):
    conexion = sqlite3.connect("asistencia.db")
    cursor = conexion.cursor()
    cursor.execute("UPDATE alumno SET datos_rostro = ? WHERE id = ?", (datos_rostro, alumno_id))
    conexion.commit()
    conexion.close()

# ---------- RUTA RESERVADA PARA FUTURO USO ----------
@app.route('/listar_alumnos/<int:clase_id>', methods=['GET'])
def listar_alumnos(clase_id):
    pass



