/* =========================================================================
   IPC Messenger · Frontend
   Toda la lógica de simulación vive en el servidor (paquete ipc_sim);
   este archivo sólo consume la API REST y dibuja.
   ========================================================================= */
"use strict";

const COLOR_ESTADO = {
  "Nuevo": "#94A3B8", "Listo": "#2F7FD8", "Ejecución": "#0C853B", "Bloqueado": "#E39A0B",
  "Espera activa": "#E0611A", "No responde": "#7C4DDB", "Caído": "#D32F2F", "Terminado": "#4A5A52",
};
const GRIS_FLECHA = "#C6D3CB";
const COLORES_SERIE = ["#0C853B", "#2F7FD8", "#E0611A", "#7C4DDB"];
const NOMBRE_ROL = { emisor: "emisor", receptor: "receptor", mixto: "envía / recibe" };
const ETIQUETA_FALLO = { caer: "Caída", no_responder: "Congelado", lento: "Lento", recuperar: "Recuperación" };

const $ = (sel, raiz = document) => raiz.querySelector(sel);
const $$ = (sel, raiz = document) => Array.from(raiz.querySelectorAll(sel));
const esc = (t) => String(t ?? "").replace(/[&<>"']/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const recortar = (t, n) => (t.length > n ? t.slice(0, Math.max(1, n - 1)) + "…" : t);

// ------------------------------------------------------------------ API
async function api(url, opciones = {}) {
  const init = { headers: { "Content-Type": "application/json" }, ...opciones };
  if (init.body && typeof init.body !== "string") init.body = JSON.stringify(init.body);
  let respuesta;
  try {
    respuesta = await fetch(url, init);
  } catch (e) {
    throw new Error(t("No hay conexión con el servidor. ¿Sigue en ejecución «python main.py»?"));
  }
  let datos = {};
  try { datos = await respuesta.json(); } catch (e) { /* respuesta vacía */ }
  if (!respuesta.ok || datos.ok === false) {
    const err = new Error((datos.errores || [`Error ${respuesta.status}`]).map(tr).join("\n"));
    err.errores = datos.errores || [];
    throw err;
  }
  return datos;
}

function toast(mensaje, tipo = "info", titulo = "") {
  const caja = document.createElement("div");
  caja.className = `toast ${tipo}`;
  caja.innerHTML = (titulo ? `<b>${esc(titulo)}</b>` : "") + esc(mensaje).replace(/\n/g, "<br>");
  $("#toasts").appendChild(caja);
  setTimeout(() => caja.remove(), tipo === "error" ? 7000 : 4500);
}

// ---------------------------------------------------------------- vistas
const VISTAS = ["inicio", "simulador", "experimento", "real", "conceptos"];
function mostrarVista(nombre) {
  if (!VISTAS.includes(nombre)) nombre = "inicio";
  VISTAS.forEach((v) => { $(`#vista-${v}`).hidden = v !== nombre; });
  $$(".navegacion a").forEach((a) => a.classList.toggle("activo", a.dataset.ir === nombre));
  $("#navegacion").classList.remove("abierta");
  $("#toasts").innerHTML = "";
  if (nombre === "simulador" && sim.estado) dibujarTodo(sim.estado, false);
  window.scrollTo({ top: 0 });
}
window.addEventListener("hashchange", () => mostrarVista(location.hash.slice(1)));
$("#btnMenu").addEventListener("click", () => $("#navegacion").classList.toggle("abierta"));

// ===================================================================
//                              SIMULADOR
// ===================================================================
const sim = {
  escenarios: [], estado: null, eventosVistos: 0,
  corriendo: false, temporizador: null, seleccion: null,
  // El servidor no guarda estado (apto para Vercel): el navegador conserva la
  // «receta» y el servidor la reproduce de forma determinista en cada petición.
  receta: null,            // { escenario, config, ops: [["p", n] | ["e"] | ["f", pid, tipo, factor]] }
  cola: Promise.resolve(), // las peticiones se envían en orden, una a la vez
};

function encolar(tarea) {
  const r = sim.cola.then(tarea, tarea);
  sim.cola = r.catch(() => {});
  return r;
}

function opsCon(op) {
  const ops = sim.receta.ops.map((o) => o.slice());
  const ultima = ops[ops.length - 1];
  if (op[0] === "p" && ultima && ultima[0] === "p" && ultima[1] + op[1] <= 5000) ultima[1] += op[1];
  else ops.push(op);
  return ops;
}
const form = $("#formConfig");

function leerFormulario(formulario) {
  const config = {}, errores = [];
  $$("input, select", formulario).forEach((el) => {
    if (!el.name) return;
    el.classList.remove("invalido");
    if (el.type === "checkbox") { config[el.name] = el.checked; return; }
    if (el.type === "number") {
      const txt = el.value.trim(), v = Number(txt);
      const min = Number(el.min), max = Number(el.max);
      const lbl = el.closest("label");
      const etiqueta = (lbl.querySelector("[data-i18n]") || lbl.childNodes[0]).textContent.trim();
      if (txt === "" || !Number.isInteger(v)) {
        errores.push(t("«{e}» debe ser un número entero.", { e: etiqueta }));
        el.classList.add("invalido");
      } else if (v < min || v > max) {
        errores.push(t("«{e}» debe estar entre {min} y {max}.", { e: etiqueta, min, max }));
        el.classList.add("invalido");
      }
      config[el.name] = v;
      return;
    }
    config[el.name] = el.value;
  });
  return { config, errores };
}

function llenarFormulario(config) {
  Object.entries(config).forEach(([clave, valor]) => {
    const el = form.elements[clave];
    if (!el) return;
    if (el.type === "checkbox") el.checked = !!valor; else el.value = valor;
    el.classList.remove("invalido");
  });
}

function describirEscenario(esc_) {
  const caja = $("#descEscenario");
  if (!esc_) {
    caja.innerHTML = `<span class="tipo-escenario tipo-normal">${t("Personalizado")}</span>
      <p>${t("Configuración libre. Ajusta los parámetros y pulsa <b>Aplicar y reiniciar</b>.")}</p>`;
    return;
  }
  const fallos = esc_.fallos.map((f) => t("{f} de {pid} en el tick {t}", { f: t(ETIQUETA_FALLO[f.tipo]), pid: f.pid, t: f.tick })).join(" · ");
  const tx = escTexto(esc_);
  caja.innerHTML = `<span class="tipo-escenario tipo-${esc(esc_.tipo)}">${esc(t(esc_.tipo))}</span>
    <p>${esc(tx.descripcion)}</p>
    <p><b>${t("Esperado:")}</b> ${esc(tx.esperado)}</p>
    ${fallos ? `<p><b>${t("Fallos programados:")}</b> ${esc(fallos)}</p>` : ""}`;
}

async function cargarEscenarios() {
  try {
    sim.escenarios = await api("/api/escenarios");
  } catch (e) { toast(e.message, "error", t("No se pudieron cargar los escenarios")); return; }
  llenarSelectorEscenarios();
  $("#selEscenario").value = sim.escenarios[0].clave;
  await elegirEscenario(sim.escenarios[0].clave);
}

function llenarSelectorEscenarios() {
  const sel = $("#selEscenario");
  const actual = sel.value;
  sel.innerHTML = `<option value="">${t("— Personalizado —")}</option>` +
    sim.escenarios.map((e) => `<option value="${esc(e.clave)}">${esc(escTexto(e).titulo)}</option>`).join("");
  sel.value = actual;
}

async function elegirEscenario(clave) {
  detener();
  const esc_ = sim.escenarios.find((e) => e.clave === clave);
  describirEscenario(esc_);
  if (esc_) llenarFormulario(esc_.config);
  await crearSimulacion(esc_ ? { escenario: clave } : { config: leerFormulario(form).config });
}

async function crearSimulacion(cuerpo) {
  const receta = { escenario: cuerpo.escenario || null, config: cuerpo.config ?? null, ops: [] };
  try {
    const estado = await encolar(() => api("/api/simular", { method: "POST", body: { ...receta, desde: 0 } }));
    sim.receta = receta;
    sim.eventosVistos = 0;
    $("#registro").innerHTML = "";
    sim.registro = [];
    sim.seleccion = null;
    aplicarEstado(estado, false);
  } catch (e) { toast(e.message, "error", t("Configuración inválida")); }
}

function aplicarEstado(estado, animar) {
  sim.estado = estado;
  if (estado.eventos_reinicio) { $("#registro").innerHTML = ""; sim.registro = []; }
  agregarEventos(estado.eventos);
  sim.eventosVistos = estado.eventos_total;
  dibujarTodo(estado, animar);
}

// -------------------------------------------------------------- ejecución
const continua = (e) => !e.finalizado && !e.estancado;

async function enviarOp(op) {
  const ops = opsCon(op);
  const estado = await api("/api/simular",
    { method: "POST", body: { ...sim.receta, ops, desde: sim.eventosVistos } });
  sim.receta.ops = ops;
  return estado;
}

async function avanzar(ruta, cuerpo = {}) {
  if (!sim.receta) return false;
  return encolar(() => avanzarAhora(ruta, cuerpo));
}

async function avanzarAhora(ruta, cuerpo) {
  try {
    const estado = await enviarOp(ruta === "final" ? ["e"] : ["p", cuerpo.n || 1]);
    const antes = sim.estado;
    aplicarEstado(estado, true);
    if (estado.estancado && !(antes && antes.estancado)) {
      toast(tr(estado.diagnostico), "error", t("⛔ Estancamiento detectado"));
    } else if (estado.finalizado && !(antes && antes.finalizado)) {
      toast(t("La simulación terminó en el tick {t}.", { t: estado.tick }), "info", t("■ Finalizada"));
    }
    return continua(estado);
  } catch (e) {
    toast(e.message, "error");
    return false;
  }
}

function retardo() {
  const v = Number($("#rngVelocidad").value);          // 1 lento … 10 rápido
  return Math.round(950 * Math.pow(0.68, v - 1));
}

async function bucle() {
  if (!sim.corriendo) return;
  const sigue = await avanzar("paso", { n: 1 });
  if (!sigue) { detener(); return; }
  sim.temporizador = setTimeout(bucle, retardo());
}

function iniciar() {
  if (!sim.estado) return;
  if (!continua(sim.estado)) {
    if (sim.estado.estancado) toast(t("La simulación está estancada. Recupera un proceso o reinicia."), "aviso");
    else toast(t("La simulación ya terminó. Pulsa «Aplicar y reiniciar»."), "aviso");
    return;
  }
  sim.corriendo = true;
  $("#btnEjecutar").textContent = t("⏸ Pausa");
  actualizarInsignia(sim.estado);
  bucle();
}

function detener() {
  sim.corriendo = false;
  clearTimeout(sim.temporizador);
  $("#btnEjecutar").textContent = t("▶ Ejecutar");
  if (sim.estado) actualizarInsignia(sim.estado);
}

$("#btnEjecutar").addEventListener("click", () => (sim.corriendo ? detener() : iniciar()));
$("#btnPaso").addEventListener("click", async () => {
  detener();
  if (sim.estado && !continua(sim.estado)) { toast(t("No hay más pasos que ejecutar."), "aviso"); return; }
  await avanzar("paso", { n: 1 });
});
$("#btnFinal").addEventListener("click", async () => { detener(); await avanzar("final"); });
$("#selEscenario").addEventListener("change", (e) => elegirEscenario(e.target.value));
form.addEventListener("submit", async (ev) => {
  ev.preventDefault();
  detener();
  const { config, errores } = leerFormulario(form);
  if (errores.length) { toast(errores.join("\n"), "error", t("Revisa la configuración")); return; }
  const clave = $("#selEscenario").value;
  await crearSimulacion(clave ? { escenario: clave, config } : { config });
});
form.addEventListener("input", () => {
  const caja = $("#descEscenario");
  if (!caja.querySelector(".pendiente")) {
    caja.insertAdjacentHTML("beforeend", `<p class="pendiente">${t("<b>✎ Cambios sin aplicar.</b> Pulsa «Aplicar y reiniciar».")}</p>`);
  }
});
$$("[data-fallo]").forEach((b) => b.addEventListener("click", () => inyectarFallo(b.dataset.fallo)));
$("#selProceso").addEventListener("change", (e) => { sim.seleccion = e.target.value; dibujarDiagrama(sim.estado, false); });
$("#btnCsv").addEventListener("click", () => exportar("csv"));
$("#btnJson").addEventListener("click", () => exportar("json"));

async function exportar(formato) {
  if (!sim.receta) return;
  try {
    const r = await fetch("/api/exportar", { method: "POST", headers: { "Content-Type": "application/json" },
                                             body: JSON.stringify({ ...sim.receta, formato }) });
    if (!r.ok) throw new Error(((await r.json().catch(() => ({}))).errores || [t("No se pudo exportar")]).map(tr).join("\n"));
    const nombre = (r.headers.get("Content-Disposition") || "").split("filename=")[1] || `ipc_messenger.${formato}`;
    const blob = await r.blob();
    const a = Object.assign(document.createElement("a"), { href: URL.createObjectURL(blob), download: nombre });
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  } catch (e) { toast(e.message, "error", t("Exportar")); }
}
$("#chkSoloAlertas").addEventListener("change", (e) => $("#registro").classList.toggle("solo-alertas", e.target.checked));

async function inyectarFallo(tipo) {
  const pid = $("#selProceso").value;
  if (!sim.receta || !pid) return;
  try {
    const estado = await encolar(() => enviarOp(["f", pid, tipo, 3]));
    if (estado.mensaje) sim.receta.ops.pop();   // el fallo no cambió nada: no se guarda en la receta
    aplicarEstado(estado, false);
    if (estado.mensaje) toast(tr(estado.mensaje), "aviso", t("Fallo no aplicable"));
    else toast(t("{f} aplicada a {pid}.", { f: t(ETIQUETA_FALLO[tipo]), pid }), "info");
  } catch (e) { toast(e.message, "error"); }
}

// ------------------------------------------------------------- render
function actualizarInsignia(e) {
  const ins = $("#lblEstado");
  ins.className = "insignia";
  if (e.estancado) { ins.textContent = t("⛔ Estancado"); ins.classList.add("estancado"); }
  else if (e.finalizado) { ins.textContent = t("■ Finalizado"); ins.classList.add("finalizado"); }
  else if (sim.corriendo) { ins.textContent = t("● En ejecución"); ins.classList.add("corriendo"); }
  else ins.textContent = e.tick === 0 ? t("Listo para iniciar") : t("En pausa");
}

function dibujarTodo(e, animar) {
  $("#lblTick").textContent = e.tick;
  actualizarInsignia(e);
  const diag = $("#diagnostico");
  diag.hidden = !e.estancado;
  if (e.estancado) diag.innerHTML = `<b>${t("⛔ Estancamiento detectado:")}</b> ${esc(tr(e.diagnostico))}`;

  const sel = $("#selProceso");
  const pids = e.procesos.map((p) => p.pid);
  if (!sim.seleccion || !pids.includes(sim.seleccion)) sim.seleccion = pids[pids.length - 1];
  sel.innerHTML = e.procesos.map((p) => `<option value="${esc(p.pid)}">${esc(p.pid)} · ${esc(t(p.estado))}</option>`).join("");
  sel.value = sim.seleccion;

  if ($("#vista-simulador").hidden) return;
  dibujarDiagrama(e, animar);
  dibujarGrafica(e);
  dibujarMetricas(e);
}

function agregarEventos(eventos, rehacer = false) {
  const lista = $("#registro");
  if (!rehacer) {
    sim.registro = (sim.registro || []).concat(eventos);
    if (sim.registro.length > 900) sim.registro = sim.registro.slice(-900);
  }
  const frag = document.createDocumentFragment();
  for (const ev of eventos) {
    const li = document.createElement("li");
    li.className = ev.nivel;
    li.innerHTML = `<span class="t">${ev.tick}</span><span>${ev.origen ? `<span class="origen">${esc(ev.origen)}</span> ` : ""}${esc(tr(ev.texto))}</span>`;
    frag.appendChild(li);
  }
  const abajo = lista.scrollHeight - lista.scrollTop - lista.clientHeight < 40;
  lista.appendChild(frag);
  while (lista.children.length > 900) lista.firstChild.remove();
  if (abajo) lista.scrollTop = lista.scrollHeight;
}

// -------------------------------------------------------------- diagrama
function dibujarDiagrama(e, animar) {
  const svg = $("#diagrama");
  const ancho = Math.round((svg.parentElement.clientWidth || 1000) - 18);
  const vertical = ancho < 660;                       // celulares: emisores arriba, receptores abajo
  const W = Math.max(ancho, vertical ? 320 : 700);
  const M = 14, CH = 96, SEP = 14, CANAL_H = 178, CANAL_SEP = 24;
  const izq = e.procesos.filter((p) => p.rol === "emisor");
  const der = e.procesos.filter((p) => p.rol === "receptor");
  e.procesos.filter((p) => p.rol === "mixto").forEach((p, i) => (i % 2 ? der : izq).push(p));
  const altoCanales = e.canales.length * CANAL_H + (e.canales.length - 1) * CANAL_SEP;
  const pos = {}, posCanal = {};
  let H;

  if (!vertical) {
    const CW = W >= 940 ? 190 : W >= 800 ? 168 : 152, HUECO = W >= 940 ? 64 : 40;
    const altoLado = (n) => n * CH + (n - 1) * SEP;
    H = Math.max(altoLado(izq.length), altoLado(der.length), altoCanales, 280) + 2 * M;
    const xIzq = M, xDer = W - M - CW;
    const ubicar = (lista, x, lado) => {
      const y0 = (H - altoLado(lista.length)) / 2;
      lista.forEach((p, i) => { pos[p.pid] = { x, y: y0 + i * (CH + SEP), w: CW, lado }; });
    };
    ubicar(izq, xIzq, "izq"); ubicar(der, xDer, "der");
    const yc0 = (H - altoCanales) / 2;
    e.canales.forEach((c, i) => {
      const y0 = yc0 + i * (CANAL_H + CANAL_SEP);
      posCanal[c.nombre] = { x0: xIzq + CW + HUECO, x1: xDer - HUECO, y0, y1: y0 + CANAL_H };
    });
  } else {
    const CW = 150, GAP = 10;
    const porFila = Math.max(1, Math.floor((W - 2 * M + GAP) / (CW + GAP)));
    const filas = (n) => Math.ceil(n / porFila);
    const bloque = (n) => filas(n) * CH + (filas(n) - 1) * SEP;
    const anchoReal = Math.min(CW + 30, (W - 2 * M - (porFila - 1) * GAP) / porFila);
    const ubicar = (lista, y0, lado) => lista.forEach((p, i) => {
      const fila = Math.floor(i / porFila), col = i % porFila;
      const enFila = Math.min(porFila, lista.length - fila * porFila);
      const xIni = (W - (enFila * anchoReal + (enFila - 1) * GAP)) / 2;
      pos[p.pid] = { x: xIni + col * (anchoReal + GAP), y: y0 + fila * (CH + SEP), w: anchoReal, lado };
    });
    const yCan = M + bloque(izq.length) + 56;
    ubicar(izq, M, "izq");
    e.canales.forEach((c, i) => {
      const y0 = yCan + i * (CANAL_H + CANAL_SEP);
      posCanal[c.nombre] = { x0: M, x1: W - M, y0, y1: y0 + CANAL_H };
    });
    const yDer = yCan + altoCanales + 56;
    ubicar(der, yDer, "der");
    H = yDer + bloque(der.length) + M;
  }
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);

  let defs = "", flechas = "", canales = "", procesos = "", sobres = "";
  new Set([GRIS_FLECHA, ...Object.values(COLOR_ESTADO)]).forEach((c) => {
    defs += `<marker id="m${c.slice(1)}" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="${c}"/></marker>`;
  });

  // conexiones: los anclajes se reparten sobre el borde del canal
  const anclajes = {};
  e.procesos.forEach((p) => Object.keys(p.canales).forEach((cn) => {
    const k = `${cn}|${pos[p.pid].lado}`;
    (anclajes[k] = anclajes[k] || []).push(p.pid);
  }));
  const rutas = {};
  e.procesos.forEach((p) => {
    const pp = pos[p.pid];
    Object.entries(p.canales).forEach(([cn, tipo]) => {
      const pc = posCanal[cn];
      const lista = anclajes[`${cn}|${pp.lado}`];
      const f = (lista.indexOf(p.pid) + 1) / (lista.length + 1);
      let puntoProc, puntoCanal, d;
      if (!vertical) {
        const yA = pc.y0 + 40 + (pc.y1 - pc.y0 - 70) * f;
        puntoProc = pp.lado === "izq" ? [pp.x + pp.w, pp.y + CH / 2] : [pp.x, pp.y + CH / 2];
        puntoCanal = pp.lado === "izq" ? [pc.x0, yA] : [pc.x1, yA];
      } else {
        const xA = pc.x0 + 20 + (pc.x1 - pc.x0 - 40) * f;
        puntoProc = pp.lado === "izq" ? [pp.x + pp.w / 2, pp.y + CH] : [pp.x + pp.w / 2, pp.y];
        puntoCanal = pp.lado === "izq" ? [xA, pc.y0] : [xA, pc.y1];
      }
      const [a, b] = tipo === "enviar" ? [puntoProc, puntoCanal] : [puntoCanal, puntoProc];
      if (!vertical) { const mx = (a[0] + b[0]) / 2; d = `M${a[0]},${a[1]} C${mx},${a[1]} ${mx},${b[1]} ${b[0]},${b[1]}`; }
      else { const my = (a[1] + b[1]) / 2; d = `M${a[0]},${a[1]} C${a[0]},${my} ${b[0]},${my} ${b[0]},${b[1]}`; }
      const activa = p.vivo && p.op_canal === cn && p.estado !== "Nuevo";
      const color = activa ? COLOR_ESTADO[p.estado] : GRIS_FLECHA;
      const id = `ruta-${p.pid}-${cn}`.replace(/[^\w-]/g, "_");
      rutas[`${p.pid}|${tipo}`] = id;
      flechas += `<path id="${id}" d="${d}" class="svg-flecha${activa ? " activa" : ""}" style="stroke:${color}" marker-end="url(#m${color.slice(1)})"/>`;
    });
  });

  e.canales.forEach((c) => { canales += dibujarCanal(c, posCanal[c.nombre]); });
  e.procesos.forEach((p) => { procesos += dibujarProceso(p, pos[p.pid], pos[p.pid].w, CH); });

  // sobres animados: mensajes enviados / recibidos en el último tick
  if (animar) {
    e.eventos.filter((ev) => ev.tick === e.tick).forEach((ev) => {
      const tipo = ev.texto.startsWith("📤") ? "enviar" : ev.texto.startsWith("📥") ? "recibir" : null;
      const id = tipo && rutas[`${ev.origen}|${tipo}`];
      if (!id) return;
      const dur = Math.min(0.7, Math.max(0.25, retardo() / 1000 * 0.9));
      sobres += `<g><rect x="-8" y="-6" width="16" height="12" rx="2" class="svg-sobre"/><path d="M-8,-6 L0,1 L8,-6" fill="none" stroke="#053D1C" stroke-width="1.2"/>
        <animateMotion dur="${dur}s" fill="freeze"><mpath href="#${id}"/></animateMotion>
        <animate attributeName="opacity" values="1;1;0" keyTimes="0;0.85;1" dur="${dur}s" fill="freeze"/></g>`;
    });
  }

  svg.innerHTML = `<defs>${defs}</defs>${flechas}${canales}${procesos}${sobres}`;
  $$(".svg-proceso", svg).forEach((g) => g.addEventListener("click", () => {
    sim.seleccion = g.dataset.pid;
    $("#selProceso").value = sim.seleccion;
    dibujarDiagrama(sim.estado, false);
  }));
}

let temporizadorAjuste = null;
window.addEventListener("resize", () => {
  clearTimeout(temporizadorAjuste);
  temporizadorAjuste = setTimeout(() => {
    if (sim.estado && !$("#vista-simulador").hidden) dibujarDiagrama(sim.estado, false);
  }, 150);
});

function dibujarProceso(p, pos, CW, CH) {
  const { x, y } = pos;
  const color = COLOR_ESTADO[p.estado];
  const sel = p.pid === sim.seleccion;
  const estadoTxt = t(p.estado);
  const anchoPill = 16 + estadoTxt.length * 6.6;
  const lento = p.lento > 1 ? `<text x="${x + CW - 10}" y="${y + 44}" text-anchor="end" class="svg-chip" fill="#7C4DDB">🐢 ×${p.lento}</text>` : "";
  return `<g class="svg-proceso" data-pid="${esc(p.pid)}">
    <title>${esc(p.pid)} · ${esc(estadoTxt)}${p.motivo ? " — " + esc(tr(p.motivo)) : ""}</title>
    ${sel ? `<rect x="${x - 5}" y="${y - 5}" width="${CW + 10}" height="${CH + 10}" rx="14" fill="none" stroke="#075E29" stroke-width="2" stroke-dasharray="5 4"/>` : ""}
    <rect x="${x}" y="${y}" width="${CW}" height="${CH}" rx="10" class="caja" stroke="${color}"/>
    <rect x="${x}" y="${y}" width="7" height="${CH}" rx="3" fill="${color}"/>
    <text x="${x + 18}" y="${y + 24}" class="svg-pid">${esc(p.pid)}</text>
    <text x="${x + CW - 10}" y="${y + 22}" text-anchor="end" class="svg-rol">${esc(t(NOMBRE_ROL[p.rol]))}</text>
    <rect x="${x + 18}" y="${y + 33}" width="${anchoPill}" height="19" rx="9.5" fill="${color}"/>
    <text x="${x + 18 + anchoPill / 2}" y="${y + 46.5}" text-anchor="middle" class="svg-pill">${esc(estadoTxt)}</text>
    ${lento}
    <text x="${x + 18}" y="${y + 68}" class="svg-op">${esc(recortar(tr(p.operacion), Math.floor((CW - 26) / 7)))}</text>
    <text x="${x + 18}" y="${y + 86}" class="svg-cont">${CW < 165 ? t("{e} env · {r} rec", { e: p.enviados, r: p.recibidos }) : t("env {e} · rec {r} · err {x}", { e: p.enviados, r: p.recibidos, x: p.errores })}</text>
  </g>`;
}

function dibujarCanal(c, pc) {
  const { x0, x1, y0, y1 } = pc;
  const w = x1 - x0;
  let s = `<rect x="${x0}" y="${y0}" width="${w}" height="${y1 - y0}" rx="12" class="svg-canal-caja"/>`;
  s += `<text x="${x0 + 16}" y="${y0 + 24}" class="svg-canal-titulo">${esc(c.nombre)} · ${esc(t(c.tipo_nombre))}</text>`;
  let sub = t("ocupación {o}/{c} {u}", { o: c.ocupacion, c: c.capacidad, u: t(c.unidad) });
  if (c.tipo === "cola") sub += c.por_prioridad ? t(" · ordenada por prioridad") : t(" · FIFO");
  if (c.tipo === "tuberia") sub += t(" · read() de {n} B", { n: c.tam_lectura });
  if (c.tipo === "memoria") sub = (c.sincronizada ? t("con mutex + semáforos") : t("⚠ SIN sincronización")) + " · " + sub;
  s += `<text x="${x0 + 16}" y="${y0 + 42}" class="svg-canal-sub">${esc(sub)}</text>`;
  const frac = c.capacidad ? c.ocupacion / c.capacidad : 0;
  const colorBarra = frac >= 1 ? "#D32F2F" : frac >= 0.75 ? "#E39A0B" : "#0C853B";
  s += `<rect x="${x1 - 110}" y="${y0 + 16}" width="94" height="8" rx="4" fill="#E3EBE6"/>
        <rect x="${x1 - 110}" y="${y0 + 16}" width="${94 * Math.min(1, frac)}" height="8" rx="4" fill="${colorBarra}"/>`;

  const zx0 = x0 + 16, zx1 = x1 - 16, zy0 = y0 + 62, zy1 = y1 - 44;
  const zw = zx1 - zx0;
  if (c.tipo === "tuberia") {
    s += `<rect x="${zx0}" y="${zy0}" width="${zw}" height="${zy1 - zy0}" rx="8" class="svg-celda"/>`;
    s += `<rect x="${zx0}" y="${zy0}" width="${zw * Math.min(1, frac)}" height="${zy1 - zy0}" rx="8" fill="#D6EEDF"/>`;
    const texto = c.buffer.replace(/\n/g, "⏎");
    const maxC = Math.floor((zw - 20) / 7.3);
    s += `<text x="${zx0 + 10}" y="${(zy0 + zy1) / 2 + 4}" class="svg-bytes">${esc(texto ? recortar(texto, maxC) : t("(vacía)"))}</text>`;
    s += `<text x="${zx0}" y="${y1 - 16}" class="svg-mini">${zw > 380 ? t("escritura → flujo de bytes → lectura · ") : ""}${t("mensajes en tránsito: {n}", { n: c.en_transito })}</text>`;
    return s;
  }
  const slots = c.tipo === "cola"
    ? Array.from({ length: c.capacidad }, (_, i) => c.items[i] || null)
    : c.ranuras;
  const visibles = Math.min(slots.length, Math.max(4, Math.floor(zw / 54)));
  const cel = zw / visibles;
  for (let i = 0; i < visibles; i++) {
    const m = slots[i];
    const cx = zx0 + i * cel;
    s += `<rect x="${cx + 3}" y="${zy0}" width="${cel - 6}" height="${zy1 - zy0}" rx="7" class="svg-celda${m ? " llena" : ""}"><title>${m ? esc(t("#{id} {texto} (de {o})", { id: m.id, texto: tr(m.texto), o: m.origen })) : t("vacía")}</title></rect>`;
    if (m) {
      s += `<text x="${cx + cel / 2}" y="${(zy0 + zy1) / 2 - 3}" text-anchor="middle" class="svg-celda-txt">#${m.id}</text>`;
      if (cel > 50) s += `<text x="${cx + cel / 2}" y="${(zy0 + zy1) / 2 + 12}" text-anchor="middle" class="svg-celda-sub">${esc(recortar(tr(m.texto), Math.floor(cel / 6.5)))}${m.prioridad ? " p" + m.prioridad : ""}</text>`;
    }
    if (c.tipo === "memoria") {
      s += `<text x="${cx + cel / 2}" y="${zy1 + 14}" text-anchor="middle" class="svg-mini">${i}</text>`;
      if (i === c.idx_in) s += `<text x="${cx + 8}" y="${zy0 - 5}" class="svg-chip" fill="#0C853B">in ▾</text>`;
      if (i === c.idx_out) s += `<text x="${cx + cel - 8}" y="${zy0 - 5}" text-anchor="end" class="svg-chip" fill="#D32F2F">▾ out</text>`;
    }
  }
  if (slots.length > visibles) {
    s += `<text x="${zx1}" y="${zy1 + 14}" text-anchor="end" class="svg-mini">${t("+{n} ranuras no mostradas", { n: slots.length - visibles })}</text>`;
  }
  if (c.tipo === "cola") {
    s += `<text x="${zx0}" y="${y1 - 16}" class="svg-mini">${t("◀ frente (se recibe)")}</text>
          <text x="${zx1}" y="${y1 - 16}" text-anchor="end" class="svg-mini">${t("final (se envía) ◀")}</text>`;
  } else if (c.sincronizada) {
    const colMutex = c.mutex ? "#D32F2F" : "#0C853B";
    let chips = [[c.mutex ? `mutex: ${c.mutex}` : t("mutex: libre"), colMutex], [t("vacíos = {n}", { n: c.sem_vacios }), "#2F7FD8"],
                 [t("llenos = {n}", { n: c.sem_llenos }), "#7C4DDB"], [t("contador = {n}", { n: c.contador }), "#4A5A52"]];
    const anchoChips = (lista) => lista.reduce((a, [txt]) => a + txt.length * 6.4 + 22, 0);
    if (anchoChips(chips) > zw) {
      chips = [[`🔒 ${c.mutex || t("libre")}`, colMutex], [`${idioma === "en" ? "emp" : "vac"} ${c.sem_vacios}`, "#2F7FD8"],
               [`${idioma === "en" ? "full" : "ll"} ${c.sem_llenos}`, "#7C4DDB"], [`cnt ${c.contador}`, "#4A5A52"]];
    }
    let cx = zx0;
    chips.forEach(([txt, col]) => {
      const ancho = txt.length * 6.4 + 16;
      s += `<rect x="${cx}" y="${y1 - 30}" width="${ancho}" height="20" rx="10" fill="${col}" opacity=".12"/>
            <text x="${cx + ancho / 2}" y="${y1 - 16}" text-anchor="middle" class="svg-chip" fill="${col}">${esc(txt)}</text>`;
      cx += ancho + 6;
    });
  } else {
    s += `<text x="${zx0}" y="${y1 - 16}" class="svg-chip" fill="#D32F2F">${zw > 380 ? t("contador compartido = {n} (sin protección: sujeto a carreras)", { n: c.contador }) : t("contador = {n} (sin protección)", { n: c.contador })}</text>`;
  }
  return s;
}

// --------------------------------------------------- gráfica de ocupación
function dibujarGrafica(e) {
  const svg = $("#graficaOcupacion");
  const W = 1000, H = 150, PX = 34, PY = 10;
  let s = "";
  [0, 0.5, 1].forEach((f) => {
    const y = H - PY - (H - 2 * PY) * f;
    s += `<line x1="${PX}" x2="${W - 6}" y1="${y}" y2="${y}" stroke="#E3EBE6" stroke-width="1" vector-effect="non-scaling-stroke"/>
          <text x="${PX - 6}" y="${y + 4}" text-anchor="end" font-size="11" fill="#5C6E63">${f * 100}%</text>`;
  });
  const h = e.historial;
  if (h.length >= 2) {
    e.canales.forEach((c, i) => {
      const pts = h.map((fila, k) => {
        const x = PX + (W - PX - 8) * k / (h.length - 1);
        const y = H - PY - (H - 2 * PY) * Math.min(1, (fila[c.nombre] || 0) / c.capacidad);
        return `${x.toFixed(1)},${y.toFixed(1)}`;
      }).join(" ");
      const col = COLORES_SERIE[i % COLORES_SERIE.length];
      s += `<polyline points="${PX},${H - PY} ${pts} ${W - 8},${H - PY}" fill="${col}" opacity=".08"/>
            <polyline points="${pts}" fill="none" stroke="${col}" stroke-width="2.2" vector-effect="non-scaling-stroke" stroke-linejoin="round"/>`;
    });
  } else {
    s += `<text x="${W / 2}" y="${H / 2}" text-anchor="middle" font-size="13" fill="#5C6E63">${t("Ejecuta la simulación para ver la evolución del canal")}</text>`;
  }
  svg.innerHTML = s;
  $("#leyendaGrafica").innerHTML = e.canales.map((c, i) =>
    `<span style="color:${COLORES_SERIE[i % COLORES_SERIE.length]};font-weight:700">■ ${esc(c.nombre)}</span>`).join(" &nbsp;");
}

// --------------------------------------------------------------- métricas
const NOMBRES_METRICA = {
  enviados: "Enviados", entregados: "Entregados", en_transito: "Pendientes en el canal", perdidos: "Perdidos",
  rechazados_eagain: "Rechazados (EAGAIN)", descartados_timeout: "Descartados por timeout", epipe: "EPIPE",
  corruptos: "Corruptos", sobrescritos: "Sobrescritos (carrera)", lecturas_invalidas: "Lecturas inválidas",
  duplicados: "Duplicados", max_ocupacion: "Ocupación máxima", latencia_prom: "Latencia promedio (ticks)",
  latencia_max: "Latencia máxima (ticks)",
};
const SIEMPRE = new Set(["enviados", "entregados", "en_transito", "perdidos", "latencia_prom"]);
const MALAS = new Set(["perdidos", "rechazados_eagain", "descartados_timeout", "epipe", "corruptos",
  "sobrescritos", "lecturas_invalidas", "duplicados"]);

function dibujarMetricas(e) {
  const m = e.metricas;
  const canales = Object.values(m.canales);
  const entregados = canales.reduce((a, c) => a + c.entregados, 0);
  const perdidos = canales.reduce((a, c) => a + c.perdidos, 0);
  let html = `<div class="kpis">
      <div class="kpi"><strong>${m.ticks}</strong><span>${t("ticks")}</span></div>
      <div class="kpi"><strong>${entregados}</strong><span>${t("entregados")}</span></div>
      <div class="kpi ${perdidos ? "alerta" : ""}"><strong>${perdidos}</strong><span>${t("perdidos")}</span></div>
      <div class="kpi"><strong>${m.ticks_bloqueado}</strong><span>${t("ticks bloqueado (Σ)")}</span></div>
      <div class="kpi ${m.ticks_espera_activa ? "alerta" : ""}"><strong>${m.ticks_espera_activa}</strong><span>${t("ticks espera activa")}</span></div>
      <div class="kpi"><strong>${e.procesos.filter((p) => p.vivo).length}/${e.procesos.length}</strong><span>${t("procesos activos")}</span></div>
    </div>`;
  e.canales.forEach((c) => {
    const mc = m.canales[c.nombre];
    const filas = Object.entries(NOMBRES_METRICA)
      .filter(([k]) => SIEMPRE.has(k) || mc[k])
      .map(([k, n]) => `<li class="${MALAS.has(k) && mc[k] ? "alerta" : ""}"><span>${t(n)}</span><b>${mc[k]}</b></li>`).join("");
    html += `<div class="grupo-metricas"><h4>${esc(t("Canal {n} · {t}", { n: c.nombre, t: t(c.tipo_nombre) }))}</h4>
      <div class="barra-ocupacion" title="${esc(t("Ocupación {o}/{c}", { o: c.ocupacion, c: c.capacidad }))}"><div style="width:${Math.min(100, 100 * c.ocupacion / c.capacidad)}%"></div></div>
      <ul class="lista-metricas">${filas}</ul></div>`;
  });
  html += `<div class="grupo-metricas"><h4>${t("Procesos")}</h4><table class="tabla-procesos">
    <tr><th>PID</th><th>${t("Estado")}</th><th>${t("Env")}</th><th>${t("Rec")}</th><th>${t("Err")}</th></tr>
    ${e.procesos.map((p) => `<tr title="${esc(tr(p.motivo))}"><td><span class="punto" style="background:${COLOR_ESTADO[p.estado]}"></span>${esc(p.pid)}</td>
      <td>${esc(t(p.estado))}</td><td>${p.enviados}</td><td>${p.recibidos}</td><td>${p.errores}</td></tr>`).join("")}
    </table></div>`;
  $("#metricas").innerHTML = html;
}

function dibujarLeyenda() {
  $("#leyenda").innerHTML = Object.entries(COLOR_ESTADO)
    .map(([n, c]) => `<span><i style="background:${c}"></i>${esc(t(n))}</span>`).join("") +
    `<span><svg width="22" height="12"><rect x="3" y="1" width="16" height="10" rx="2" fill="#FFD84D" stroke="#053D1C"/></svg>${t("mensaje en tránsito")}</span>`;
  $("#flujoEstados").innerHTML = Object.entries(COLOR_ESTADO)
    .map(([n, c]) => `<span style="background:${c}">${esc(t(n))}</span>`).join("");
}

// ===================================================================
//                             EXPERIMENTO
// ===================================================================
let ultimoExperimento = null;

$("#formExperimento").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const { config, errores } = leerFormulario(ev.target);
  if (errores.length) { toast(errores.join("\n"), "error", t("Revisa la carga de trabajo")); return; }
  const falloTick = config.fallo_tick;
  delete config.fallo_tick;
  const boton = ev.submitter || $("button[type=submit]", ev.target);
  boton.disabled = true;
  try {
    const r = await api("/api/experimento", { method: "POST", body: { config, fallo_tick: falloTick } });
    ultimoExperimento = r;
    mostrarExperimento(r);
  } catch (e) { toast(e.message, "error"); }
  finally { boton.disabled = false; }
});

