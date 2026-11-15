"""Sincronizacion completa del portal hacia la base local."""
import threading
import time
import traceback

from . import datos, fuentes

# Estado compartido que consulta la interfaz para mostrar el progreso
ESTADO = {
    "corriendo": False,
    "fase": "",
    "categoria": "",
    "subtipo": "",
    "pagina": 0,
    "paginas": 0,
    "filas": 0,
    "nuevos": 0,
    "actualizados": 0,
    "error": None,
    "inicio": None,
    "fin": None,
}
_lock = threading.Lock()


def estado():
    """Copia del estado actual de la sincronizacion."""
    with _lock:
        return dict(ESTADO)


def _set(**kw):
    """Actualiza campos del estado de forma segura entre hilos."""
    with _lock:
        ESTADO.update(kw)


def sincronizar(con):
    """Recorre categorias, subtipos y paginas, y guarda todo en SQLite."""
    inicio = datos.ahora()
    _set(corriendo=True, fase="Conectando con el portal", error=None, inicio=inicio,
         nuevos=0, actualizados=0, filas=0, pagina=0, paginas=0)
    total_nuevos = total_actualizados = total_filas = 0
    try:
        s0 = fuentes.sesion_nueva()
        _set(fase="Leyendo categorias", pagina=0, paginas=0)
        categorias = fuentes.categorias(s0)
        for cat in categorias:
            _set(categoria=cat["nombre"], subtipo="", fase=f"Categoria {cat['nombre']}")
            s1 = fuentes.sesion_nueva()
            subtipos = fuentes.subtipos_de(s1, cat["nombre"])
            for sub in subtipos:
                _set(subtipo=sub["nombre"], pagina=1, paginas=0, filas=0)
                try:
                    s2 = fuentes.sesion_nueva()
                    panel = fuentes.ir_a_subtipo(s2, cat["nombre"], sub["nombre"])
                    total_pag = fuentes.paginas_desde(panel)
                    _set(paginas=total_pag)
                    filas = fuentes.parse_filas(panel)
                    n, a = datos.guardar_filas(con, cat["nombre"], sub["nombre"], filas)
                    total_nuevos += n
                    total_actualizados += a
                    total_filas += len(filas)
                    filas_sub = len(filas)
                    _set(filas=filas_sub, pagina=1, nuevos=total_nuevos,
                         actualizados=total_actualizados)
                    for p in range(2, total_pag + 1):
                        time.sleep(0.35)  # pausa amable con el servidor publico
                        frag = fuentes.pagina(s2, p)
                        filas = fuentes.parse_filas(frag)
                        n, a = datos.guardar_filas(con, cat["nombre"], sub["nombre"], filas)
                        total_nuevos += n
                        total_actualizados += a
                        total_filas += len(filas)
                        filas_sub += len(filas)
                        _set(filas=filas_sub, pagina=p, nuevos=total_nuevos,
                             actualizados=total_actualizados)
                except Exception as e:  # un subtipo que falle no debe tumbar el resto
                    _set(error=f"{sub['nombre']}: {e}")
                    print("ERROR subtipo", sub["nombre"], e)
                    traceback.print_exc()

        vencidos = datos.purgar_vencidos(con)
        fin = datos.ahora()
        datos.registrar_sync(con, inicio, fin, total_nuevos, total_actualizados, total_filas, True)
        _set(corriendo=False, fase="Listo", fin=fin)
        print(f"Sync OK nuevos={total_nuevos} actualizados={total_actualizados} vencidos={vencidos}")
    except Exception as e:
        fin = datos.ahora()
        datos.registrar_sync(con, inicio, fin, total_nuevos, total_actualizados, total_filas, False, str(e))
        _set(corriendo=False, fase="Error", error=str(e), fin=fin)
        traceback.print_exc()


def lanzar(con):
    """Arranca la sincronizacion en un hilo aparte (no bloquea la interfaz)."""
    if estado()["corriendo"]:
        return False
    hilo = threading.Thread(target=sincronizar, args=(con,), daemon=True)
    hilo.start()
    return True
