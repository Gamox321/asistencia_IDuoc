import sqlite3
import pickle
import random
import hashlib
import os
from datetime import date, timedelta
from app.config import Config

# Función para generar vectores de rostro ficticios
def generar_vector_rostro():
    return pickle.dumps([random.random() for _ in range(128)])

# Hasheo de contraseñas simple para pruebas
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def insertar_datos():
    # Asegurarse de que el directorio de datos existe
    os.makedirs(os.path.dirname(Config.DATABASE_PATH), exist_ok=True)
    
    print(f"Conectando a la base de datos en: {Config.DATABASE_PATH}")
    conexion = sqlite3.connect(Config.DATABASE_PATH)
    cursor = conexion.cursor()

    try:
        # Insertar profesores
        profesores = [
            ("Arturo Vargas", "avargas", hash_password("arturo123")),
            ("Claudia Ríos", "crios", hash_password("claudia123"))
        ]
        cursor.executemany("INSERT OR IGNORE INTO profesor (nombre, usuario, password_hash) VALUES (?, ?, ?)", profesores)

        # Insertar alumnos
        nombres_alumnos = [
            "Genaro Marín", "Héctor Torres", "Diego Ortiz", "Camila Reyes", "Valentina Soto",
            "Javiera Contreras", "Tomás Figueroa", "Lucas Morales", "Benjamín Araya", "Antonia Fuentes",
            "Matías Riquelme", "Isidora Carrasco", "Fernanda Pérez", "Ignacio Salazar", "Martina Herrera",
            "Catalina López", "Vicente Silva", "Emilia Gallardo", "Andrés Vega", "Florencia Pino"
        ]

        alumnos = []
        for i, nombre in enumerate(nombres_alumnos, start=1):
            rut = f"20.{i:03d}.{random.randint(100,999)}-{random.randint(0,9)}"
            # Ya no generamos datos faciales ficticios, los dejamos como NULL
            alumnos.append((nombre, rut, None))

        cursor.executemany("INSERT OR IGNORE INTO alumno (nombre, rut, datos_rostro) VALUES (?, ?, ?)", alumnos)

        # Insertar clases (últimos 3 días)
        clases = [
            ("Portafolio de Título", date.today().isoformat()),
            ("Redes y Seguridad", (date.today() - timedelta(days=1)).isoformat()),
            ("Programación Avanzada", (date.today() - timedelta(days=2)).isoformat())
        ]
        cursor.executemany("INSERT OR IGNORE INTO clase (nombre, fecha) VALUES (?, ?)", clases)

        # Obtener IDs generados
        cursor.execute("SELECT id FROM profesor")
        ids_profesores = [row[0] for row in cursor.fetchall()]

        cursor.execute("SELECT id FROM clase")
        ids_clases = [row[0] for row in cursor.fetchall()]

        cursor.execute("SELECT id FROM alumno")
        ids_alumnos = [row[0] for row in cursor.fetchall()]

        # Relacionar profesores con dos clases cada uno (alternando)
        profesor_clase = []
        for i, profesor_id in enumerate(ids_profesores):
            profesor_clase.append((profesor_id, ids_clases[i % len(ids_clases)]))
            profesor_clase.append((profesor_id, ids_clases[(i+1) % len(ids_clases)]))
        cursor.executemany("INSERT OR IGNORE INTO profesor_clase (profesor_id, clase_id) VALUES (?, ?)", profesor_clase)

        # Relacionar alumnos con dos clases cada uno (alternando)
        alumno_clase = []
        for i, alumno_id in enumerate(ids_alumnos):
            alumno_clase.append((alumno_id, ids_clases[i % len(ids_clases)]))
            alumno_clase.append((alumno_id, ids_clases[(i+1) % len(ids_clases)]))
        cursor.executemany("INSERT OR IGNORE INTO alumno_clase (alumno_id, clase_id) VALUES (?, ?)", alumno_clase)

        # Inicializar la tabla registro_facial para cada alumno como pendiente
        for alumno_id in ids_alumnos:
            cursor.execute("""
                INSERT OR IGNORE INTO registro_facial (alumno_id, estado, intentos, fecha_registro)
                VALUES (?, 'pendiente', 0, NULL)
            """, (alumno_id,))

        conexion.commit()
        print("Datos de prueba insertados correctamente.")
        
        # Mostrar resumen de los datos insertados
        print("\nResumen de datos insertados:")
        print(f"- Profesores: {len(profesores)}")
        print(f"- Alumnos: {len(alumnos)}")
        print(f"- Clases: {len(clases)}")
        print(f"- Relaciones profesor-clase: {len(profesor_clase)}")
        print(f"- Relaciones alumno-clase: {len(alumno_clase)}")

    except sqlite3.Error as e:
        print(f"Error al insertar datos: {e}")
        conexion.rollback()
    finally:
        conexion.close()

if __name__ == "__main__":
    # Inicializar la configuración
    Config.init_app()
    insertar_datos()