"""Persistencia local (SQLite) de los remates."""
import json
import os
import re
import sqlite3
from datetime import date, datetime

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUTA_DB = os.path.join(RAIZ, "datos", "remates.db")
FOTOS = os.path.join(RAIZ, "datos", "fotos")

ESQUEMA = """
CREATE TABLE IF NOT EXISTS remates (
    codigo       TEXT PRIMARY KEY,
    categoria    TEXT NOT NULL,
    subtipo      TEXT NOT NULL,
    tipo         TEXT,
    fecha        TEXT,
    fecha_txt    TEXT,
    provincia    TEXT,
    canton       TEXT,
    bienes       TEXT,
    senalamiento TEXT,
    avaluo       REAL,
    avaluo_calc  REAL,
    pct          INTEGER,
    primera_vez  TEXT,
    ultima_vez   TEXT,
    activo       INTEGER DEFAULT 1,
    nuevo        INTEGER DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_remates_fecha ON remates(fecha);
CREATE INDEX IF NOT EXISTS idx_remates_cat ON remates(categoria, subtipo);
CREATE INDEX IF NOT EXISTS idx_remates_prov ON remates(provincia);

CREATE TABLE IF NOT EXISTS detalles (
    codigo       TEXT PRIMARY KEY,
    descripcion  TEXT,
    campos_json  TEXT,
    foto_url     TEXT,
    foto_archivo TEXT,
    actualizado  TEXT
);

CREATE TABLE IF NOT EXISTS sincronizaciones (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    inicio       TEXT,
    fin          TEXT,
    nuevos       INTEGER DEFAULT 0,
    actualizados INTEGER DEFAULT 0,
    total        INTEGER DEFAULT 0,
    ok           INTEGER DEFAULT 0,
    error        TEXT
);
"""


