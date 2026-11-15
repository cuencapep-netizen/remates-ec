// Interfaz de la app de remates: consulta la API local y pinta la tabla.
const $ = (s) => document.querySelector(s);
const LIMITE = 100; // filas por carga

let estado = { offset: 0, total: 0, filtros: {} };
let sincronizando = false;

/** Escapa texto para insertarlo seguro en HTML. */
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => (
  { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

/** Convierte '2026-11-16' a '16/11/2026'. */
const fmtFecha = (iso) => {
  if (!iso) return "—";
  const [a, m, d] = iso.split("-");
  return `${d}/${m}/${a}`;
};

/** Formatea un numero como dinero en dolares. */
const fmtDinero = (n) => (n == null ? "—" : "$ " + n.toLocaleString("es-EC", { minimumFractionDigits: 2, maximumFractionDigits: 2 }));

/** Envoltorio de fetch que valida la respuesta y devuelve JSON. */
async function api(url, opciones) {
  const r = await fetch(url, opciones);
  if (!r.ok) throw new Error("Error " + r.status);
  return r.json();
}

/** Lee los filtros que el usuario tiene puestos en pantalla. */
function leerFiltros() {
  return {
    q: $("#q").value.trim(),
    categoria: $("#categoria").value,
    subtipo: $("#subtipo").value,
    provincia: $("#provincia").value,
    desde: $("#desde").value,
    hasta: $("#hasta").value,
    orden: $("#orden").value,
  };
}

/** Construye la cadena de consulta con los filtros actuales mas los extra. */
function queryString(extra = {}) {
  const f = { ...leerFiltros(), ...extra };
  const p = new URLSearchParams();
  Object.entries(f).forEach(([k, v]) => { if (v !== "" && v != null) p.set(k, v); });
  return p.toString();
}

// ---------------------------------------------------------------- estado
/** Pide el resumen al servidor, actualiza los selectores y el chip de estado. */
async function cargarEstado(pintar = true) {
  const data = await api("/api/estado");
  const r = data.resumen;
  if (pintar) pintarSelects(r);
  const chip = $("#chipEstado");
  let texto = `${r.activos} vigentes de ${r.total}`;
  if (r.ultima && r.ultima.fin) texto += ` · act. ${r.ultima.fin.slice(0, 16)}`;
  chip.textContent = texto;
  chip.className = "chip ok";
  if (r.nuevos > 0) {
    chip.textContent = `${r.nuevos} nuevos · ${texto}`;
    chip.className = "chip nuevo";
  }
  actualizarSync(data.sync);
  return r;
}

/** Rellena los selectores de categoria, subtipo y provincia. */
function pintarSelects(r) {
  const cat = $("#categoria");
  const cats = [...new Set(r.categorias.map((c) => c.categoria))];
  const valorCat = cat.value;
  cat.innerHTML = '<option value="">Todas las categorías</option>' +
    cats.map((c) => `<option value="${esc(c)}">${esc(c)}</option>`).join("");
  cat.value = valorCat;

  const sub = $("#subtipo");
  const valorSub = sub.value;
  const subs = r.categorias.filter((c) => !cat.value || c.categoria === cat.value);
  sub.innerHTML = '<option value="">Todos los subtipos</option>' +
    subs.map((c) => `<option value="${esc(c.subtipo)}">${esc(c.subtipo)} (${c.n})</option>`).join("");
  sub.value = valorSub;

  const prov = $("#provincia");
  const valorProv = prov.value;
  prov.innerHTML = '<option value="">Todas las provincias</option>' +
    r.provincias.map((p) => `<option value="${esc(p)}">${esc(p)}</option>`).join("");
  prov.value = valorProv;
}

// ---------------------------------------------------------------- listado
/** Carga la tabla de remates; con reset=true vuelve a la primera pagina. */
async function cargarRemates(reset = true) {
  if (reset) estado.offset = 0;
  const data = await api("/api/remates?" + queryString({ limite: LIMITE, offset: estado.offset }));
  const cuerpo = $("#cuerpo");
  if (reset) cuerpo.innerHTML = "";
  estado.total = data.total;

  data.filas.forEach((f) => {
    const tr = document.createElement("tr");
    tr.dataset.codigo = f.codigo;
    tr.innerHTML = `
      <td class="cod">${esc(f.codigo)}</td>
      <td class="fecha">${fmtFecha(f.fecha)}</td>
      <td><span class="etiqueta ${f.categoria === "Mueble" ? "mueble" : ""}">${esc(f.subtipo)}</span></td>
      <td>${esc(f.provincia)}${f.canton ? " · " + esc(f.canton) : ""}</td>
      <td>${esc(f.tipo)}</td>
      <td>${esc(f.senalamiento)}</td>
      <td class="der"><span class="monto">${fmtDinero(f.avaluo_calc)}</span>
        <div class="pct">${f.pct != null ? f.pct + "% del avalúo" : ""}</div></td>
      <td><button class="btn">Detalle</button></td>`;
    tr.addEventListener("click", () => abrirDetalle(f.codigo));
    cuerpo.appendChild(tr);
  });

  estado.offset += data.filas.length;
  $("#contador").textContent = `${data.total} remate${data.total === 1 ? "" : "s"}`;
  $("#vacio").classList.toggle("oculto", data.total !== 0);
  $("#btnMas").classList.toggle("oculto", estado.offset >= data.total);
}

// ---------------------------------------------------------------- detalle
/** Abre el cajon lateral con la ficha completa y la foto del remate. */
async function abrirDetalle(codigo) {
  $("#cajon").classList.add("abierto");
  $("#velo").classList.remove("oculto");
  $("#detCodigo").textContent = codigo;
  $("#detSub").textContent = "";
  $("#detCampos").innerHTML = "";
  $("#detDesc").textContent = "";
  $("#detFoto").innerHTML = '<div class="cargando">cargando ficha…</div>';

  try {
    const d = await api("/api/remate/" + encodeURIComponent(codigo));
    $("#detCodigo").textContent = d.codigo || codigo;
    $("#detSub").textContent = [d.remate.categoria, d.remate.subtipo].filter(Boolean).join(" · ") +
      " · " + fmtFecha(d.remate.fecha);
    const campos = Object.entries(d.campos || {});
    $("#detCampos").innerHTML = campos.map(([k, v]) =>
      `<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`).join("");
    $("#detDesc").textContent = d.descripcion || "Sin descripción registrada.";
    $("#detFoto").innerHTML = `<img src="/api/foto/${encodeURIComponent(codigo)}?t=${Date.now()}" alt="Foto del bien"
      onerror="this.parentNode.innerHTML='<div class=&quot;cargando&quot;>sin foto</div>'" />`;
  } catch (e) {
    $("#detFoto").innerHTML = `<div class="cargando">no se pudo cargar la ficha</div>`;
    $("#detDesc").textContent = e.message + ". Revisa tu conexión e inténtalo otra vez.";
  }
}

/** Cierra el cajon de detalle. */
function cerrarDetalle() {
  $("#cajon").classList.remove("abierto");
  $("#velo").classList.add("oculto");
}

// ---------------------------------------------------------------- sync
/** Refleja en la barra de progreso el estado de la sincronizacion. */
function actualizarSync(s) {
  const barra = $("#progreso");
  if (s && s.corriendo) {
    barra.classList.remove("oculto");
    const pct = s.paginas ? Math.round((s.pagina / s.paginas) * 100) : 5;
    $("#progresoBarra").style.width = pct + "%";
    $("#progresoPct").textContent = pct + "%";
    $("#progresoTexto").textContent = `${s.fase}${s.subtipo ? " · " + s.subtipo : ""} · pág. ${s.pagina}/${s.paginas || "?"} · ${s.filas} filas`;
    $("#btnSync").disabled = true;
    sincronizando = true;
  } else {
    $("#btnSync").disabled = false;
    if (sincronizando) {
      barra.classList.add("oculto");
      sincronizando = false;
      cargarEstado();
      cargarRemates(true);
    }
    if (s && s.error) {
      $("#chipEstado").textContent = "error al actualizar";
      $("#chipEstado").className = "chip nuevo";
    }
  }
}

/** Lanza la sincronizacion y va consultando el progreso cada 1,5 s. */
async function sincronizar() {
  await api("/api/sync", { method: "POST" });
  sincronizando = true;
  $("#progreso").classList.remove("oculto");
  const tic = setInterval(async () => {
    const data = await api("/api/estado");
    actualizarSync(data.sync);
    if (!data.sync.corriendo) clearInterval(tic);
  }, 1500);
}

// ---------------------------------------------------------------- eventos
let temporizador;

/** Devuelve una version "retrasada" de fn, para no consultar en cada tecla. */
function conDebounce(fn, ms = 320) {
  return (...a) => { clearTimeout(temporizador); temporizador = setTimeout(() => fn(...a), ms); };
}

$("#q").addEventListener("input", conDebounce(() => cargarRemates(true)));
["#provincia", "#orden", "#desde", "#hasta"].forEach((s) =>
  $(s).addEventListener("change", () => cargarRemates(true)));
$("#categoria").addEventListener("change", async () => {
  const r = await api("/api/estado");
  pintarSelects(r.resumen);
  cargarRemates(true);
});
$("#subtipo").addEventListener("change", () => cargarRemates(true));
$("#btnMas").addEventListener("click", () => cargarRemates(false));
$("#btnSync").addEventListener("click", sincronizar);
$("#chipEstado").addEventListener("click", async () => {
  await api("/api/vistos", { method: "POST" });
  cargarEstado(false);
});
$("#cerrar").addEventListener("click", cerrarDetalle);
$("#velo").addEventListener("click", cerrarDetalle);
$("#btnCsv").addEventListener("click", () => { window.location = "/api/export.csv?" + queryString(); });
$("#btnXlsx").addEventListener("click", () => { window.location = "/api/export.xlsx?" + queryString(); });
document.addEventListener("keydown", (e) => { if (e.key === "Escape") cerrarDetalle(); });

// ---------------------------------------------------------------- arranque
/** Arranca la interfaz: estado inicial y, si la base esta vacia, primera sincronizacion. */
(async function init() {
  const r = await cargarEstado();
  await cargarRemates(true);
  if (!r.total) {
    await api("/api/vistos", { method: "POST" }).catch(() => {});
    sincronizar();
  }
})();
