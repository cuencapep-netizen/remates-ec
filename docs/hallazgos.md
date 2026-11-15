# Remates Judiciales Ecuador — hallazgos de extracción (paso 1)

Fecha: 2026-11-15
Fuente: `https://remates.funcionjudicial.gob.ec/rematesjudiciales-web/pages/public/filtrando0.jsf`

## Resultado

Sí se puede extraer la información. Las **dos categorías** del buscador "Por Tipo de Bien" son:

| Categoría | Subtipos |
|---|---|
| **Mueble** | Vehículo, Derechos y Acciones, Lote |
| **Inmueble** | Urbano, Rural |

Cada subtipo lleva a un listado paginado (10 filas por página) con estas columnas:
`No. | Fotografía | Código | Fecha de Remate | Localización | Tipo | Bienes | Señalamiento | Avalúo Pericial | Avalúo Calculado`.

Ejemplo real (Mueble → Vehículo):

| Código | Fecha | Localización | Tipo | Avalúo |
|---|---|---|---|---|
| EC-RJ-157130 | nov, 16 2026 | GUAYAS GUAYAQUIL | Terrestre Liviano | 4,620.00 (100%) |
| EC-RJ-157845 | nov, 17 2026 | TUNGURAHUA AMBATO | Terrestre Pesado | 16,417.48 (75%) |

## Cómo funciona el sitio (para la app)

- JSF 2 + RichFaces 4. Todo va por POST con `javax.faces.ViewState` y AJAX parcial (`Faces-Request: partial/ajax`).
- Hay que "aceptar términos" una vez por sesión: `portal.jsf` → check `pagoDiferido` → botón `btn_aceptar_solicitud2` → redirige a `filtrando0.jsf`.
- **Truco clave:** los enlaces son *command links*; además de `javax.faces.source`, hay que enviar el parámetro con el **clientId del enlace** (`calendarIconPrincipal11=calendarIconPrincipal11`). Sin eso el servidor responde 200 pero no ejecuta la acción.
- La navegación devuelve fragmentos `<update id="pnlF">…` con el HTML del panel; de ahí se parsea con lxml.
- Paginación: POST con `source=tablaResultados:down` y `tablaResultados:down:page=N`; las filas llegan en `tablaResultados:tb`.
- Filtros disponibles en el panel de resultados: Provincia, Tipo de Bien, Clasificación, Tipo Específico, Fecha de Remate.
- Codificación: el servidor declara UTF-8 pero algunos textos vienen en cp1252; conviene decodificar con fallback.
- No requiere login para la búsqueda pública.

## Volumen observado (aprox., 10 por página)
| Categoría | Subtipo | Páginas | Registros |
|---|---|---|---|
| Mueble | Vehículo | 14 | ~140 |
| Mueble | Derechos y Acciones | 1 | ~10 |
| Mueble | Lote | 1 | ~10 |
| Inmueble | Urbano | 20 | ~200 |
| Inmueble | Rural | 20 | ~200 |

(El paginador puede topar en 20 páginas visibles; el total exacto se obtiene recorriendo todas las páginas.)

## Archivos

- `tools/jsf.py` — cliente de sesión JSF/RichFaces (aceptar términos, clicks, ViewState).
- `tools/extractor.py` — categorías, subtipos y muestra de remates → `salida/`.
- `tools/count_totals.py` — conteo de páginas por subtipo.
- `salida/categorias.json`, `salida/muestra_remates.csv`, `salida/resumen.json`.

## Listas que la app NO usa

El portal ofrece tres accesos extra en la pantalla de busqueda:

| Enlace | Comportamiento | Uso en la app |
|---|---|---|
| Remates historicos | Redirige y cambia el modo de la pantalla (ya no ofrece el catalogo por tipo de bien) | No se consulta |
| Remates bloqueados | Accion aparte, no forma parte del listado normal | No se consulta |
| Remates inhabilitados | Accion aparte, no forma parte del listado normal | No se consulta |

La app solo recorre la busqueda normal (remates en difusion) y ademas descarta cualquier
fila cuya fecha ya paso, de modo que la lista final contiene unicamente remates vigentes.
