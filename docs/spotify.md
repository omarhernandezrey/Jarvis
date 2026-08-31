# Spotify

JARVIS reproduce cualquier canción que le pidas usando tu propia cuenta de
Spotify (API oficial). Requiere **Spotify Premium**: la API no permite
controlar la reproducción remota con cuentas gratuitas.

Hay dos piezas que configurar una sola vez:

1. **Un dispositivo Spotify Connect activo** — algo que reciba la orden de
   "reproducir" y realmente suene. La app oficial de Spotify (celular,
   escritorio o este mismo PC) sirve para esto.
2. **Una app en el panel de desarrolladores de Spotify** — le da a JARVIS
   permiso para buscar canciones y decirle a ese dispositivo qué reproducir,
   vía la API oficial.

> **Nota sobre `spotifyd`** (reproductor sin interfaz gráfica): lo probamos
> primero porque no requiere tener ninguna app abierta, pero en la práctica
> falla al descifrar el audio (`Symphonia Decoder Error`, `audio key error`,
> `400 Bad Request`) por un bug **abierto y sin resolver** en `librespot`, la
> librería de la que depende (ver
> [spotifyd#1385](https://github.com/Spotifyd/spotifyd/issues/1385)). Spotify
> parece estar restringiendo la obtención de llaves de descifrado a clientes
> no oficiales. Por eso la app oficial (snap) es la opción que de verdad
> funciona hoy. Si el bug se resuelve río arriba, `spotifyd` se puede retomar
> sin tocar el código de JARVIS (el device se detecta automáticamente).

---

## 1. Instalar la app oficial de Spotify

```bash
sudo snap install spotify
```

Ábrela una vez e inicia sesión con tu cuenta (para que la sesión quede
recordada). Después de esto **no hace falta dejarla abierta ni volver a
loguearse**: si le pides una canción a JARVIS y Spotify no está corriendo, la
abre solo, espera a que se registre como dispositivo y reproduce ahí (tarda
unos 8-10 segundos la primera vez que la abre).

---

## 2. Crear la app de Spotify (para que JARVIS busque y controle la reproducción)

1. Entra a <https://developer.spotify.com/dashboard> con tu cuenta de Spotify.
2. "Create app" → nombre y descripción libres (ej. "Jarvis Local").
3. En **Redirect URIs** agrega exactamente: `http://127.0.0.1:8888/callback`
4. Guarda. Entra a "Settings" de la app recién creada y copia **Client ID** y
   **Client Secret**.
5. Pégalos en `secrets.yaml` (en la raíz del proyecto, ya está en
   `.gitignore`):

   ```yaml
   spotify:
     client_id: "tu-client-id"
     client_secret: "tu-client-secret"
     redirect_uri: "http://127.0.0.1:8888/callback"
   ```

---

## 3. Usar

Con `secrets.yaml` configurado, solo pide una canción (no hace falta abrir
Spotify primero, JARVIS lo hace si no está corriendo):

> "pon bohemian rhapsody"
> "reproduce algo de bad bunny"
> "quiero escuchar imagine dragons"

La primera vez que JARVIS llame a la API de Spotify se abrirá el navegador
para que autorices la app (una sola vez; el token queda cacheado en
`data/.spotify_cache`, con refresco automático después).

**Pausar / siguiente / anterior** ya funcionan con los comandos de música
existentes de JARVIS (`controlar_musica` / "pausa", "siguiente cancion"): usan
`playerctl`, que detecta la app de Spotify automáticamente vía MPRIS.

## Solución de problemas

| Síntoma | Causa probable |
|---|---|
| "Spotify no esta configurado" | Falta `secrets.yaml` con `client_id`/`client_secret` |
| "Falta instalar la libreria de Spotify" | `pip install spotipy` en el venv del proyecto |
| "No pude abrir Spotify en este equipo" | La app no está instalada (`sudo snap install spotify`), o tardó más de 15s en registrarse — pídele la canción de nuevo |
| "Esta funcion requiere una cuenta Premium" | La API de Spotify no permite reproducción remota en cuentas gratuitas |
