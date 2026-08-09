"""
Plugin de ejemplo para JARVIS.
Muestra cómo crear un plugin personalizado.
"""
from jarvis_local.plugins import ToolPlugin


class HelloPlugin(ToolPlugin):
    """Ejemplo de plugin que saluda al usuario."""

    name = "hello_plugin"
    description = "Saluda al usuario desde un plugin"
    parameters = {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Nombre del usuario"
            }
        },
        "required": ["name"]
    }

    def execute(self, name: str = "Usuario") -> str:
        return f"¡Hola {name}! Este saludo viene desde un plugin de JARVIS."
