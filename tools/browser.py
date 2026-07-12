"""
JARVIS Local - Navegador automatizado con Selenium (Fase 5)
Chrome controlado por JARVIS: navegar, buscar y mostrar ofertas de empleo.
El chromedriver lo gestiona Selenium Manager automaticamente.
"""
from jarvis_local.safety.policy import ActionPlan, RiskLevel, ActionStatus

_driver = None


def _get_driver():
    """Devuelve el Chrome controlado (lo crea si no existe o se cerro)."""
    global _driver
    if _driver is not None:
        try:
            _ = _driver.current_url  # sigue vivo?
            return _driver
        except Exception:
            _driver = None
    from selenium import webdriver
    opts = webdriver.ChromeOptions()
    opts.add_argument("--start-maximized")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    # No usar excludeSwitches: impide que Chrome 150+ arranque (session not created)
    opts.add_experimental_option("detach", True)  # la ventana queda abierta
    _driver = webdriver.Chrome(options=opts)
    return _driver


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
        d = _get_driver()
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
    from jarvis_local.tools.jobs import portal_urls, last_query
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
        d = _get_driver()
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
    global _driver
    plan = ActionPlan(action="cerrar_navegador", risk=RiskLevel.EXECUTE,
                      reason="Cerrar navegador automatizado")
    try:
        if _driver is not None:
            _driver.quit()
        plan.result = "Navegador automatizado cerrado, senor."
        plan.status = ActionStatus.EXECUTED
    except Exception:
        plan.result = "El navegador ya estaba cerrado, senor."
        plan.status = ActionStatus.EXECUTED
    finally:
        _driver = None
    return plan
