# Remates Judiciales EC — app de escritorio

Copia local de los remates judiciales publicados en
`https://remates.funcionjudicial.gob.ec/rematesjudiciales-web/pages/public/filtrando0.jsf`.

La app descarga los datos una vez, los guarda en SQLite y luego funciona **sin internet**:
búsqueda instantánea, filtros, ficha con foto y exportación a CSV/Excel.

## Versión portable (opcional, no versionada)

La carpeta `dist\` (y `dist\RematesEC-portable.zip`) es un intento de empaquetado con
PyInstaller. **No se versiona** en el repositorio y quedó como experimental: en algunas
máquinas la ventana de Edge en modo aplicación no carga la página.

Lo estable es la ejecución desde el código con `iniciar.bat`.

## Cómo se usa

1. Doble clic en **`iniciar.bat`**.
2. Se abre una ventana con la app (navegador en modo aplicación, sin barras).
3. La primera vez sincroniza solo (~45 s) y muestra la barra de progreso.
4. Botón **Actualizar datos** para volver a bajar cambios del portal.

> Requiere Windows y Python 3.10+. Las librerías (`lxml`, `Pillow`, `openpyxl`) viajan en
> la carpeta `vendor/`, así que no hace falta instalar nada con pip en este equipo.
>
> Si mueves la app a otro PC: borra `vendor/` y ejecuta `instalar_dependencias.bat`
> (o `pip install -r requirements.txt --target vendor`).

## Qué hace

- **Descarga completa**: categorías (Mueble/Inmueble), subtipos y todas las páginas.
- **Búsqueda y filtros** offline: texto libre, categoría, subtipo, provincia, rango de fechas.
- **Ficha de cada remate** bajo demanda: juzgado, sector, número de proceso, fechas de
  posturas, descripción, atributos del bien y foto.
- **Fotos optimizadas**: se guardan como JPG de ~30 KB (la original pesa ~2 MB).
- **Solo remates vigentes**: la app únicamente consulta la búsqueda normal (remates en
  difusión). No entra a *Remates históricos*, *Remates bloqueados* ni *Remates
  inhabilitados*.
- **Regla de vencimiento**: al pasar la fecha del remate se **borra** de la base junto con
  su foto, y deja de aparecer en la lista.
- **Alertas**: contador de remates nuevos desde la última sincronización (clic en el
  chip para marcarlos como vistos).
- **Exportar** el listado filtrado a CSV o Excel.

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
datos/remates.db        base local
datos/fotos/            fotos reducidas
iniciar.bat             arranque
```

## Notas técnicas

- El portal es JSF 2 + RichFaces: no hay API JSON. Los clics son POST con
  `javax.faces.ViewState`; además hay que enviar el parámetro con el **clientId del enlace**
  (`calendarIconPrincipal11=calendarIconPrincipal11`), si no el servidor responde 200 sin
  ejecutar la acción.
- Las fichas pesan ~50 MB porque incrustan las fotos en base64; se corta la lectura a
  500 KB, que es donde están los datos útiles.
- La foto del listado sí se puede descargar (~2 MB) y se reduce a ~30 KB antes de guardarla.
- Codificación: el sitio declara UTF-8 pero mezcla cp1252; se decodifica con respaldo.
- Todas las funciones del código están comentadas en español.
