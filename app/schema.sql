-- Tabla de profesores
CREATE TABLE IF NOT EXISTS profesor (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL,
    usuario TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL
);

-- Tabla de alumnos
CREATE TABLE IF NOT EXISTS alumno (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL,
    rut TEXT NOT NULL UNIQUE,
    datos_rostro BLOB
);

-- Tabla de clases
CREATE TABLE IF NOT EXISTS clase (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL,
    fecha DATE NOT NULL
);

-- Relación profesor-clase (muchos a muchos)
CREATE TABLE IF NOT EXISTS profesor_clase (
    profesor_id INTEGER NOT NULL,
    clase_id INTEGER NOT NULL,
    PRIMARY KEY (profesor_id, clase_id),
    FOREIGN KEY (profesor_id) REFERENCES profesor(id) ON DELETE CASCADE,
    FOREIGN KEY (clase_id) REFERENCES clase(id) ON DELETE CASCADE
);

-- Relación alumno-clase (muchos a muchos)
CREATE TABLE IF NOT EXISTS alumno_clase (
    alumno_id INTEGER NOT NULL,
    clase_id INTEGER NOT NULL,
    PRIMARY KEY (alumno_id, clase_id),
    FOREIGN KEY (alumno_id) REFERENCES alumno(id) ON DELETE CASCADE,
    FOREIGN KEY (clase_id) REFERENCES clase(id) ON DELETE CASCADE
);

-- Tabla de asistencias
CREATE TABLE IF NOT EXISTS asistencia (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    clase_id INTEGER NOT NULL,
    alumno_id INTEGER NOT NULL,
    presente BOOLEAN NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (clase_id) REFERENCES clase(id) ON DELETE CASCADE,
    FOREIGN KEY (alumno_id) REFERENCES alumno(id) ON DELETE CASCADE
);

-- Tabla para el tracking de registros faciales
CREATE TABLE IF NOT EXISTS registro_facial (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    alumno_id INTEGER NOT NULL,
    fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    calidad_registro FLOAT,  -- Valor entre 0 y 1 indicando la calidad del registro
    intentos INTEGER DEFAULT 1,
    estado TEXT CHECK(estado IN ('pendiente', 'registrado', 'fallido')) DEFAULT 'pendiente',
    FOREIGN KEY (alumno_id) REFERENCES alumno(id) ON DELETE CASCADE
); 