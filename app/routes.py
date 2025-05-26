import face_recognition
import pickle
from flask import Blueprint, render_template, redirect, url_for, request, session
import sqlite3
from PIL import Image
import base64
import io

main = Blueprint('main', __name__)

# Simulación de login (sin BD por ahora)
@main.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        usuario = request.form.get('usuario')
        # Verificar si el usuario existe en la tabla profesor
        conexion = sqlite3.connect("asistencia.db")
        cursor = conexion.cursor()
        cursor.execute("SELECT usuario FROM profesor WHERE usuario = ?", (usuario,))
        profesor = cursor.fetchone()
        conexion.close()
        if profesor:
            session['usuario'] = usuario
            return redirect(url_for('main.index'))
        else:
            return render_template('login.html', error='Usuario inválido')
    return render_template('login.html')

@main.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('main.login'))

@main.route('/')
def index():
    if 'usuario' not in session:
        return redirect(url_for('main.login'))
    
    usuario = session['usuario']
    # Obtener id del profesor
    conexion = sqlite3.connect("asistencia.db")
    cursor = conexion.cursor()
    cursor.execute("SELECT id, nombre FROM profesor WHERE usuario = ?", (usuario,))
    profesor = cursor.fetchone()
    if not profesor:
        conexion.close()
        return redirect(url_for('main.logout'))
    profesor_id, nombre_profesor = profesor

    # Obtener clases del profesor
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

@main.route('/asistencia/<int:clase_id>')
def asistencia(clase_id):
    if 'usuario' not in session:
        return redirect(url_for('main.login'))
    conexion = sqlite3.connect("asistencia.db")
    cursor = conexion.cursor()
    cursor.execute("""
        SELECT alumno.id, alumno.nombre, alumno.rut
        FROM alumno
        JOIN alumno_clase ON alumno.id = alumno_clase.alumno_id
        WHERE alumno_clase.clase_id = ?
    """, (clase_id,))
    alumnos = [{"id": a[0], "nombre": a[1], "rut": a[2]} for a in cursor.fetchall()]
    conexion.close()

    return render_template('asistencia.html', clase_id=clase_id, alumnos=alumnos)

@main.route('/procesar_fotograma/<int:clase_id>', methods=['POST'])
def procesar_fotograma(clase_id):
    if 'usuario' not in session:
        return {"mensaje": "No autorizado"}, 401

    data = request.get_json()
    imagen_base64 = data.get('imagen')

    if not imagen_base64:
        return {"mensaje": "No se recibió ninguna imagen"}, 400

    # Decodificar la imagen Base64
    try:
        header, encoded = imagen_base64.split(',', 1)
        imagen_bytes = base64.b64decode(encoded)
        imagen = face_recognition.load_image_file(io.BytesIO(imagen_bytes))
    except Exception as e:
        return {"mensaje": f"Error al procesar la imagen: {str(e)}"}, 400

    # Extraer datos faciales de la imagen capturada
    encodings_capturados = face_recognition.face_encodings(imagen)
    if len(encodings_capturados) == 0:
        return {"mensaje": "No se detectó ningún rostro en la imagen"}, 400

    # Obtener los datos faciales de los alumnos de la clase
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

    # Comparar los datos faciales capturados con los almacenados
    alumnos_detectados = []
    for alumno_id, datos_rostro in alumnos:
        if datos_rostro:
            datos_rostro_almacenados = pickle.loads(datos_rostro)
            coincidencias = face_recognition.compare_faces([datos_rostro_almacenados], encodings_capturados[0],tolerance=0.6)
            alumnos_detectados.append({"id": alumno_id, "detectado": bool(coincidencias[0])})

    return {"alumnos": alumnos_detectados}

@main.route('/ingresar_alumno/<int:clase_id>', methods=['GET', 'POST'])
def ingresar_alumno(clase_id):
    if 'usuario' not in session:
        return redirect(url_for('main.login'))

    mensaje = None

    if request.method == 'POST':
        # Buscar qué alumno envió la foto
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

    # Obtener alumnos del curso
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

@main.route('/capturar_foto/<int:alumno_id>', methods=['POST'])
def capturar_foto(alumno_id):
    if 'usuario' not in session:
        return {"mensaje": "No autorizado"}, 401

    data = request.get_json()
    imagen_base64 = data.get('imagen')

    if not imagen_base64:
        return {"mensaje": "No se recibió ninguna imagen"}, 400

    # Decodificar la imagen Base64
    try:
        header, encoded = imagen_base64.split(',', 1)
        imagen_bytes = base64.b64decode(encoded)
        imagen = Image.open(io.BytesIO(imagen_bytes))
    except Exception as e:
        return {"mensaje": f"Error al procesar la imagen: {str(e)}"}, 400

    # Procesar la imagen y extraer datos faciales
    imagen_array = face_recognition.load_image_file(io.BytesIO(imagen_bytes))
    datos_rostro = procesar_imagen(imagen_array)
    if datos_rostro is None:
        return {"mensaje": "No se detectó ningún rostro en la imagen"}, 400

    # Guardar los datos faciales en la base de datos
    guardar_datos_faciales(alumno_id, datos_rostro)

    return {"mensaje": "Datos faciales registrados correctamente"}

def procesar_imagen(imagen):
    """
    Procesa una imagen y extrae los datos faciales (encodings).
    Retorna los encodings o None si no se detecta ningún rostro.
    """
    encodings = face_recognition.face_encodings(imagen)
    if len(encodings) == 0:
        return None
    return pickle.dumps(encodings[0])

def guardar_datos_faciales(alumno_id, datos_rostro):
    """
    Guarda los datos faciales en la base de datos para un alumno específico.
    """
    conexion = sqlite3.connect("asistencia.db")
    cursor = conexion.cursor()
    cursor.execute("UPDATE alumno SET datos_rostro = ? WHERE id = ?", (datos_rostro, alumno_id))
    conexion.commit()
    conexion.close()

@main.route('/listar_alumnos/<int:clase_id>', methods=['GET'])
def listar_alumnos(clase_id):
    # Lógica para listar alumnos
    pass