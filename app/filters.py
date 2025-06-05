from datetime import datetime, time

def format_time(value):
    """Formatea un objeto time o datetime para mostrar solo la hora"""
    if isinstance(value, time):
        return value.strftime('%H:%M')
    elif isinstance(value, datetime):
        return value.strftime('%H:%M')
    elif isinstance(value, str):
        try:
            # Intentar parsear la cadena como hora
            t = datetime.strptime(value, '%H:%M:%S').time()
            return t.strftime('%H:%M')
        except ValueError:
            return value
    return str(value)

def format_date(value):
    """Formatea una fecha en formato dd/mm/yyyy"""
    if isinstance(value, datetime):
        return value.strftime('%d/%m/%Y')
    return str(value)

def format_datetime(value):
    """Formatea una fecha y hora en formato dd/mm/yyyy HH:MM"""
    if isinstance(value, datetime):
        return value.strftime('%d/%m/%Y %H:%M')
    elif value is None:
        return ''
    return str(value)

def datetime_filter(value):
    """Filtro general para formatear fechas y horas"""
    if isinstance(value, datetime):
        return value.strftime('%d/%m/%Y %H:%M')
    elif value is None:
        return ''
    try:
        if isinstance(value, str):
            dt = datetime.fromisoformat(value)
            return dt.strftime('%d/%m/%Y %H:%M')
    except ValueError:
        pass
    return str(value) 