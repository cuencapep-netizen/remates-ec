"""Servidor local (solo stdlib) que sirve la interfaz y la API de la app.

La ventana de escritorio es un navegador en modo "app" apuntando a este servidor.
"""
import io
import json
import os
import re
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import datos, fuentes, sync

RAIZ = os.path.dirname(os.path.abspath(__file__))
WEB = os.path.join(RAIZ, "web")
FOTOS = datos.FOTOS

CON = datos.conectar()
MIME = {".html": "text/html; charset=utf-8", ".js": "application/javascript; charset=utf-8",
        ".css": "text/css; charset=utf-8", ".png": "image/png", ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg", ".svg": "image/svg+xml", ".ico": "image/x-icon"}


def _json(handler, obj, code=200):
    """Responde JSON con codificacion UTF-8 y sin cache."""
    data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
    handler.send_response(code)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(data)))
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers()
    handler.wfile.write(data)


def _archivo(handler, ruta, mime=None):
    """Sirve un archivo del disco (o 404 si no existe)."""
    if not os.path.isfile(ruta):
        handler.send_error(404)
        return
    with open(ruta, "rb") as f:
        data = f.read()
    handler.send_response(200)
    handler.send_header("Content-Type", mime or MIME.get(os.path.splitext(ruta)[1].lower(), "application/octet-stream"))
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


def _filas_filtradas(qs):
    """Traduce los parametros de la URL a la consulta SQL de la base."""
    return datos.consultar(
        CON,
        q=qs.get("q", [""])[0],
        categoria=qs.get("categoria", [""])[0],
        subtipo=qs.get("subtipo", [""])[0],
        provincia=qs.get("provincia", [""])[0],
        desde=qs.get("desde", [""])[0],
        hasta=qs.get("hasta", [""])[0],
        orden=qs.get("orden", ["fecha"])[0],
        limite=int(qs.get("limite", ["200"])[0]),
        desplazamiento=int(qs.get("offset", ["0"])[0]),
    )


def _foto(codigo, datos_img):
    """Reduce la foto a un JPG ligero (~30-40 KB) y devuelve el nombre del archivo."""
    if not datos_img:
        return None
    os.makedirs(FOTOS, exist_ok=True)
    nombre = re.sub(r"[^A-Za-z0-9_-]", "_", codigo) + ".jpg"
    destino = os.path.join(FOTOS, nombre)
    if os.path.exists(destino):
        return nombre
    try:
        from PIL import Image
        img = Image.open(io.BytesIO(datos_img)).convert("RGB")
        img.thumbnail((480, 480), Image.LANCZOS)
        img.save(destino, "JPEG", quality=65, optimize=True, progressive=True)
    except Exception:
        with open(destino, "wb") as f:
            f.write(datos_img)
    return nombre