function mostrarExperimento(r) {
  $("#expVacio").hidden = true;
  $("#expResultados").hidden = false;
  $("#btnExpCsv").disabled = false;

  $("#expResumen").innerHTML = r.filas.map((f) => {
    const perfecto = f.Perdidos === 0 && f["Corruptos/carrera"] === 0 && f.Final === "Completado";
    const clase = perfecto ? "" : f.Final === "Estancado" || f.Perdidos > f.programados / 3 ? "mal" : "regular";
    return `<div class="tarjeta-resumen ${clase}"><h4>${esc(t(f.Mecanismo))}</h4>
      <strong>${f.entregados_n}/${f.programados}</strong><span>${esc(t("entregados · {f}", { f: t(f.Final) }))}</span></div>`;
  }).join("");

  const columnas = r.columnas;
  const malo = (col, v) => ["Perdidos", "Corruptos/carrera", "EAGAIN/timeout", "Espera activa"].includes(col) && v > 0;
  const chipFinal = (v) => `<span class="chip ${v === "Completado" ? "ok" : v === "Estancado" ? "mal" : "aviso"}">${esc(t(v))}</span>`;
  $("#tablaExperimento").innerHTML =
    `<thead><tr>${columnas.map((c) => `<th>${esc(t(c))}</th>`).join("")}</tr></thead><tbody>` +
    r.filas.map((f) => `<tr>${columnas.map((c) => c === "Final" ? `<td>${chipFinal(f[c])}</td>`
      : `<td class="${malo(c, f[c]) ? "malo" : ""}">${esc(c === "Mecanismo" ? t(f[c]) : f[c])}</td>`).join("")}</tr>`).join("") + "</tbody>";

  // entregados vs perdidos
  const W = 900, filaH = 40, etiq = 270;
  const maximo = Math.max(...r.filas.map((f) => f.programados), 1);
  let s = "";
  r.filas.forEach((f, i) => {
    const y = 10 + i * filaH, ancho = W - etiq - 90;
    const e_ = ancho * f.entregados_n / maximo, p_ = ancho * f.Perdidos / maximo;
    s += `<text x="0" y="${y + 18}" font-size="14" fill="#1C2A22">${esc(t(f.Mecanismo))}</text>
      <rect x="${etiq}" y="${y + 4}" width="${ancho}" height="20" rx="4" fill="#EEF3F0"/>
      <rect x="${etiq}" y="${y + 4}" width="${e_}" height="20" rx="4" fill="#0C853B"/>
      <rect x="${etiq + e_}" y="${y + 4}" width="${p_}" height="20" fill="#D32F2F"/>
      <text x="${etiq + ancho + 8}" y="${y + 19}" font-size="13" fill="#5C6E63">${f.entregados_n} ✔ ${f.Perdidos} ✖</text>`;
  });
  s += `<g transform="translate(${etiq},${10 + r.filas.length * filaH + 6})" font-size="12" fill="#5C6E63">
    <rect width="12" height="12" fill="#0C853B" rx="2"/><text x="18" y="10">${t("entregados")}</text>
    <rect x="110" width="12" height="12" fill="#D32F2F" rx="2"/><text x="128" y="10">${t("perdidos")}</text></g>`;
  $("#graficaEntregas").innerHTML = `<div class="grafica-barras"><svg viewBox="0 0 ${W} ${r.filas.length * filaH + 40}">${s}</svg></div>`;

  // latencia y ticks totales (cada métrica con su propia escala)
  const metricas = [["Lat. prom", "Latencia promedio (ticks)", "#2F7FD8"], ["Ticks totales", "Ticks hasta terminar", "#075E29"]];
  let s2 = "", y = 0;
  metricas.forEach(([col, titulo, color]) => {
    const max = Math.max(...r.filas.map((f) => Number(f[col])), 1);
    s2 += `<text x="0" y="${y + 14}" font-size="14" font-weight="700" fill="#075E29">${t(titulo)}</text>`;
    y += 22;
    r.filas.forEach((f) => {
      const ancho = (W - etiq - 60) * Number(f[col]) / max;
      s2 += `<text x="0" y="${y + 14}" font-size="14" fill="#1C2A22">${esc(t(f.Mecanismo))}</text>
        <rect x="${etiq}" y="${y + 2}" width="${Math.max(2, ancho)}" height="16" rx="3" fill="${color}"/>
        <text x="${etiq + ancho + 6}" y="${y + 15}" font-size="13" fill="#5C6E63">${f[col]}</text>`;
      y += 24;
    });
    y += 10;
  });
  $("#graficaLatencia").innerHTML = `<div class="grafica-barras"><svg viewBox="0 0 ${W} ${y}">${s2}</svg></div>`;
  $("#listaConclusiones").innerHTML = r.conclusiones.map((c) => `<li>${esc(tr(c.replace(/^•\s*/, "")))}</li>`).join("");
}

