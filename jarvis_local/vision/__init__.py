"""
JARVIS Local - Módulo de Visión
Captura y análisis de pantalla.
"""
from pathlib import Path

from jarvis_local.logging_config import get_logger

logger = get_logger("vision")


def capture_screenshot(name: str = "screenshot") -> str | None:
    """Captura una screenshot y la guarda."""
    try:
        from PIL import ImageGrab
        img = ImageGrab.grab()
        save_path = Path.home() / "Pictures" / f"{name}.png"
        save_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(save_path)
        logger.info(f"Screenshot guardada: {save_path}")
        return str(save_path)
    except ImportError:
        logger.error("Pillow no instalado. Ejecute: pip install pillow")
        return None
    except Exception as e:
        logger.error(f"Error capturando screenshot: {e}")
        return None


def describe_screen() -> str:
    """Describe el contenido de la pantalla (requiere OCR)."""
    try:
        import pytesseract
        from PIL import ImageGrab
        img = ImageGrab.grab()
        text = pytesseract.image_to_string(img, lang='spa')
        if text.strip():
            return f"Texto detectado en pantalla: {text[:500]}"
        return "No se detectó texto en la pantalla."
    except ImportError:
        return "OCR no disponible. Instale pytesseract: pip install pytesseract"
    except Exception as e:
        return f"Error analizando pantalla: {e}"


def vision_available() -> bool:
    """Verifica si las herramientas de visión están disponibles."""
    try:
        from PIL import ImageGrab  # noqa: F401
        return True
    except ImportError:
        return False
