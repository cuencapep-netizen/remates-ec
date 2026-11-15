"""Lanzador de la app de escritorio (servidor local + ventana tipo app)."""
import os
import subprocess
import sys
import threading
import time
import traceback
import webbrowser

from . import datos, sync
from .servidor import CON, crear_servidor

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PERFIL = os.path.join(RAIZ, "datos", "perfil-navegador")

# Navegadores que se pueden abrir en modo "app" (sin barra de direcciones)
NAVEGADORES = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
]


def abrir_ventana(url):
    """Abre la interfaz en una ventana de navegador sin barras; si no hay, usa el navegador por defecto."""
    for exe in NAVEGADORES:
        if os.path.isfile(exe):
            try:
                subprocess.Popen([
                    exe, f"--app={url}", "--window-size=1360,900",
                    f"--user-data-dir={PERFIL}", "--no-first-run",
                    "--no-default-browser-check", "--disable-features=Translate",
                ])
                return True
            except Exception:
                continue
    webbrowser.open(url)
    return False


def main():
    """Levanta el servidor, abre la ventana y mantiene la app viva."""
    servidor = crear_servidor(8765)
    puerto = servidor.server_address[1]
    url = f"http://127.0.0.1:{puerto}/"
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    print(f"Remates EC corriendo en {url}")

    # Primera ejecucion: si la base esta vacia, sincroniza en segundo plano
    datos.purgar_vencidos(CON)
    if datos.resumen(CON)["total"] == 0:
        threading.Thread(target=sync.sincronizar, args=(CON,), daemon=True).start()

    abrir_ventana(url)
    try:
        while True:
            time.sleep(3600)  # cada hora revisa remates vencidos
            datos.purgar_vencidos(CON)
    except KeyboardInterrupt:
        print("Cerrando…")


def _error_fatal(e):
    """Guarda el error en datos\\error.log y lo muestra en un cuadro de dialogo.

    Necesario cuando la app va empaquetada sin consola: si no, el fallo seria invisible.
    """
    import ctypes
    detalle = traceback.format_exc()
    try:
        os.makedirs(os.path.join(RAIZ, "datos"), exist_ok=True)
        with open(os.path.join(RAIZ, "datos", "error.log"), "a", encoding="utf-8") as f:
            f.write(f"\n=== {time.strftime('%Y-%m-%d %H:%M:%S')} ===\n{detalle}")
    except Exception:
        pass
    try:
        ctypes.windll.user32.MessageBoxW(None, detalle[-900:], "Remates EC - error", 0x10)
    except Exception:
        pass


if __name__ == "__main__":
    sys.path.insert(0, RAIZ)
    try:
        main()
    except Exception as error:  # sin consola, cualquier fallo se muestra en un dialogo
        _error_fatal(error)