$("#btnExpCsv").addEventListener("click", () => {
  if (!ultimoExperimento) return;
  const { columnas, filas } = ultimoExperimento;
  const celda = (c, v) => String(c === "Mecanismo" || c === "Final" ? t(v) : v).replace(/;/g, ",");
  const csv = [columnas.map((c) => t(c)).join(";"), ...filas.map((f) => columnas.map((c) => celda(c, f[c])).join(";"))].join("\r\n");
  const blob = new Blob(["﻿" + csv], { type: "text/csv;charset=utf-8" });
  const a = Object.assign(document.createElement("a"), { href: URL.createObjectURL(blob), download: "experimento_ipc.csv" });
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
});

// ===================================================================
//                              IPC REAL
// ===================================================================
let ultimoReal = null;

$("#formReal").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const { config, errores } = leerFormulario(ev.target);
  if (errores.length) { toast(errores.join("\n"), "error"); return; }
  const boton = $("#btnReal"), estado = $("#estadoReal");
  boton.disabled = true;
  ultimoReal = null;
  estado.textContent = t("⏳ Creando procesos reales y midiendo… (puede tardar unos segundos)");
  try {
    ultimoReal = await api("/api/ipc-real", { method: "POST", body: { n: config.n } });
    mostrarReal(ultimoReal);
  } catch (e) {
    estado.textContent = "";
    toast(e.message, "error", t("IPC real"));
  } finally { boton.disabled = false; }
});