class Handler(BaseHTTPRequestHandler):
    """Atiende las rutas de la API y los archivos de la interfaz."""

    server_version = "RematesEC/0.2"

    def log_message(self, fmt, *args):
        """Silencia el log de cada peticion (la app no lo necesita)."""
        pass

    def do_GET(self):
        """Rutas de lectura: estado, listado, ficha, foto y exportaciones."""
        parsed = urllib.parse.urlparse(self.path)
        ruta = urllib.parse.unquote(parsed.path)
        qs = urllib.parse.parse_qs(parsed.query)

        if ruta == "/api/estado":
            datos.purgar_vencidos(CON)
            return _json(self, {"resumen": datos.resumen(CON), "sync": sync.estado()})

        if ruta == "/api/remates":
            return _json(self, _filas_filtradas(qs))

        if ruta.startswith("/api/remate/"):
            codigo = ruta.split("/")[-1]
            return self._detalle(codigo, qs)

        if ruta.startswith("/api/foto/"):
            codigo = ruta.split("/")[-1]
            return self._servir_foto(codigo)

        if ruta == "/api/export.csv":
            return self._csv(qs)
        if ruta == "/api/export.xlsx":
            return self._xlsx(qs)

        if ruta == "/":
            ruta = "/index.html"
        return _archivo(self, os.path.join(WEB, ruta.lstrip("/")))

    def do_POST(self):
        """Rutas de escritura: lanzar sincronizacion y marcar vistos."""
        parsed = urllib.parse.urlparse(self.path)
        largo = int(self.headers.get("Content-Length") or 0)
        if largo:
            self.rfile.read(largo)
        if parsed.path == "/api/sync":
            return _json(self, {"lanzado": sync.lanzar(CON)})
        if parsed.path == "/api/vistos":
            datos.marcar_vistos(CON)
            return _json(self, {"ok": True})
        self.send_error(404)

    # ------------------------------------------------------------------
    def _detalle(self, codigo, qs):
        """Devuelve la ficha del remate; la descarga del portal si no esta en cache."""
        fila = datos.obtener(CON, codigo)
        if not fila:
            return _json(self, {"error": "no existe"}, 404)
        guardado = datos.obtener_detalle(CON, codigo)
        refrescar = qs.get("refresh", ["0"])[0] == "1"
        if guardado and not refrescar:
            return _json(self, {"remate": fila, **guardado})

        try:
            d = fuentes.detalle(fila["categoria"], fila["subtipo"], codigo)
            archivo = _foto(codigo, d.pop("foto_bytes", None))
            datos.guardar_detalle(CON, codigo, d["descripcion"], d["campos"],
                                  d.get("foto_url"), archivo)
            return _json(self, {"remate": fila, **datos.obtener_detalle(CON, codigo)})
        except Exception as e:
            return _json(self, {"error": str(e)}, 500)

    def _servir_foto(self, codigo):
        """Entrega la foto ya reducida; si falta, la descarga y la guarda."""
        det = datos.obtener_detalle(CON, codigo)
        nombre = (det or {}).get("foto_archivo")
        if nombre:
            ruta = os.path.join(FOTOS, nombre)
            if os.path.exists(ruta):
                return _archivo(self, ruta, "image/jpeg")
        fila = datos.obtener(CON, codigo)
        if not fila:
            return self.send_error(404)
        try:
            d = fuentes.detalle(fila["categoria"], fila["subtipo"], codigo)
            nombre = _foto(codigo, d.pop("foto_bytes", None))
            datos.guardar_detalle(CON, codigo, d["descripcion"], d["campos"],
                                  d.get("foto_url"), nombre)
        except Exception:
            return self.send_error(404)
        if not nombre:
            return self.send_error(404)
        return _archivo(self, os.path.join(FOTOS, nombre), "image/jpeg")

    def _csv(self, qs):
        """Exporta el listado filtrado a CSV (separador ';', con BOM para Excel)."""
        import csv
        res = _filas_filtradas(qs)
        buf = io.StringIO()
        w = csv.writer(buf, delimiter=";")
        w.writerow(["Codigo", "Categoria", "Subtipo", "Fecha", "Provincia", "Canton",
                    "Tipo", "Bienes", "Senalamiento", "Avaluo", "Avaluo calculado", "%"])
        for f in res["filas"]:
            w.writerow([f["codigo"], f["categoria"], f["subtipo"], f["fecha"], f["provincia"],
                        f["canton"], f["tipo"], f["bienes"], f["senalamiento"],
                        f["avaluo"], f["avaluo_calc"], f["pct"]])
        data = buf.getvalue().encode("utf-8-sig")
        self.send_response(200)
        self.send_header("Content-Type", "text/csv; charset=utf-8")
        self.send_header("Content-Disposition", 'attachment; filename="remates.csv"')
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _xlsx(self, qs):
        """Exporta el listado filtrado a un libro de Excel (.xlsx)."""
        from openpyxl import Workbook
        res = _filas_filtradas(qs)
        wb = Workbook()
        ws = wb.active
        ws.title = "Remates"
        ws.append(["Codigo", "Categoria", "Subtipo", "Fecha", "Provincia", "Canton",
                   "Tipo", "Bienes", "Senalamiento", "Avaluo", "Avaluo calculado", "%"])
        for f in res["filas"]:
            ws.append([f["codigo"], f["categoria"], f["subtipo"], f["fecha"], f["provincia"],
                       f["canton"], f["tipo"], f["bienes"], f["senalamiento"],
                       f["avaluo"], f["avaluo_calc"], f["pct"]])
        ws.freeze_panes = "A2"
        for i, w in enumerate([16, 11, 20, 12, 16, 18, 22, 8, 20, 14, 16, 6], start=1):
            ws.column_dimensions[chr(64 + i)].width = w
        buf = io.BytesIO()
        wb.save(buf)
        data = buf.getvalue()
        self.send_response(200)
        self.send_header("Content-Type", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        self.send_header("Content-Disposition", 'attachment; filename="remates.xlsx"')
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def crear_servidor(puerto=8765):
    """Crea el servidor en el primer puerto libre a partir del indicado."""
    for p in range(puerto, puerto + 20):
        try:
            return ThreadingHTTPServer(("127.0.0.1", p), Handler)
        except OSError:
            continue
    raise RuntimeError("sin puerto libre")
