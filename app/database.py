import sqlite3

def crear_base_datos():
    conexion = sqlite3.connect("asistencia.db")
    cursor = conexion.cursor()

    # Tabla de profesores
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS profesor (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT NOT NULL,
        usuario TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL
    );
    """)

    # Tabla de alumnos
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS alumno (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT NOT NULL,
        rut TEXT NOT NULL UNIQUE,
        datos_rostro BLOB NOT NULL
    );
    """)

    # Tabla de clases
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS clase (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT NOT NULL,
        fecha DATE NOT NULL
    );
    """)

    # Relación profesor-clase (muchos a muchos)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS profesor_clase (
        profesor_id INTEGER NOT NULL,
        clase_id INTEGER NOT NULL,
        PRIMARY KEY (profesor_id, clase_id),
        FOREIGN KEY (profesor_id) REFERENCES profesor(id),
        FOREIGN KEY (clase_id) REFERENCES clase(id)
    );
    """)

    # Relación alumno-clase (muchos a muchos)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS alumno_clase (
        alumno_id INTEGER NOT NULL,
        clase_id INTEGER NOT NULL,
        PRIMARY KEY (alumno_id, clase_id),
        FOREIGN KEY (alumno_id) REFERENCES alumno(id),
        FOREIGN KEY (clase_id) REFERENCES clase(id)
    );
    """)

    # Tabla de asistencias
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS asistencia (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        clase_id INTEGER NOT NULL,
        alumno_id INTEGER NOT NULL,
        presente BOOL NOT NULL,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (clase_id) REFERENCES clase(id),
        FOREIGN KEY (alumno_id) REFERENCES alumno(id)
    );
    """)

    conexion.commit()
    conexion.close()
    print("Base de datos creada correctamente como 'asistencia.db'.")

if __name__ == "__main__":
    crear_base_datos()