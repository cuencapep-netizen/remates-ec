"""Extractor de categorias y remates del portal publico de Remates Judiciales (Ecuador).

Uso:
    python tools/extractor.py            -> genera salida/categorias.json y salida/muestra.csv
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from jsf import RematesSession  # noqa: E402
from lxml import html as LH  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "salida")


def clean(s):
    return " ".join((s or "").split())


def parse_categories(panel_html):
    doc = LH.fromstring(panel_html)
    cats = []
    for a in doc.iter("a"):
        txt = clean(a.text_content())
        aid = a.get("id") or ""
        if txt and ":" in aid and "Regresar" not in txt:
            cats.append({"id": aid, "nombre": txt})
    return cats


def parse_subtypes(panel_html):
    doc = LH.fromstring(panel_html)
    subs = []
    for tr in doc.iter("tr"):
        cells = [clean(td.text_content()) for td in tr.iter("td")]
        if len(cells) >= 2 and cells[0].isdigit():
            link = next((a.get("id") for a in tr.iter("a") if a.get("id")), None)
            subs.append({"n": int(cells[0]), "nombre": cells[1], "id": link})
    return subs


def parse_results(panel_html):
    doc = LH.fromstring(panel_html)
    table = next((t for t in doc.iter("table") if t.get("id") == "tablaResultados"), None)
    rows = []
    if table is not None:
        for tr in table.iter("tr"):
            cells = [clean(td.text_content()) for td in tr.iter("td")]
            if len(cells) >= 10 and cells[0].isdigit():
                rows.append({
                    "n": int(cells[0]),
                    "codigo": cells[2],
                    "fecha_remate": cells[3],
                    "localizacion": cells[4],
                    "tipo": cells[5],
                    "bienes": cells[6],
                    "senalamiento": cells[7],
                    "avaluo_pericial": cells[8],
                    "avaluo_calculado": cells[9],
                })
    pages = sorted({int(x) for x in re.findall(r'tablaResultados:down_ds_(\d+)"', panel_html)})
    return rows, (max(pages) if pages else 1)


def session_with_categories():
    s = RematesSession()
    s.accept_terms()
    _, u = s.click("calendarIconPrincipal11")
    return s, parse_categories(u.get("pnlF", ""))


def main():
    os.makedirs(OUT, exist_ok=True)
    report = {"categorias": [], "generado": None}

    s, cats = session_with_categories()
    print("Categorias encontradas:", [c["nombre"] for c in cats])

    for idx, cat in enumerate(cats):
        # sesion nueva por categoria para evitar ids/estados cruzados
        s2, cats2 = session_with_categories()
        target = cats2[idx]
        _, u = s2.click(target["id"])
        subs = parse_subtypes(u.get("pnlF", ""))
        print(f"  {target['nombre']}: subtipos -> {[x['nombre'] for x in subs]}")

        muestra = []
        if subs:
            _, u2 = s2.click(subs[0]["id"])
            muestra, paginas = parse_results(u2.get("pnlF", ""))
            print(f"    muestra {subs[0]['nombre']}: {len(muestra)} filas, {paginas} paginas")

        report["categorias"].append({
            "nombre": target["nombre"],
            "subtipos": [x["nombre"] for x in subs],
            "muestra_subtipo": subs[0]["nombre"] if subs else None,
            "muestra": muestra,
        })

    with open(os.path.join(OUT, "categorias.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    # CSV plano de la muestra
    import csv
    with open(os.path.join(OUT, "muestra_remates.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["categoria", "subtipo", "codigo", "fecha_remate", "localizacion",
                    "tipo", "bienes", "senalamiento", "avaluo_pericial", "avaluo_calculado"])
        for c in report["categorias"]:
            for r in c["muestra"]:
                w.writerow([c["nombre"], c["muestra_subtipo"], r["codigo"], r["fecha_remate"],
                            r["localizacion"], r["tipo"], r["bienes"], r["senalamiento"],
                            r["avaluo_pericial"], r["avaluo_calculado"]])
    print("OK ->", OUT)


if __name__ == "__main__":
    main()
