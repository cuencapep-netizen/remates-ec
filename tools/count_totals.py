import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from jsf import RematesSession
from extractor import parse_categories, parse_subtypes, parse_results

CAT_IDS = {}  # filled per session

def fresh():
    s = RematesSession()
    s.accept_terms()
    _, u = s.click("calendarIconPrincipal11")
    cats = parse_categories(u.get("pnlF", ""))
    return s, cats

summary = []
s, cats = fresh()
for ci, cat in enumerate(cats):
    s2, cats2 = fresh()
    _, u = s2.click(cats2[ci]["id"])
    subs = parse_subtypes(u.get("pnlF", ""))
    for sub in subs:
        s3, cats3 = fresh()
        _, u3 = s3.click(cats3[ci]["id"])
        subs3 = parse_subtypes(u3.get("pnlF", ""))
        target = next(x for x in subs3 if x["nombre"] == sub["nombre"])
        _, u4 = s3.click(target["id"])
        rows, pages = parse_results(u4.get("pnlF", ""))
        summary.append({"categoria": cat["nombre"], "subtipo": sub["nombre"],
                        "paginas": pages, "aprox": pages * 10})
        print(f"{cat['nombre']:9} {sub['nombre']:22} paginas={pages:3} aprox={pages*10}")

out = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "salida", "resumen.json")
with open(out, "w", encoding="utf-8") as f:
    json.dump(summary, f, ensure_ascii=False, indent=2)
print("total aprox:", sum(x["aprox"] for x in summary))
