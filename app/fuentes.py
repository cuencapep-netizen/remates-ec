"""Scraping del portal publico de Remates Judiciales (Ecuador).

Convierte el HTML del portal en datos: categorias (Mueble/Inmueble),
subtipos, filas del listado y la ficha de cada remate.
"""
import re
import unicodedata
from lxml import html as LH

from .jsf import RematesSession, BASE

# Abreviaturas de mes que usa el portal: "nov, 16 2026"
MESES = {
    "ene": 1, "feb": 2, "mar": 3, "abr": 4, "may": 5, "jun": 6,
    "jul": 7, "ago": 8, "sep": 9, "set": 9, "oct": 10, "nov": 11, "dic": 12,
}

# Provincias del Ecuador, para separar provincia y canton del listado
PROVINCIAS = [
    "AZUAY", "BOLIVAR", "CAÑAR", "CARCHI", "COTOPAXI", "CHIMBORAZO", "EL ORO",
    "ESMERALDAS", "GALAPAGOS", "GUAYAS", "IMBABURA", "LOJA", "LOS RIOS",
    "MANABI", "MORONA SANTIAGO", "NAPO", "PASTAZA", "PICHINCHA",
    "SANTO DOMINGO DE LOS TSACHILAS", "TUNGURAHUA", "ZAMORA CHINCHIPE",
    "SUCUMBIOS", "ORELLANA", "SANTA ELENA",
]


def limpiar(s):
    """Quita espacios repetidos y saltos de linea de un texto."""
    return " ".join((s or "").split())


def sin_tildes(s):
    """Devuelve el texto en mayusculas y sin tildes (para comparar)."""
    s = unicodedata.normalize("NFKD", s or "")
    return "".join(c for c in s if not unicodedata.combining(c)).upper()


def fecha_iso(txt):
    """Convierte 'nov, 16 2026' en ('2026-11-16', 'nov, 16 2026')."""
    m = re.search(r"([a-zA-Záéíóú]{3,})\.?,?\s*(\d{1,2})\s+(\d{4})", txt or "")
    if not m:
        return None, None
    mes = MESES.get(sin_tildes(m.group(1))[:3].lower())
    if not mes:
        return None, None
    return f"{m.group(3)}-{mes:02d}-{int(m.group(2)):02d}", limpiar(txt)


def numero(txt):
    """Extrae el primer numero con decimales ('4,620.00' -> 4620.0)."""
    m = re.search(r"-?[\d,]+\.\d+", txt or "")
    if not m:
        return None
    try:
        return float(m.group(0).replace(",", ""))
    except ValueError:
        return None


def porcentaje(txt):
    """Extrae el porcentaje entre parentesis ('(75%)' -> 75)."""
    m = re.search(r"\((\d{1,3})\s*%\)", txt or "")
    return int(m.group(1)) if m else None


def partir_localizacion(td):
    """Separa la celda 'PROVINCIA <br/> CANTON' en (provincia, canton)."""
    provincia, canton = limpiar(td.text_content()), ""
    for br in td.iter("br"):
        canton = limpiar(br.tail)
        break
    if canton:
        provincia = limpiar(td.text)
    # normaliza la provincia (el sitio a veces omite tildes)
    provincia_n = sin_tildes(provincia)
    for p in PROVINCIAS:
        if provincia_n.startswith(sin_tildes(p)):
            provincia = p
            if not canton:
                canton = limpiar(provincia_n[len(sin_tildes(p)):])
            break
    return provincia, canton


def parse_categorias(panel):
    """Lee los enlaces de categoria del panel 'Tipo de Bien' (Mueble, Inmueble)."""
    doc = LH.fromstring(panel)
    return [{"id": a.get("id"), "nombre": limpiar(a.text_content())}
            for a in doc.iter("a")
            if a.get("id") and ":" in a.get("id") and limpiar(a.text_content())
            and "Regresar" not in a.text_content()]


