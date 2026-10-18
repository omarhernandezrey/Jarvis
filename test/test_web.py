"""
Tests de herramientas web - Fase 4
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jarvis_local.safety.policy import ActionStatus
from jarvis_local.tools import web as web_mod
from jarvis_local.tools.web import (
    _is_safe_url,
    build_url,
    build_youtube_watch_url,
    parse_first_youtube_video,
    youtube_play,
)


def test_build_url_http():
    """URL con http se mantiene."""
    assert build_url("http://example.com") == "http://example.com"


def test_build_url_https():
    """URL con https se mantiene."""
    assert build_url("https://example.com") == "https://example.com"


def test_build_url_sin_esquema():
    """URL sin esquema añade https."""
    assert build_url("example.com") == "https://example.com"


def test_build_url_nombre_sin_dominio():
    """Nombre sin dominio añade https://www..com."""
    assert build_url("google") == "https://www.google.com"


def test_build_url_con_espacios():
    """Nombre con espacios se procesa."""
    assert build_url("mi sitio") == "https://www.misitio.com"


def test_is_safe_url_http():
    """URL http es segura."""
    assert _is_safe_url("http://example.com") is True


def test_is_safe_url_https():
    """URL https es segura."""
    assert _is_safe_url("https://example.com") is True


def test_is_safe_url_javascript():
    """URL javascript no es segura."""
    assert _is_safe_url("javascript:alert(1)") is False


def test_is_safe_url_data():
    """URL data no es segura."""
    assert _is_safe_url("data:text/html,<h1>hola</h1>") is False


def test_is_safe_url_file():
    """URL file no es segura."""
    assert _is_safe_url("file:///etc/passwd") is False


def test_build_url_javascript_blocked():
    """URL javascript se bloquea y devuelve fallback."""
    url = build_url("javascript:alert(1)")
    assert url == "https://www.google.com"


def test_build_url_data_blocked():
    """URL data se bloquea y devuelve fallback."""
    url = build_url("data:text/html,<h1>hola</h1>")
    assert url == "https://www.google.com"


# ── YouTube: reproducir el primer video real, no solo abrir la búsqueda ──
# Regresión: "reproduce X en youtube" abría la página de resultados
# (/results?search_query=...) y el usuario tenía que elegir el video a
# mano — nunca sonaba solo. `parse_first_youtube_video` lee el bloque
# `ytInitialData` que YouTube ya manda embebido en el HTML (lo necesita su
# propio JS) para resolver el primer resultado real, sin API key.

def _yt_initial_data_html(contents: list) -> str:
    """HTML mínimo con el bloque ytInitialData que YouTube embebe de
    verdad, con `contents` como la lista de resultados (orden real)."""
    data = {"contents": {"twoColumnSearchResultsRenderer": {"primaryContents": {
        "sectionListRenderer": {"contents": [{"itemSectionRenderer": {"contents": contents}}]}
    }}}}
    return f"<html><script>var ytInitialData = {json.dumps(data)};</script></html>"


def _video_renderer(video_id: str, title: str) -> dict:
    return {"videoRenderer": {"videoId": video_id, "title": {"runs": [{"text": title}]}}}


def test_parse_first_youtube_video_returns_first_real_result():
    html = _yt_initial_data_html([
        _video_renderer("abc12345678", "AC/DC - Back In Black (Official 4K Video)"),
        _video_renderer("zzz99999999", "AC/DC - Back In Black (Lyrics)"),
    ])
    assert parse_first_youtube_video(html) == ("abc12345678", "AC/DC - Back In Black (Official 4K Video)")


def test_parse_first_youtube_video_skips_non_video_renderers():
    """Un `channelRenderer` (canal) antes del primer video no debe
    confundirse con un resultado reproducible."""
    html = _yt_initial_data_html([
        {"channelRenderer": {"channelId": "UC123", "title": {"simpleText": "AC/DC"}}},
        _video_renderer("abc12345678", "AC/DC - Back In Black (Official 4K Video)"),
    ])
    assert parse_first_youtube_video(html) == ("abc12345678", "AC/DC - Back In Black (Official 4K Video)")


def test_parse_first_youtube_video_no_ytinitialdata_returns_none():
    """YouTube cambió el formato de la página: no inventar un video."""
    assert parse_first_youtube_video("<html>sin datos embebidos</html>") is None


def test_parse_first_youtube_video_malformed_json_returns_none():
    html = "<html><script>var ytInitialData = {esto no es json};</script></html>"
    assert parse_first_youtube_video(html) is None


def test_parse_first_youtube_video_no_video_renderer_returns_none():
    """Resultados reales pero ninguno es un video (solo canales/listas)."""
    html = _yt_initial_data_html([{"channelRenderer": {"channelId": "UC123"}}])
    assert parse_first_youtube_video(html) is None


def test_build_youtube_watch_url():
    assert build_youtube_watch_url("abc12345678") == "https://www.youtube.com/watch?v=abc12345678"


def test_youtube_play_opens_direct_watch_url_when_video_resolved(monkeypatch):
    opened = []
    monkeypatch.setattr(web_mod.webbrowser, "open", lambda url: opened.append(url) or True)
    monkeypatch.setattr(
        web_mod, "_first_youtube_video",
        lambda query: ("abc12345678", "AC/DC - Back In Black (Official 4K Video)"),
    )
    plan = youtube_play("back in black")
    assert plan.status == ActionStatus.EXECUTED
    assert opened == ["https://www.youtube.com/watch?v=abc12345678"]
    assert plan.result == "Reproduciendo 'AC/DC - Back In Black (Official 4K Video)' en YouTube."


def test_youtube_play_falls_back_to_search_when_video_not_resolved(monkeypatch):
    """Red caída o YouTube cambió su HTML: cae a la búsqueda en vez de
    fingir que encontró un video (regla de CLAUDE.md — nunca inventar)."""
    opened = []
    monkeypatch.setattr(web_mod.webbrowser, "open", lambda url: opened.append(url) or True)
    monkeypatch.setattr(web_mod, "_first_youtube_video", lambda query: None)
    plan = youtube_play("una cancion muy rara")
    assert plan.status == ActionStatus.EXECUTED
    assert opened == ["https://www.youtube.com/results?search_query=una+cancion+muy+rara"]
    assert "Seleccione el video" in plan.result


if __name__ == "__main__":
    test_build_url_http()
    test_build_url_https()
    test_build_url_sin_esquema()
    test_build_url_nombre_sin_dominio()
    test_build_url_con_espacios()
    test_is_safe_url_http()
    test_is_safe_url_https()
    test_is_safe_url_javascript()
    test_is_safe_url_data()
    test_is_safe_url_file()
    test_build_url_javascript_blocked()
    test_build_url_data_blocked()
    print("OK: Todos los tests de web pasaron.")