function mostrarReal(r) {
  $("#realResultados").hidden = false;
  const max = Math.max(...r.filas.map((f) => f["Mensajes/s"]), 1);
  const W = 560, etiq = 230;
  let s = "";
  r.filas.forEach((f, i) => {
    const y = 8 + i * 54, ancho = (W - etiq - 20) * f["Mensajes/s"] / max;
    const nombre = esc(tr(f.Mecanismo));
    if (f.Disponible === false) {
      s += `<text x="0" y="${y + 16}" font-size="13" font-weight="600" fill="#1C2A22">${nombre}</text>
        <rect x="${etiq}" y="${y + 6}" width="${W - etiq - 20}" height="22" rx="4" fill="#F3F5F4" stroke="#D9E4DD"/>
        <text x="${etiq + 8}" y="${y + 21}" font-size="12" fill="#5C6E63">${t("No disponible en este servidor")}</text>`;
      return;
    }
    s += `<text x="0" y="${y + 16}" font-size="13" font-weight="600" fill="#1C2A22">${nombre}</text>
      <text x="0" y="${y + 33}" font-size="12" fill="#5C6E63">${f["Tiempo (s)"]} s</text>
      <rect x="${etiq}" y="${y + 6}" width="${Math.max(2, ancho)}" height="22" rx="4" fill="${COLORES_SERIE[i]}"/>
      <text x="${etiq + 8}" y="${y + 21}" font-size="12" font-weight="700" fill="#fff">${formatoNumero(f["Mensajes/s"])} msg/s</text>`;
  });
  $("#graficaReal").innerHTML = `<div class="grafica-barras"><svg viewBox="0 0 ${W} ${r.filas.length * 54 + 10}">${s}</svg></div>
    <p class="pista">${t("{n} mensajes de {b} B · medición real del servidor; varía entre ejecuciones.", { n: formatoNumero(r.n), b: r.tam_mensaje })}</p>
    ${r.filas.some((f) => f.Disponible === false) ? `<p class="pista">${t("ℹ Algunos mecanismos necesitan semáforos POSIX (<code>/dev/shm</code>), que las plataformas <i>serverless</i> como Vercel no ofrecen. Ejecuta la aplicación en local (<code>python main.py</code>) para medirlos.")}</p>` : ""}`;
  $("#consolaReal").textContent = r.salida.map(tr).join("\n");
  $("#estadoReal").textContent = t("✔ Completado en {s} s", { s: r.duracion });
}

