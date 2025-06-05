-- Esquema de base de datos MySQL para Sistema de Asistencia DuocUC
-- Basado en el Modelo Entidad-Relación proporcionado

-- Configuración inicial de la base de datos
SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
SET AUTOCOMMIT = 0;
START TRANSACTION;
SET time_zone = "+00:00";

-- Tabla de información de contacto
CREATE TABLE IF NOT EXISTS informacion_contacto (
    id INT AUTO_INCREMENT PRIMARY KEY,
    email VARCHAR(100),
    telefono VARCHAR(20),
    comuna VARCHAR(50),
    ciudad VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Tabla de carreras
CREATE TABLE IF NOT EXISTS carrera (
    id INT AUTO_INCREMENT PRIMARY KEY,
    codigo VARCHAR(10) NOT NULL UNIQUE,
    nombre VARCHAR(100) NOT NULL,
    descripcion TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_codigo (codigo)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Tabla de secciones
CREATE TABLE IF NOT EXISTS seccion (
    id INT AUTO_INCREMENT PRIMARY KEY,
    codigo VARCHAR(20) NOT NULL,
    cupo_maximo INT NOT NULL DEFAULT 40,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_codigo (codigo)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Tabla de periodos académicos
CREATE TABLE IF NOT EXISTS periodo_academico (
    id INT AUTO_INCREMENT PRIMARY KEY,
    año INT NOT NULL,
    semestre INT NOT NULL CHECK (semestre IN (1, 2)),
    fecha_inicio DATE NOT NULL,
    fecha_fin DATE NOT NULL,
    estado ENUM('activo', 'inactivo', 'planificacion') DEFAULT 'planificacion',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY unique_periodo (año, semestre),
    INDEX idx_estado (estado),
    INDEX idx_fechas (fecha_inicio, fecha_fin)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Tabla de alumnos
CREATE TABLE IF NOT EXISTS alumno (
    id INT AUTO_INCREMENT PRIMARY KEY,
    rut VARCHAR(12) NOT NULL UNIQUE,
    nombre VARCHAR(50) NOT NULL,
    apellido_paterno VARCHAR(50) NOT NULL,
    apellido_materno VARCHAR(50),
    carrera_id INT NOT NULL,
    informacion_contacto_id INT,
    datos_rostro MEDIUMBLOB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (carrera_id) REFERENCES carrera(id) ON DELETE RESTRICT ON UPDATE CASCADE,
    FOREIGN KEY (informacion_contacto_id) REFERENCES informacion_contacto(id) ON DELETE SET NULL ON UPDATE CASCADE,
    INDEX idx_rut (rut),
    INDEX idx_nombre (nombre, apellido_paterno),
    INDEX idx_carrera (carrera_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Tabla de profesores
CREATE TABLE IF NOT EXISTS profesor (
    id INT AUTO_INCREMENT PRIMARY KEY,
    rut VARCHAR(12) NOT NULL UNIQUE,
    nombre VARCHAR(50) NOT NULL,
    apellido_paterno VARCHAR(50) NOT NULL,
    apellido_materno VARCHAR(50),
    usuario VARCHAR(50) NOT NULL UNIQUE,
    informacion_contacto_id INT,
    estado ENUM('activo', 'inactivo', 'suspendido') DEFAULT 'activo',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (informacion_contacto_id) REFERENCES informacion_contacto(id) ON DELETE SET NULL ON UPDATE CASCADE,
    INDEX idx_rut (rut),
    INDEX idx_usuario (usuario),
    INDEX idx_estado (estado)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Tabla de autenticación
CREATE TABLE IF NOT EXISTS autenticacion (
    id INT AUTO_INCREMENT PRIMARY KEY,
    usuario VARCHAR(50) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    tipo_usuario ENUM('profesor', 'admin', 'coordinador') DEFAULT 'profesor',
    profesor_id INT NOT NULL,
    ultimo_login TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (profesor_id) REFERENCES profesor(id) ON DELETE CASCADE ON UPDATE CASCADE,
    INDEX idx_usuario (usuario),
    INDEX idx_tipo (tipo_usuario)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Tabla de matrículas
CREATE TABLE IF NOT EXISTS matricula (
    id INT AUTO_INCREMENT PRIMARY KEY,
    alumno_id INT NOT NULL,
    estado ENUM('matriculado', 'retirado', 'suspendido', 'egresado') DEFAULT 'matriculado',
    fecha_matricula TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (alumno_id) REFERENCES alumno(id) ON DELETE CASCADE ON UPDATE CASCADE,
    INDEX idx_alumno (alumno_id),
    INDEX idx_estado (estado),
    INDEX idx_fecha (fecha_matricula)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Tabla de clases
CREATE TABLE IF NOT EXISTS clase (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    fecha DATE NOT NULL,
    hora_inicio TIME NOT NULL,
    hora_fin TIME NOT NULL,
    sala VARCHAR(20),
    modalidad ENUM('presencial', 'virtual', 'hibrida') DEFAULT 'presencial',
    seccion_id INT NOT NULL,
    profesor_id INT NOT NULL,
    periodo_academico_id INT NOT NULL,
    estado VARCHAR(20) DEFAULT 'activa',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (seccion_id) REFERENCES seccion(id) ON DELETE CASCADE,
    FOREIGN KEY (profesor_id) REFERENCES profesor(id) ON DELETE CASCADE,
    FOREIGN KEY (periodo_academico_id) REFERENCES periodo_academico(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Tabla de asistencias
CREATE TABLE IF NOT EXISTS asistencia (
    id INT AUTO_INCREMENT PRIMARY KEY,
    clase_id INT NOT NULL,
    alumno_id INT NOT NULL,
    presente TINYINT(1) NOT NULL DEFAULT 0,
    fecha_asistencia DATE NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    observaciones TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (clase_id) REFERENCES clase(id) ON DELETE CASCADE ON UPDATE CASCADE,
    FOREIGN KEY (alumno_id) REFERENCES alumno(id) ON DELETE CASCADE ON UPDATE CASCADE,
    INDEX idx_clase_fecha (clase_id, fecha_asistencia),
    INDEX idx_alumno (alumno_id),
    INDEX idx_presente (presente),
    UNIQUE KEY unique_asistencia_diaria (clase_id, alumno_id, fecha_asistencia)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Tabla para el tracking de registros faciales
CREATE TABLE IF NOT EXISTS registro_facial (
    id INT AUTO_INCREMENT PRIMARY KEY,
    alumno_id INT NOT NULL,
    estado ENUM('pendiente', 'registrado', 'fallido') DEFAULT 'pendiente',
    intentos INT DEFAULT 1,
    fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    calidad_registro FLOAT CHECK (calidad_registro >= 0 AND calidad_registro <= 1),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (alumno_id) REFERENCES alumno(id) ON DELETE CASCADE ON UPDATE CASCADE,
    UNIQUE KEY unique_registro_facial (alumno_id),
    INDEX idx_estado (estado),
    INDEX idx_fecha (fecha_registro)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Tabla de relación profesor-clase (muchos a muchos)
CREATE TABLE IF NOT EXISTS profesor_clase (
    profesor_id INT NOT NULL,
    clase_id INT NOT NULL,
    rol ENUM('titular', 'ayudante', 'invitado') DEFAULT 'titular',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (profesor_id, clase_id),
    FOREIGN KEY (profesor_id) REFERENCES profesor(id) ON DELETE CASCADE ON UPDATE CASCADE,
    FOREIGN KEY (clase_id) REFERENCES clase(id) ON DELETE CASCADE ON UPDATE CASCADE,
    INDEX idx_rol (rol)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Tabla de relación alumno-clase (muchos a muchos) - inscripciones
CREATE TABLE IF NOT EXISTS alumno_clase (
    alumno_id INT NOT NULL,
    clase_id INT NOT NULL,
    fecha_inscripcion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    estado ENUM('inscrito', 'retirado') DEFAULT 'inscrito',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (alumno_id, clase_id),
    FOREIGN KEY (alumno_id) REFERENCES alumno(id) ON DELETE CASCADE ON UPDATE CASCADE,
    FOREIGN KEY (clase_id) REFERENCES clase(id) ON DELETE CASCADE ON UPDATE CASCADE,
    INDEX idx_estado (estado),
    INDEX idx_fecha (fecha_inscripcion)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ====================
-- NUEVAS TABLAS PARA FUNCIONALIDADES DE ALTA PRIORIDAD
-- ====================

-- Tabla de permisos del sistema
CREATE TABLE IF NOT EXISTS permisos (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(50) NOT NULL UNIQUE,
    descripcion VARCHAR(255),
    categoria VARCHAR(30) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_categoria (categoria)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Tabla de roles del sistema
CREATE TABLE IF NOT EXISTS roles (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(30) NOT NULL UNIQUE,
    descripcion VARCHAR(255),
    nivel_acceso INT NOT NULL DEFAULT 1,
    activo BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_nivel (nivel_acceso),
    INDEX idx_activo (activo)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Tabla de relación roles-permisos (muchos a muchos)
CREATE TABLE IF NOT EXISTS rol_permisos (
    rol_id INT NOT NULL,
    permiso_id INT NOT NULL,
    granted_by INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (rol_id, permiso_id),
    FOREIGN KEY (rol_id) REFERENCES roles(id) ON DELETE CASCADE ON UPDATE CASCADE,
    FOREIGN KEY (permiso_id) REFERENCES permisos(id) ON DELETE CASCADE ON UPDATE CASCADE,
    FOREIGN KEY (granted_by) REFERENCES profesor(id) ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Tabla de asignación de roles a usuarios
CREATE TABLE IF NOT EXISTS usuario_roles (
    usuario_id INT NOT NULL,
    rol_id INT NOT NULL,
    assigned_by INT,
    fecha_asignacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    fecha_expiracion TIMESTAMP NULL,
    activo BOOLEAN DEFAULT TRUE,
    PRIMARY KEY (usuario_id, rol_id),
    FOREIGN KEY (usuario_id) REFERENCES profesor(id) ON DELETE CASCADE ON UPDATE CASCADE,
    FOREIGN KEY (rol_id) REFERENCES roles(id) ON DELETE CASCADE ON UPDATE CASCADE,
    FOREIGN KEY (assigned_by) REFERENCES profesor(id) ON DELETE SET NULL ON UPDATE CASCADE,
    INDEX idx_activo (activo),
    INDEX idx_expiracion (fecha_expiracion)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Tabla de logs de auditoría
CREATE TABLE IF NOT EXISTS logs_auditoria (
    id INT AUTO_INCREMENT PRIMARY KEY,
    usuario_id INT,
    accion VARCHAR(50) NOT NULL,
    tabla_afectada VARCHAR(50),
    registro_id INT,
    datos_anteriores JSON,
    datos_nuevos JSON,
    ip_address VARCHAR(45),
    user_agent TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (usuario_id) REFERENCES profesor(id) ON DELETE SET NULL ON UPDATE CASCADE,
    INDEX idx_usuario_fecha (usuario_id, timestamp),
    INDEX idx_accion (accion),
    INDEX idx_tabla (tabla_afectada),
    INDEX idx_timestamp (timestamp)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Tabla de intentos de login
CREATE TABLE IF NOT EXISTS login_attempts (
    id INT AUTO_INCREMENT PRIMARY KEY,
    usuario VARCHAR(50) NOT NULL,
    ip_address VARCHAR(45) NOT NULL,
    user_agent TEXT,
    exitoso BOOLEAN NOT NULL DEFAULT FALSE,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_usuario_timestamp (usuario, timestamp),
    INDEX idx_ip_timestamp (ip_address, timestamp),
    INDEX idx_exitoso (exitoso)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Tabla de sesiones activas
CREATE TABLE IF NOT EXISTS sesiones_activas (
    id VARCHAR(255) PRIMARY KEY,
    usuario_id INT NOT NULL,
    ip_address VARCHAR(45),
    user_agent TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL,
    activa BOOLEAN DEFAULT TRUE,
    FOREIGN KEY (usuario_id) REFERENCES profesor(id) ON DELETE CASCADE ON UPDATE CASCADE,
    INDEX idx_usuario (usuario_id),
    INDEX idx_expires (expires_at),
    INDEX idx_activa (activa),
    INDEX idx_last_activity (last_activity)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Tabla de configuraciones del sistema
CREATE TABLE IF NOT EXISTS configuraciones (
    id INT AUTO_INCREMENT PRIMARY KEY,
    clave VARCHAR(100) NOT NULL UNIQUE,
    valor TEXT,
    tipo ENUM('string', 'integer', 'boolean', 'json') DEFAULT 'string',
    descripcion VARCHAR(255),
    categoria VARCHAR(50),
    modificable BOOLEAN DEFAULT TRUE,
    updated_by INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (updated_by) REFERENCES profesor(id) ON DELETE SET NULL ON UPDATE CASCADE,
    INDEX idx_categoria (categoria),
    INDEX idx_modificable (modificable)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Tabla de notificaciones
CREATE TABLE IF NOT EXISTS notificaciones (
    id INT AUTO_INCREMENT PRIMARY KEY,
    usuario_id INT,
    tipo ENUM('info', 'warning', 'error', 'success') DEFAULT 'info',
    titulo VARCHAR(255) NOT NULL,
    mensaje TEXT NOT NULL,
    leida BOOLEAN DEFAULT FALSE,
    url_accion VARCHAR(255),
    datos_extra JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    leida_at TIMESTAMP NULL,
    FOREIGN KEY (usuario_id) REFERENCES profesor(id) ON DELETE CASCADE ON UPDATE CASCADE,
    INDEX idx_usuario_leida (usuario_id, leida),
    INDEX idx_tipo (tipo),
    INDEX idx_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Tabla de reportes programados
CREATE TABLE IF NOT EXISTS reportes_programados (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    tipo_reporte ENUM('asistencia', 'estadisticas', 'alumnos', 'custom') NOT NULL,
    parametros JSON,
    frecuencia ENUM('diario', 'semanal', 'mensual', 'trimestral') NOT NULL,
    proxima_ejecucion TIMESTAMP NOT NULL,
    destinatarios JSON,
    activo BOOLEAN DEFAULT TRUE,
    created_by INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (created_by) REFERENCES profesor(id) ON DELETE CASCADE ON UPDATE CASCADE,
    INDEX idx_activo_proxima (activo, proxima_ejecucion),
    INDEX idx_tipo (tipo_reporte),
    INDEX idx_frecuencia (frecuencia)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Tabla de historial de reportes ejecutados
CREATE TABLE IF NOT EXISTS historial_reportes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    reporte_programado_id INT,
    ejecutado_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    exitoso BOOLEAN NOT NULL,
    archivo_generado VARCHAR(255),
    error_mensaje TEXT,
    tiempo_ejecucion INT,
    registros_procesados INT,
    FOREIGN KEY (reporte_programado_id) REFERENCES reportes_programados(id) ON DELETE SET NULL ON UPDATE CASCADE,
    INDEX idx_reporte_fecha (reporte_programado_id, ejecutado_at),
    INDEX idx_exitoso (exitoso)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Tabla de alertas del sistema
CREATE TABLE IF NOT EXISTS alertas_sistema (
    id INT AUTO_INCREMENT PRIMARY KEY,
    tipo ENUM('baja_asistencia', 'sistema', 'academica', 'seguridad') NOT NULL,
    titulo VARCHAR(255) NOT NULL,
    descripcion TEXT,
    criterios JSON,
    activa BOOLEAN DEFAULT TRUE,
    ultima_verificacion TIMESTAMP,
    proxima_verificacion TIMESTAMP,
    created_by INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (created_by) REFERENCES profesor(id) ON DELETE CASCADE ON UPDATE CASCADE,
    INDEX idx_activa_proxima (activa, proxima_verificacion),
    INDEX idx_tipo (tipo)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Tabla para registrar la asistencia de alumnos
CREATE TABLE IF NOT EXISTS alumno_asistencia (
    id INT AUTO_INCREMENT PRIMARY KEY,
    asistencia_id INT NOT NULL,
    alumno_id INT NOT NULL,
    estado VARCHAR(20) NOT NULL DEFAULT 'presente',
    hora_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (asistencia_id) REFERENCES asistencia(id) ON DELETE CASCADE,
    FOREIGN KEY (alumno_id) REFERENCES alumno(id) ON DELETE CASCADE,
    UNIQUE KEY unique_asistencia_alumno (asistencia_id, alumno_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Índices adicionales para optimización de consultas frecuentes
CREATE INDEX idx_asistencia_fecha_presente ON asistencia(fecha_asistencia, presente);
CREATE INDEX idx_clase_fecha_hora ON clase(fecha, hora_inicio);
CREATE INDEX idx_alumno_nombre_completo ON alumno(apellido_paterno, apellido_materno, nombre);

-- Índices adicionales para las nuevas tablas
CREATE INDEX idx_logs_usuario_accion_fecha ON logs_auditoria(usuario_id, accion, timestamp);
CREATE INDEX idx_notificaciones_usuario_fecha ON notificaciones(usuario_id, created_at);
CREATE INDEX idx_login_attempts_recientes ON login_attempts(usuario, timestamp);

-- Eliminar columna es_admin si existe (ya no la necesitamos)
ALTER TABLE autenticacion
DROP COLUMN IF EXISTS es_admin;

-- Asegurarnos de que tipo_usuario tenga los valores correctos
UPDATE autenticacion 
SET tipo_usuario = 'admin' 
WHERE usuario = 'admin';

-- Crear tabla alumno_asistencia si no existe
CREATE TABLE IF NOT EXISTS alumno_asistencia (
    id INT AUTO_INCREMENT PRIMARY KEY,
    asistencia_id INT NOT NULL,
    alumno_id INT NOT NULL,
    estado VARCHAR(20) NOT NULL DEFAULT 'presente',
    hora_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (asistencia_id) REFERENCES asistencia(id) ON DELETE CASCADE,
    FOREIGN KEY (alumno_id) REFERENCES alumno(id) ON DELETE CASCADE,
    UNIQUE KEY unique_asistencia_alumno (asistencia_id, alumno_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

COMMIT; 