def conectar():
    """Abre (y crea si hace falta) la base local y su esquema."""
    os.makedirs(os.path.dirname(RUTA_DB), exist_ok=True)
    con = sqlite3.connect(RUTA_DB, check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.executescript(ESQUEMA)
    return con


def ahora():
    """Fecha y hora actual en formato 'YYYY-MM-DD HH:MM:SS'."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def guardar_filas(con, categoria, subtipo, filas):
    """Inserta o actualiza las filas de un subtipo; devuelve (nuevos, actualizados).

    Solo se guardan remates vigentes: si la fecha ya paso se descarta la fila
    (asi nunca entran remates historicos).
    """
    nuevos = actualizados = 0
    hoy = date.today().isoformat()
    cur = con.cursor()
    for f in filas:
        if not f.get("fecha") or f["fecha"] < hoy:
            continue
        existe = cur.execute("SELECT 1 FROM remates WHERE codigo=?", (f["codigo"],)).fetchone()
        if existe:
            cur.execute("""
                UPDATE remates SET categoria=?, subtipo=?, tipo=?, fecha=?, fecha_txt=?,
                    provincia=?, canton=?, bienes=?, senalamiento=?, avaluo=?, avaluo_calc=?,
                    pct=?, ultima_vez=?, activo=1
                WHERE codigo=?""", (
                categoria, subtipo, f["tipo"], f["fecha"], f["fecha_txt"], f["provincia"],
                f["canton"], f["bienes"], f["senalamiento"], f["avaluo"], f["avaluo_calc"],
                f["pct"], ahora(), f["codigo"]))
            actualizados += 1
        else:
            cur.execute("""
                INSERT INTO remates (codigo, categoria, subtipo, tipo, fecha, fecha_txt,
                    provincia, canton, bienes, senalamiento, avaluo, avaluo_calc, pct,
                    primera_vez, ultima_vez, activo, nuevo)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1,1)""", (
                f["codigo"], categoria, subtipo, f["tipo"], f["fecha"], f["fecha_txt"],
                f["provincia"], f["canton"], f["bienes"], f["senalamiento"], f["avaluo"],
                f["avaluo_calc"], f["pct"], ahora(), ahora()))
            nuevos += 1
    con.commit()
    return nuevos, actualizados


def purgar_vencidos(con, hoy=None):
    """Borra de la base los remates vencidos (y su foto): solo quedan los vigentes."""
    hoy = hoy or date.today().isoformat()
    vencidos = [r["codigo"] for r in con.execute(
        "SELECT codigo FROM remates WHERE fecha IS NOT NULL AND fecha < ?", (hoy,))]
    if not vencidos:
        return []
    con.execute("DELETE FROM detalles WHERE codigo IN (%s)" % ",".join("?" * len(vencidos)), vencidos)
    con.execute("DELETE FROM remates WHERE codigo IN (%s)" % ",".join("?" * len(vencidos)), vencidos)
    con.commit()
    # elimina tambien la foto guardada de cada remate que sale de la lista
    for codigo in vencidos:
        ruta = os.path.join(FOTOS, re.sub(r"[^A-Za-z0-9_-]", "_", codigo) + ".jpg")
        if os.path.exists(ruta):
            try:
                os.remove(ruta)
            except OSError:
                pass
    return vencidos


def resumen(con):
    """Devuelve totales, categorias, provincias y la ultima sincronizacion."""
    total = con.execute("SELECT COUNT(*) c FROM remates").fetchone()["c"]
    activos = con.execute("SELECT COUNT(*) c FROM remates WHERE activo=1").fetchone()["c"]
    nuevos = con.execute("SELECT COUNT(*) c FROM remates WHERE nuevo=1 AND activo=1").fetchone()["c"]
    ult = con.execute("SELECT * FROM sincronizaciones WHERE ok=1 ORDER BY id DESC LIMIT 1").fetchone()
    cats = [dict(r) for r in con.execute(
        "SELECT categoria, subtipo, COUNT(*) n FROM remates WHERE activo=1 GROUP BY categoria, subtipo ORDER BY categoria, subtipo")]
    provs = [r["provincia"] for r in con.execute(
        "SELECT DISTINCT provincia FROM remates WHERE activo=1 AND provincia<>'' ORDER BY provincia")]
    return {
        "total": total, "activos": activos, "nuevos": nuevos,
        "ultima": dict(ult) if ult else None,
        "categorias": cats, "provincias": provs,
    }


def consultar(con, q="", categoria="", subtipo="", provincia="", desde="", hasta="",
              orden="fecha", limite=100, desplazamiento=0):
    """Busca remates vigentes con filtros; devuelve {'total': n, 'filas': [...]}."""
    where, params = ["activo=1"], []
    if q:
        where.append("(codigo LIKE ? OR tipo LIKE ? OR provincia LIKE ? OR canton LIKE ? OR senalamiento LIKE ?)")
        like = f"%{q}%"
        params += [like] * 5
    if categoria:
        where.append("categoria=?")
        params.append(categoria)
    if subtipo:
        where.append("subtipo=?")
        params.append(subtipo)
    if provincia:
        where.append("provincia=?")
        params.append(provincia)
    if desde:
        where.append("fecha>=?")
        params.append(desde)
    if hasta:
        where.append("fecha<=?")
        params.append(hasta)
    sql_where = ("WHERE " + " AND ".join(where)) if where else ""

    ordenes = {
        "fecha": "fecha ASC, codigo ASC",
        "fecha_desc": "fecha DESC, codigo ASC",
        "avaluo": "avaluo DESC",
        "codigo": "codigo ASC",
    }
    orden_sql = ordenes.get(orden, ordenes["fecha"])
    total = con.execute(f"SELECT COUNT(*) c FROM remates {sql_where}", params).fetchone()["c"]
    filas = con.execute(
        f"SELECT * FROM remates {sql_where} ORDER BY {orden_sql} LIMIT ? OFFSET ?",
        params + [limite, desplazamiento]).fetchall()
    return {"total": total, "filas": [dict(f) for f in filas]}


def obtener(con, codigo):
    """Devuelve un remate por su codigo, o None."""
    r = con.execute("SELECT * FROM remates WHERE codigo=?", (codigo,)).fetchone()
    return dict(r) if r else None


def obtener_detalle(con, codigo):
    """Devuelve la ficha guardada (descripcion, campos y foto) o None."""
    r = con.execute("SELECT * FROM detalles WHERE codigo=?", (codigo,)).fetchone()
    if not r:
        return None
    d = dict(r)
    d["campos"] = json.loads(d.pop("campos_json") or "{}")
    return d


def guardar_detalle(con, codigo, descripcion, campos, foto_url, foto_archivo=None):
    """Guarda (o actualiza) la ficha de un remate en la base local."""
    con.execute("""
        INSERT INTO detalles (codigo, descripcion, campos_json, foto_url, foto_archivo, actualizado)
        VALUES (?,?,?,?,?,?)
        ON CONFLICT(codigo) DO UPDATE SET descripcion=excluded.descripcion,
            campos_json=excluded.campos_json, foto_url=excluded.foto_url,
            foto_archivo=COALESCE(excluded.foto_archivo, detalles.foto_archivo),
            actualizado=excluded.actualizado""",
        (codigo, descripcion, json.dumps(campos, ensure_ascii=False), foto_url,
         foto_archivo, ahora()))
    con.commit()


def marcar_vistos(con):
    """Quita la marca de 'nuevo' a todos los remates (al abrir la app)."""
    con.execute("UPDATE remates SET nuevo=0 WHERE nuevo=1")
    con.commit()


def registrar_sync(con, inicio, fin, nuevos, actualizados, total, ok, error=None):
    """Anota una sincronizacion en el historial."""
    con.execute("""INSERT INTO sincronizaciones (inicio, fin, nuevos, actualizados, total, ok, error)
                   VALUES (?,?,?,?,?,?,?)""",
                (inicio, fin, nuevos, actualizados, total, 1 if ok else 0, error))
    con.commit()
