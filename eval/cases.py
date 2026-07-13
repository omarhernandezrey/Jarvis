"""
Casos de evaluacion del enrutamiento de intencion.

Cada caso: (entrada, herramienta_esperada, categoria)

Valores especiales de herramienta_esperada:
  None       -> ninguna accion: debe conversar/responder honestamente, NO alucinar
  "CLARIFY"  -> ambiguo: debe pedir aclaracion, no adivinar
  "a|b"      -> cualquiera de esas herramientas es aceptable

Estos casos son el contrato del router. Si un cambio los rompe, el build falla.
"""

# --- A. Comandos directos simples ---
DIRECTOS = [
    ("abre Chrome", "abrir_aplicacion"),
    ("abre WhatsApp", "abrir_aplicacion"),
    ("que hora es", None),                      # respuesta instantanea, sin tool
    ("estado del sistema", "estado_del_sistema"),
    ("cuentame un chiste", "contar_chiste"),
    ("cual es mi ip", "mi_direccion_ip"),
    ("clima en Bogota", "clima"),
    ("toma una captura de pantalla", "captura_de_pantalla"),
]

# --- B. Coloquiales / espanol natural ---
COLOQUIALES = [
    ("oye abreme el navegador", "abrir_aplicacion|abrir_sitio_web"),
    ("necesito revisar mis correos", "abrir_aplicacion|abrir_sitio_web"),
    ("hazme el favor y abre el whatsapp", "abrir_aplicacion"),
    ("como anda la maquina?", "estado_del_sistema"),
    ("que tal anda mi maquina de recursos", "estado_del_sistema"),
    ("se me antoja escuchar algo de musica", "reproducir_musica_local|reproducir_en_youtube"),
    ("ando aburrido, dime algo divertido", "contar_chiste"),
    ("necesito saber si va a llover por alla en Cartagena", "clima"),
    ("me consigues unas vacantes de programador por Medellin", "buscar_empleo"),
    ("estoy buscando pega de disenador", "buscar_empleo"),
    ("necesito la pagina de github abierta", "abrir_sitio_web"),
    # "recordar" (memoria permanente) y "tomar_nota" (archivo de notas) son
    # ambas respuestas razonables a "apuntame esto": el usuario queda servido
    # con cualquiera. No es un fallo de razonamiento.
    ("apuntame que tengo que llamar al banco", "tomar_nota|recordar"),
    ("mi pc esta lentisimo, revisa", "estado_del_sistema"),
    ("quien diablos fue Simon Bolivar", "wikipedia"),
    ("echale un ojo a las noticias", "noticias"),
]

# --- C. Ambiguos: deben pedir aclaracion, no adivinar ---
AMBIGUOS = [
    ("abre eso", "CLARIFY"),
    ("hazlo", "CLARIFY"),
    ("busca", "CLARIFY"),
    ("necesito ayuda con algo", "CLARIFY"),
]

# --- D. Encadenados / multi-paso ---
ENCADENADOS = [
    ("dime el clima de Cali y despues abre Chrome", "clima+abrir_aplicacion"),
    ("busca trabajo de python en Bogota y abre la primera oferta",
     "buscar_empleo+abrir_oferta_empleo"),
]

# --- E. Negacion (no debe ejecutar lo negado) ---
NEGACION = [
    ("no abras Chrome", None),
    ("no me cuentes chistes, mejor dime el clima de Cali", "clima"),
    ("no borres nada, solo lista los archivos de Documentos", "listar_archivos"),
]

# --- F. Fuera de alcance: responder honestamente, NO alucinar ejecucion ---
FUERA_DE_ALCANCE = [
    ("pideme una pizza", None),
    ("llama a mi mama por telefono", None),
    ("de que color es el cielo", None),
    ("que opinas del futbol colombiano", None),
    ("imprime este documento en la impresora", None),
]

# --- G. Consistencia: 5+ variantes de la misma intencion ---
VARIANTES_ABRIR_APP = [
    ("abre chrome", "abrir_aplicacion"),
    ("abreme chrome", "abrir_aplicacion"),
    ("lanza chrome", "abrir_aplicacion"),
    ("inicia el chrome", "abrir_aplicacion"),
    ("podrias abrir chrome?", "abrir_aplicacion"),
    ("necesito chrome abierto", "abrir_aplicacion"),
]

VARIANTES_CLIMA = [
    ("clima en Medellin", "clima"),
    ("como esta el clima en Medellin", "clima"),
    ("va a llover en Medellin?", "clima"),
    ("hace frio en Medellin?", "clima"),
    ("que temperatura hay en Medellin", "clima"),
    ("dime el pronostico de Medellin", "clima"),
]

VARIANTES_SISTEMA = [
    ("estado del sistema", "estado_del_sistema"),
    ("como esta la ram", "estado_del_sistema"),
    ("cuanta memoria estoy usando", "estado_del_sistema"),
    ("como va la bateria", "estado_del_sistema"),
    ("uso de cpu", "estado_del_sistema"),
    ("mi pc esta lento, que lo tiene ocupado", "estado_del_sistema"),
]

VARIANTES_EMPLEO = [
    ("busca trabajo de contador", "buscar_empleo"),
    ("hay vacantes de contador?", "buscar_empleo"),
    ("consigueme empleo de contador", "buscar_empleo"),
    ("quiero ofertas laborales de contador", "buscar_empleo"),
    ("estoy buscando chamba de contador", "buscar_empleo"),
]

# --- H. Contexto conversacional (anafora: se refiere al turno anterior) ---
# (historial, entrada, herramienta_esperada)
CONTEXTUALES = [
    ([("user", "busca trabajo de python en Bogota"),
      ("assistant", "Encontre 5 ofertas: 1. Desarrollador Python...")],
     "abreme la segunda", "abrir_oferta_empleo"),
    ([("user", "abre chrome"),
      ("assistant", "Chrome abierto correctamente.")],
     "ahora abre whatsapp", "abrir_aplicacion"),
    ([("user", "cual es el clima en Cali"),
      ("assistant", "Clima en Cali: soleado, 30 grados.")],
     "y en Bogota?", "clima"),
]


def todos_los_casos() -> list[tuple[str, str | None, str]]:
    """Casos planos (entrada, esperado, categoria), sin los contextuales."""
    grupos = [
        ("directo", DIRECTOS),
        ("coloquial", COLOQUIALES),
        ("ambiguo", AMBIGUOS),
        ("encadenado", ENCADENADOS),
        ("negacion", NEGACION),
        ("fuera_de_alcance", FUERA_DE_ALCANCE),
        ("variante_app", VARIANTES_ABRIR_APP),
        ("variante_clima", VARIANTES_CLIMA),
        ("variante_sistema", VARIANTES_SISTEMA),
        ("variante_empleo", VARIANTES_EMPLEO),
    ]
    out = []
    for cat, casos in grupos:
        for entrada, esperado in casos:
            out.append((entrada, esperado, cat))
    return out


def es_correcto(esperado: str | None, obtenido: list[str],
                pidio_aclaracion: bool = False) -> bool:
    """Compara lo esperado con las herramientas realmente ejecutadas."""
    if esperado == "CLARIFY":
        return pidio_aclaracion and not obtenido

    if esperado is None:
        # No debe ejecutar NINGUNA herramienta (ni alucinar una accion)
        return not obtenido

    if "+" in esperado:  # encadenado: deben estar todas, en orden
        requeridas = esperado.split("+")
        return obtenido[:len(requeridas)] == requeridas

    opciones = esperado.split("|")
    return bool(obtenido) and obtenido[0] in opciones
