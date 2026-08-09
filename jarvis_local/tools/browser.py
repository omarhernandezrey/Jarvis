"""
JARVIS Local - Navegador automatizado con Selenium (Fase 5)
Chrome controlado por JARVIS: navegar, buscar y mostrar ofertas de empleo.
El chromedriver lo gestiona Selenium Manager automaticamente.
"""
import atexit
import contextlib

from jarvis_local.safety.policy import ActionPlan, ActionStatus, RiskLevel


class BrowserManager:
    """Gestiona el driver de Chrome de forma segura."""

    _instance = None
    _driver = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def _cleanup(cls):
        """Cierra el driver al terminar el proceso."""
        if cls._driver is not None:
            with contextlib.suppress(Exception):
                cls._driver.quit()
            cls._driver = None

    def get_driver(self):
        """Devuelve el Chrome controlado (lo crea si no existe o se cerro)."""
        if BrowserManager._driver is not None:
            try:
                _ = BrowserManager._driver.current_url  # sigue vivo?
                return BrowserManager._driver
            except Exception:
                BrowserManager._driver = None
        from selenium import webdriver
        opts = webdriver.ChromeOptions()
        opts.add_argument("--start-maximized")
        opts.add_argument("--disable-blink-features=AutomationControlled")
        # No usar excludeSwitches: impide que Chrome 150+ arranque (session not created)
        opts.add_experimental_option("detach", True)  # la ventana queda abierta
        BrowserManager._driver = webdriver.Chrome(options=opts)
        return BrowserManager._driver

    def close(self):
        """Cierra el Chrome controlado."""
        if BrowserManager._driver is not None:
            with contextlib.suppress(Exception):
                BrowserManager._driver.quit()
            BrowserManager._driver = None


# Registrar cleanup al terminar el proceso
atexit.register(BrowserManager._cleanup)


def browser_available() -> bool:
    try:
        import selenium  # noqa: F401
        return True
    except ImportError:
        return False


def navigate(url: str) -> ActionPlan:
    """Navega a una URL en el Chrome controlado por JARVIS."""
    plan = ActionPlan(action="navegar", params={"url": url},
                      risk=RiskLevel.EXECUTE, reason=f"Navegar a {url}")
    if not browser_available():
        plan.status = ActionStatus.ERROR
        plan.result = "Selenium no esta instalado, senor. Ejecute: pip install selenium"
        return plan
    try:
        manager = BrowserManager.get_instance()
        d = manager.get_driver()
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        d.get(url)
        plan.result = f"Navegando a {url} en el navegador controlado, senor."
        plan.status = ActionStatus.EXECUTED
    except Exception as e:
        plan.status = ActionStatus.ERROR
        plan.error = str(e)
        plan.result = f"No pude controlar el navegador: {e}"
    return plan


def show_jobs_in_browser(puesto: str = "", ciudad: str = "") -> ActionPlan:
    """Abre la busqueda en los tres portales, cada uno en su pestana.

    En El Empleo la busqueda solo funciona con su propio JavaScript, asi que
    verla en el navegador es la unica forma de tener sus resultados filtrados.
    """
    from jarvis_local.tools.jobs import last_query, portal_urls
    if not puesto:
        puesto, ciudad = last_query()
    if not puesto:
        plan = navigate("https://co.computrabajo.com")
        if plan.status == ActionStatus.EXECUTED:
            plan.result = ("No hay una busqueda reciente, senor. Le abro "
                           "Computrabajo; diga 'busca trabajo de <cargo> en "
                           "<ciudad>' para una busqueda concreta.")
        return plan

    urls = portal_urls(puesto, ciudad)
    plan = ActionPlan(action="mostrar_ofertas",
                      params={"puesto": puesto, "ciudad": ciudad},
                      risk=RiskLevel.EXECUTE,
                      reason=f"Mostrar ofertas de {puesto} en los portales")
    if not browser_available():
        plan.status = ActionStatus.ERROR
        plan.result = "Selenium no esta instalado, senor. Ejecute: pip install selenium"
        return plan
    try:
        manager = BrowserManager.get_instance()
        d = manager.get_driver()
        primero = True
        for _portal, url in urls.items():
            if primero:
                d.get(url)
                primero = False
            else:
                d.switch_to.new_window("tab")
                d.get(url)
        donde = f" en {ciudad}" if ciudad else ""
        plan.result = (f"Le abro las ofertas de {puesto}{donde} en "
                       f"{', '.join(urls)}, senor. Una pestana por portal.")
        plan.status = ActionStatus.EXECUTED
    except Exception as e:
        plan.status = ActionStatus.ERROR
        plan.error = str(e)
        plan.result = f"No pude controlar el navegador: {e}"
    return plan


def close_browser() -> ActionPlan:
    """Cierra el Chrome controlado por JARVIS."""
    plan = ActionPlan(action="cerrar_navegador", risk=RiskLevel.EXECUTE,
                      reason="Cerrar navegador automatizado")
    try:
        manager = BrowserManager.get_instance()
        manager.close()
        plan.result = "Navegador automatizado cerrado, senor."
        plan.status = ActionStatus.EXECUTED
    except Exception:
        plan.result = "El navegador ya estaba cerrado, senor."
        plan.status = ActionStatus.EXECUTED
    return plan