// ------------------------------------------------------------ idioma
function cambiarIdioma(nuevo) {
  fijarIdioma(nuevo);
  $("#btnEjecutar").textContent = sim.corriendo ? t("⏸ Pausa") : t("▶ Ejecutar");
  dibujarLeyenda();
  if (sim.escenarios.length) {
    llenarSelectorEscenarios();
    describirEscenario(sim.escenarios.find((e) => e.clave === $("#selEscenario").value));
  }
  if (sim.estado) {
    dibujarTodo(sim.estado, false);
    $("#registro").innerHTML = "";
    agregarEventos(sim.registro || [], true);
  }
  if (ultimoExperimento) mostrarExperimento(ultimoExperimento);
  if (ultimoReal) mostrarReal(ultimoReal);
}
$$("[data-idioma]").forEach((b) => b.addEventListener("click", () => cambiarIdioma(b.dataset.idioma)));

// ------------------------------------------------------------------ inicio
document.addEventListener("click", (ev) => {
  const enlace = ev.target.closest("[data-ir]");
  if (enlace) { ev.preventDefault(); location.hash = enlace.dataset.ir; mostrarVista(enlace.dataset.ir); }
});
aplicarIdiomaEstatico();
$("#btnEjecutar").textContent = t("▶ Ejecutar");
dibujarLeyenda();
mostrarVista(location.hash.slice(1) || "inicio");
cargarEscenarios();
