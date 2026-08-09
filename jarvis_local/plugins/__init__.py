"""
JARVIS Local - Sistema de Plugins
Permite añadir herramientas sin modificar el código fuente.
"""
import importlib.util
from pathlib import Path

from jarvis_local.logging_config import get_logger

logger = get_logger("plugins")

PLUGINS_DIR = Path(__file__).parent


class ToolPlugin:
    """Interfaz base para plugins de herramientas."""

    name: str = ""
    description: str = ""
    parameters: dict = {}

    def execute(self, **kwargs) -> str:
        """Ejecuta la herramienta. Debe ser implementado por el plugin."""
        raise NotImplementedError


class PluginManager:
    """Gestiona la carga de plugins."""

    _instance = None
    _plugins: dict[str, ToolPlugin] = {}

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
            cls._instance.load_plugins()
        return cls._instance

    def load_plugins(self):
        """Carga todos los plugins del directorio plugins/."""
        if not PLUGINS_DIR.exists():
            return

        for file in PLUGINS_DIR.glob("*.py"):
            if file.name.startswith("_"):
                continue
            try:
                self._load_plugin(file)
            except Exception as e:
                logger.error(f"Error cargando plugin {file.name}: {e}")

    def _load_plugin(self, file: Path):
        """Carga un plugin individual."""
        spec = importlib.util.spec_from_file_location(file.stem, file)
        if spec is None or spec.loader is None:
            return

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # Buscar clases que hereden de ToolPlugin
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if (isinstance(attr, type) and
                issubclass(attr, ToolPlugin) and
                attr is not ToolPlugin and
                attr.name):
                plugin = attr()
                self._plugins[plugin.name] = plugin
                logger.info(f"Plugin cargado: {plugin.name}")

    def get_plugin(self, name: str) -> ToolPlugin | None:
        """Obtiene un plugin por nombre."""
        return self._plugins.get(name)

    def list_plugins(self) -> list[str]:
        """Lista los nombres de los plugins cargados."""
        return list(self._plugins.keys())


def get_plugin_manager() -> PluginManager:
    """Obtiene la instancia del gestor de plugins."""
    return PluginManager.get_instance()
