# Sistema de Asistencia IDuoc

Sistema de gestión de asistencia para profesores y alumnos de Duoc UC.

## Características

- Gestión de clases, alumnos y profesores
- Registro y control de asistencia
- Panel administrativo
- Interfaz responsiva y moderna
- Autenticación y autorización basada en roles

## Requisitos

- Python 3.8 o superior
- MySQL 8.0 o superior
- pip (gestor de paquetes de Python)

## Instalación

1. Clonar el repositorio:
```bash
git clone https://github.com/tu-usuario/asistencia-iduoc.git
cd asistencia-iduoc
```

2. Crear un entorno virtual:
```bash
python -m venv venv
```

3. Activar el entorno virtual:
- Windows:
```bash
venv\Scripts\activate
```
- Linux/Mac:
```bash
source venv/bin/activate
```

4. Instalar dependencias:
```bash
pip install -r requirements.txt
```

5. Configurar variables de entorno:
Crear un archivo `.env` en la raíz del proyecto con el siguiente contenido:
```
SECRET_KEY=tu_clave_secreta
DB_HOST=localhost
DB_USER=tu_usuario
DB_PASSWORD=tu_contraseña
DB_NAME=asistencia_iduoc
```

6. Inicializar la base de datos:
```bash
flask init-db
```

## Uso

1. Iniciar el servidor de desarrollo:
```bash
flask run
```

2. Acceder a la aplicación:
Abrir un navegador y visitar `http://localhost:5000`

## Estructura del Proyecto

```
asistencia_iduoc/
├── app/
│   ├── __init__.py
│   ├── auth.py
│   ├── db.py
│   ├── main.py
│   ├── api.py
│   └── templates/
│       ├── admin/
│       │   ├── dashboard.html
│       │   ├── clases.html
│       │   ├── alumnos.html
│       │   ├── profesores.html
│       │   └── asistencia.html
│       └── base_new.html
├── config.py
├── requirements.txt
└── README.md
```

## Contribuir

1. Fork el proyecto
2. Crear una rama para tu feature (`git checkout -b feature/AmazingFeature`)
3. Commit tus cambios (`git commit -m 'Add some AmazingFeature'`)
4. Push a la rama (`git push origin feature/AmazingFeature`)
5. Abrir un Pull Request

## Licencia

Distribuido bajo la Licencia MIT. Ver `LICENSE` para más información.

## Contacto

Tu Nombre - [@tu_twitter](https://twitter.com/tu_twitter) - email@example.com

Link del Proyecto: [https://github.com/tu-usuario/asistencia-iduoc](https://github.com/tu-usuario/asistencia-iduoc) 