# API de Herramientas de JARVIS

## Índice de Herramientas

### Herramientas de Sistema

| Herramienta | Descripción | Parámetros |
|-------------|-------------|------------|
| `estado_del_sistema` | Estado de CPU, RAM, disco, batería | Ninguno |
| `controlar_volumen` | Control de volumen | `accion`: subir/bajar/silenciar/activar/nivel, `nivel`: 0-100 |
| `controlar_musica` | Control multimedia | `accion`: pausar/siguiente/anterior |
| `energia_del_equipo` | Gestión de energía | `accion`: bloquear/apagar/reiniciar/suspender/cancelar |

### Herramientas de Archivos

| Herramienta | Descripción | Parámetros |
|-------------|-------------|------------|
| `listar_archivos` | Lista archivos de un directorio | `path`: ruta del directorio |
| `buscar_archivos` | Busca archivos por nombre | `name`: nombre, `path`: directorio |
| `crear_archivo` | Crea un archivo | `path`: ruta, `content`: contenido |
| `crear_carpeta` | Crea una carpeta | `path`: ruta |
| `copiar_archivo` | Copia un archivo | `src`: origen, `dst`: destino |
| `mover_archivo` | Mueve un archivo | `src`: origen, `dst`: destino |
| `renombrar` | Renombra un archivo | `path`: ruta, `new_name`: nuevo nombre |
| `borrar_archivo` | Elimina un archivo (requiere confirmación) | `path`: ruta |

### Herramientas de Aplicaciones

| Herramienta | Descripción | Parámetros |
|-------------|-------------|------------|
| `abrir_aplicacion` | Abre una aplicación | `app`: nombre de la app |
| `cerrar_aplicacion` | Cierra una aplicación | `app`: nombre de la app |
| `cerrar_todas_las_apps` | Cierra todas las apps | Ninguno |
| `listar_aplicaciones` | Lista apps disponibles | Ninguno |

### Herramientas Web

| Herramienta | Descripción | Parámetros |
|-------------|-------------|------------|
| `abrir_sitio_web` | Abre un sitio web | `site`: URL o nombre |
| `buscar_en_google` | Busca en Google | `query`: búsqueda |
| `reproducir_youtube` | Busca en YouTube | `query`: búsqueda |
| `clima` | Consulta el clima | `city`: ciudad |
| `ubicar_lugar` | Abre lugar en Maps | `place`: lugar |
| `wikipedia` | Resumen de Wikipedia | `topic`: tema |
| `noticias` | Titulares del día | Ninguno |

### Herramientas de Comunicación

| Herramienta | Descripción | Parámetros |
|-------------|-------------|------------|
| `enviar_correo` | Envía un email (requiere confirmación) | `to`, `subject`, `body` |
| `enviar_whatsapp` | Abre WhatsApp con mensaje | `to`, `message` |

### Herramientas de Información

| Herramienta | Descripción | Parámetros |
|-------------|-------------|------------|
| `calcular` | Calcula expresiones | `expression`: expresión matemática |
| `contar_chiste` | Cuenta un chiste | Ninguno |
| `obtener_ip` | Muestra tu IP | Ninguno |
| `buscar_empleo` | Busca ofertas de empleo | `puesto`, `ciudad` |

### Herramientas de Voz

| Herramienta | Descripción | Parámetros |
|-------------|-------------|------------|
| `crear_recordatorio` | Crea un recordatorio | `text`, `minutes`, `hora` |
| `listar_recordatorios` | Lista recordatorios | Ninguno |
| `cancelar_recordatorio` | Cancela recordatorio | `which`: cuál cancelar |

## Niveles de Riesgo

| Nivel | Descripción | Ejemplo |
|-------|-------------|---------|
| `NONE` | Sin riesgo | Consultar hora |
| `READ` | Solo lectura | Listar archivos |
| `CREATE` | Crear/Modificar | Crear archivo |
| `EXECUTE` | Ejecutar | Abrir app, navegar |
| `DELETE` | Eliminar | Borrar archivo |
| `CRITICAL` | Crítico | Apagar equipo |

## Ejemplo de Uso

```python
from jarvis_local.agent.registry import execute

# Ejecutar una herramienta
result, needs_confirm = execute("clima", {"city": "Bogotá"})
print(result)  # "El clima en Bogotá es..."

# Ejecutar acción que requiere confirmación
result, needs_confirm = execute("borrar_archivo", {"path": "/tmp/test.txt"})
if needs_confirm:
    print("Requiere confirmación del usuario")
```