def parse_subtipos(panel):
    """Lee la tabla de subtipos (Vehículo, Urbano...) con su enlace."""
    doc = LH.fromstring(panel)
    subs = []
    for tr in doc.iter("tr"):
        celdas = [limpiar(td.text_content()) for td in tr.iter("td")]
        if len(celdas) >= 2 and celdas[0].isdigit():
            a = next((x for x in tr.iter("a") if x.get("id")), None)
            subs.append({"n": int(celdas[0]), "nombre": celdas[1],
                         "id": a.get("id") if a is not None else None})
    return subs


def parse_filas(panel):
    """Convierte la tabla de resultados en una lista de diccionarios."""
    doc = LH.fromstring(panel)
    tbody = next((t for t in doc.iter("tbody") if t.get("id") == "tablaResultados:tb"), None)
    filas = []
    if tbody is None:
        return filas
    for tr in tbody.iter("tr"):
        tds = [td for td in tr.iter("td")]
        if len(tds) < 10:
            continue
        codigo = limpiar(tds[2].text_content())
        if not codigo.startswith("EC-RJ"):
            continue
        enlace = next((a.get("id") for a in tds[1].iter("a") if a.get("id")), None)
        imagen = next((i.get("src") for i in tds[1].iter("img") if i.get("src")), None)
        provincia, canton = partir_localizacion(tds[4])
        iso, txt = fecha_iso(limpiar(tds[3].text_content()))
        filas.append({
            "codigo": codigo,
            "fecha": iso,
            "fecha_txt": txt,
            "provincia": provincia,
            "canton": canton,
            "tipo": limpiar(tds[5].text_content()),
            "bienes": limpiar(tds[6].text_content()),
            "senalamiento": limpiar(tds[7].text_content()),
            "avaluo": numero(limpiar(tds[8].text_content())),
            "avaluo_calc": numero(limpiar(tds[9].text_content())),
            "pct": porcentaje(limpiar(tds[9].text_content())),
            "enlace": enlace,
            "foto_url": imagen,
        })
    return filas


def paginas_desde(panel):
    """Deduce cuantas paginas tiene el paginador (1 si no aparece)."""
    nums = [int(x) for x in re.findall(r"tablaResultados:down_ds_(\d+)\"", panel)]
    return max(nums) if nums else 1


# ---------------------------------------------------------------- navegacion

def sesion_nueva():
    """Crea una sesion con los terminos aceptados, parada en el buscador."""
    s = RematesSession()
    s.accept_terms()
    return s


def categorias(s):
    """Abre 'Busqueda por Tipo de Bien' y devuelve las dos categorias."""
    _, u = s.click("calendarIconPrincipal11")
    return parse_categorias(u.get("pnlF", ""))


def subtipos_de(s, categoria):
    """Entra a una categoria y devuelve sus subtipos."""
    _, u = s.click("calendarIconPrincipal11")
    cats = parse_categorias(u.get("pnlF", ""))
    cat = next((c for c in cats if c["nombre"].lower() == categoria.lower()), None)
    if not cat:
        raise RuntimeError(f"categoria no encontrada: {categoria}")
    _, u = s.click(cat["id"])
    return parse_subtipos(u.get("pnlF", ""))


def ir_a_subtipo(s, categoria, subtipo):
    """Navega desde el buscador hasta el listado de un subtipo y devuelve el panel."""
    _, u = s.click("calendarIconPrincipal11")
    cats = parse_categorias(u.get("pnlF", ""))
    cat = next((c for c in cats if c["nombre"].lower() == categoria.lower()), None)
    if not cat:
        raise RuntimeError(f"categoria no encontrada: {categoria}")
    _, u = s.click(cat["id"])
    subs = parse_subtipos(u.get("pnlF", ""))
    sub = next((x for x in subs if x["nombre"].lower() == subtipo.lower()), None)
    if not sub:
        raise RuntimeError(f"subtipo no encontrado: {subtipo}")
    _, u = s.click(sub["id"])
    return u.get("pnlF", "")


