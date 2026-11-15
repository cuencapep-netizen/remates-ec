# Remates Judiciales EC

Herramienta de escritorio para consultar **sin internet** los remates judiciales publicados
por el Consejo de la Judicatura del Ecuador.

Descarga los datos del portal público, los guarda en SQLite y permite buscarlos, filtrarlos
y exportarlos al instante. No requiere instalar Python si usas la versión desde el código con
las dependencias incluidas en `vendor/`.

## Qué hace

- **Sincronización completa** del portal: categorías (Mueble / Inmueble), subtipos y todas
  las páginas del listado (~540 remates vigentes, ~45 segundos).
- **Consulta offline**: búsqueda por texto, categoría, subtipo, provincia y rango de fechas.
- **Ficha de cada remate** bajo demanda: juzgado, sector, número de proceso, fechas de
  posturas, descripción del bien y foto (guardada como JPG de ~30 KB).
- **Solo remates vigentes**: al pasar la fecha del remate se elimina de la base junto con su
  foto. No se consultan las listas de históricos, bloqueados ni inhabilitados.
- **Alertas** de remates nuevos desde la última sincronización.
- **Exportación** del listado filtrado a CSV y Excel.

## Cómo se usa

```bat
git clone https://github.com/<usuario>/remates-ec.git
cd remates-ec
instalar_dependencias.bat   :: una sola vez (lxml, Pillow, openpyxl -> vendor\)
iniciar.bat
```

`iniciar.bat` levanta un servidor local y abre la interfaz en una ventana de Edge en modo
aplicación. En la primera ejecución sincroniza automáticamente.

También se puede lanzar a mano:

```bat
python -m app.main
```

## Estructura

```
app/
  jsf.py        cliente de sesión JSF/RichFaces (términos, ViewState, clics)
  fuentes.py    parseo del portal: categorías, subtipos, listado y ficha
  datos.py      SQLite: esquema, altas/bajas, consultas y resumen
  sync.py       sincronización completa con progreso
  servidor.py   API HTTP local + exportaciones
  main.py       lanzador: servidor + ventana
  web/          interfaz (HTML, CSS y JS sin dependencias)
docs/           documentación y notas técnicas
tools/          scripts del análisis inicial del portal
iniciar.bat             arranque
instalar_dependencias.bat   instala lxml, Pillow y openpyxl en vendor\
requirements.txt
```

## Cómo funciona (resumen técnico)

El portal es JSF 2 + RichFaces: no tiene API JSON. Todo se resuelve con POST y
`javax.faces.ViewState`, y hay un detalle clave: además de `javax.faces.source`, el servidor
exige el parámetro con el **clientId del enlace** que se "pulsa"; sin él responde 200 pero no
ejecuta la acción.

Las fichas de detalle pesan ~50 MB porque incrustan las fotos en base64, así que la lectura
se corta a 500 KB, que es donde están los datos útiles. Más detalles en
[`docs/hallazgos.md`](docs/hallazgos.md).

## Aviso

Los datos son públicos (Consejo de la Judicatura del Ecuador). Esta herramienta solo los
consulta y los guarda localmente; no modifica nada en el portal ni requiere credenciales.
La sincronización incluye pausas para no cargar el servidor público.

## Licencia

MIT. Ver [`LICENSE`](LICENSE).