def pagina(s, n):
    """Pide la pagina n del listado actual (n>1) y devuelve el tbody HTML."""
    if n <= 1:
        return None
    _, u = s.click("tablaResultados:down",
                   extra={"tablaResultados:down:page": str(n)})
    return u.get("tablaResultados:tb", "")


def listar_subtipo(categoria, subtipo, al_progresar=None):
    """Recorre todas las paginas de un subtipo y devuelve (filas, total_paginas)."""
    s = sesion_nueva()
    panel = ir_a_subtipo(s, categoria, subtipo)
    total = paginas_desde(panel)
    filas = parse_filas(panel)
    if al_progresar:
        al_progresar(1, total, len(filas))
    for p in range(2, total + 1):
        frag = pagina(s, p)
        filas.extend(parse_filas(frag))
        if al_progresar:
            al_progresar(p, total, len(filas))
    return filas, total


# ------------------------------------------------------------------- detalle

def _campos_info(doc):
    """Lee los pares etiqueta/valor de la tabla #infoRemate de la ficha."""
    datos = {}
    info = next((t for t in doc.iter("table") if t.get("id") == "infoRemate"), None)
    if info is None:
        return datos
    todos = [limpiar(x.text_content()) for x in info.iter("span") if limpiar(x.text_content())]
    for i, t in enumerate(todos):
        if t.endswith(":") and i + 1 < len(todos):
            datos[t[:-1]] = todos[i + 1]
    return datos


def detalle(categoria, subtipo, codigo):
    """Abre la ficha de un remate: navega hasta su fila, sigue el enlace y la parsea."""
    s = sesion_nueva()
    panel = ir_a_subtipo(s, categoria, subtipo)
    total = paginas_desde(panel)
    filas = parse_filas(panel)
    enlace = next((f["enlace"] for f in filas if f["codigo"] == codigo), None)
    foto_url = next((f["foto_url"] for f in filas if f["codigo"] == codigo), None)
    p = 1
    while enlace is None and p < total:
        p += 1
        frag = pagina(s, p)
        filas = parse_filas(frag)
        enlace = next((f["enlace"] for f in filas if f["codigo"] == codigo), None)
        foto_url = next((f["foto_url"] for f in filas if f["codigo"] == codigo), None)

    if enlace is None:
        raise RuntimeError("remate no encontrado en el listado")

    resp, _u = s.click(enlace, render="@all")
    red = re.search(r'<redirect url="([^"]+)"', resp)
    if not red:
        raise RuntimeError("no se pudo abrir la ficha")
    url = "https://remates.funcionjudicial.gob.ec" + red.group(1)
    pagina_html = s.get_limitado(url, max_bytes=500_000)

    doc = LH.fromstring(pagina_html)
    desc = ""
    cont = next((t for t in doc.iter("table") if t.get("id") == "contenido"), None)
    if cont is not None:
        span = next((x for x in cont.iter("span") if "subtitulosEncabezado" in (x.get("class") or "")), None)
        if span is not None:
            desc = limpiar(span.text_content())

    cod = ""
    for span in doc.iter("span"):
        t = limpiar(span.text_content())
        if t.startswith("EC-RJ"):
            cod = t
            break

    img = next((i.get("src") for i in doc.iter("img")
                if i.get("src") and "MediaOutput" in i.get("src")), None)

    # La imagen de la ficha suele venir vacia; la del listado si funciona.
    foto_bytes = None
    for candidata in (foto_url, img):
        if not candidata:
            continue
        if candidata.startswith("/"):
            candidata = "https://remates.funcionjudicial.gob.ec" + candidata
        try:
            data, _tipo = s.get_bytes(candidata)
            if data:
                foto_bytes = data
                break
        except Exception:
            continue

    return {
        "codigo": cod or codigo,
        "descripcion": desc,
        "campos": _campos_info(doc),
        "foto_url": img or foto_url,
        "foto_bytes": foto_bytes,
    }
