"""
Backend web de IPC Messenger (Flask).

Expone el motor de simulación del paquete `ipc_sim` como una API REST.
La lógica NO vive aquí: este módulo sólo valida entradas, guarda las
simulaciones activas en memoria y convierte su estado a JSON.

Diseño SIN ESTADO (apto para Vercel / funciones serverless)
-----------------------------------------------------------
El servidor no guarda simulaciones en memoria: en una plataforma serverless
cada petición puede atenderla una instancia distinta. En su lugar el
navegador conserva una «receta» = {escenario, config, ops} y el servidor
reconstruye la simulación reproduciendo las operaciones. Como el motor es
determinista (semilla fija), siempre se llega exactamente al mismo estado.

    ops = [["p", n]                 avanzar n ticks
           ["e"]                    ejecutar hasta terminar o estancarse
           ["f", pid, tipo, factor] inyectar un fallo]

Rutas principales
-----------------
GET  /                      página web (SPA)
GET  /api/escenarios        escenarios predefinidos
POST /api/simular           reconstruye la simulación de una receta y devuelve su estado
POST /api/exportar          evidencia (CSV de eventos o JSON de métricas) de una receta
POST /api/experimento       reto de experimentación (misma carga, 4 mecanismos)
POST /api/ipc-real          IPC real con procesos del sistema operativo
"""
from __future__ import annotations

import csv
import io
import os
import threading
import time
from dataclasses import asdict, fields

from flask import Flask, Response, jsonify, render_template, request

from ipc_sim import ESCENARIOS, POR_CLAVE, ConfigSimulacion, Simulador
from ipc_sim.experimento import COLUMNAS, comparar, conclusiones
from ipc_sim.mecanismos import ColaMensajes, MemoriaCompartida, NOMBRES_MECANISMO, Tuberia

MAX_EVENTOS_RESPUESTA = 600
MAX_OPS = 3000                 # operaciones por receta
MAX_PASOS = 25000              # ticks totales que se pueden reproducir por petición
MAX_HISTORIAL = 400

ASIGNATURA = "Sistemas Operativos"
DOCENTE = "Álvaro Salamanca"            # Ing. Álvaro Salamanca
INTEGRANTES = [
    "Jefersson Hernando Rivera Peñaranda",
    "Victor Manuel Ortega Blanco",
    "Cristian Miranda Zuluaga",
]

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Los archivos estáticos viven en /public: en Vercel los sirve directamente su CDN
# y en local los sirve Flask en la misma ruta (/static/...).
app = Flask(__name__, static_folder=os.path.join(RAIZ, "public", "static"),
            static_url_path="/static", template_folder="templates")
app.json.ensure_ascii = False
app.json.sort_keys = False

_candado_real = threading.Lock()


class ErrorEntrada(Exception):
    def __init__(self, errores):
        super().__init__("; ".join(errores))
        self.errores = errores if isinstance(errores, list) else [errores]


@app.errorhandler(ErrorEntrada)
def _error_entrada(e: ErrorEntrada):
    return jsonify({"ok": False, "errores": e.errores}), 400


@app.errorhandler(404)
def _no_encontrado(_e):
    if request.path.startswith("/api/"):
        return jsonify({"ok": False, "errores": ["Recurso no encontrado."]}), 404
    return _no_encontrado_html()


def _no_encontrado_html():
    return render_template("index.html", integrantes=INTEGRANTES,
                           asignatura=ASIGNATURA, docente=DOCENTE), 404


# ------------------------------------------------------------- utilidades
CAMPOS_CONFIG = {f.name: f.type for f in fields(ConfigSimulacion)}
CAMPOS_BOOL = {"bloqueante", "sincronizada", "por_prioridad"}


def _config_desde_json(datos: dict | None, base: ConfigSimulacion | None = None) -> ConfigSimulacion:
    """Construye y valida una configuración a partir del JSON recibido."""
    base = base or ConfigSimulacion()
    if datos is None:
        return base
    if not isinstance(datos, dict):
        raise ErrorEntrada(["La configuración debe ser un objeto JSON."])
    valores = asdict(base)
    errores = []
    for clave, valor in datos.items():
        if clave not in CAMPOS_CONFIG:
            errores.append(f"Campo desconocido: «{clave}».")
            continue
        if clave in CAMPOS_BOOL:
            if not isinstance(valor, bool):
                errores.append(f"«{clave}» debe ser verdadero o falso.")
                continue
        elif clave == "mecanismo":
            if valor not in NOMBRES_MECANISMO:
                errores.append(f"Mecanismo inválido: «{valor}».")
                continue
        else:
            if isinstance(valor, str) and valor.strip().lstrip("-").isdigit():
                valor = int(valor)
            if isinstance(valor, bool) or not isinstance(valor, int):
                errores.append(f"«{clave}» debe ser un número entero.")
                continue
        valores[clave] = valor
    if errores:
        raise ErrorEntrada(errores)
    cfg = ConfigSimulacion(**valores)
    errores = cfg.validar()
    if errores:
        raise ErrorEntrada(errores)
    return cfg


def _json() -> dict:
    datos = request.get_json(silent=True)
    if datos is None:
        datos = {}
    if not isinstance(datos, dict):
        raise ErrorEntrada(["El cuerpo de la petición debe ser un objeto JSON."])
    return datos


def _entero(datos: dict, clave: str, defecto: int, minimo: int, maximo: int) -> int:
    valor = datos.get(clave, defecto)
    if isinstance(valor, bool) or not isinstance(valor, int):
        raise ErrorEntrada([f"«{clave}» debe ser un número entero."])
    if not minimo <= valor <= maximo:
        raise ErrorEntrada([f"«{clave}» debe estar entre {minimo} y {maximo}."])
    return valor


# --------------------------------------------------------- serialización
def _serializar_canal(nombre, c) -> dict:
    base = {
        "nombre": nombre, "tipo": c.tipo, "tipo_nombre": NOMBRES_MECANISMO[c.tipo],
        "capacidad": c.capacidad, "unidad": c.unidad, "ocupacion": c.ocupacion(),
        "en_transito": c.en_transito(),
    }
    if isinstance(c, ColaMensajes):
        base.update(por_prioridad=c.por_prioridad,
                    items=[{"id": m.id, "texto": m.contenido, "origen": m.origen,
                            "prioridad": m.prioridad} for m in c.buf])
    elif isinstance(c, Tuberia):
        base.update(buffer=c.buf, tam_lectura=c.tam_lectura)
    elif isinstance(c, MemoriaCompartida):
        base.update(sincronizada=c.sincronizada, idx_in=c.idx_in, idx_out=c.idx_out,
                    contador=c.contador, sem_vacios=c.sem_vacios, sem_llenos=c.sem_llenos,
                    mutex=c.mutex,
                    ranuras=[None if r is None else {"id": r.id, "texto": r.contenido, "origen": r.origen}
                             for r in c.ranuras])
    return base


def _serializar_proceso(p) -> dict:
    canales = {}
    for a in p.programa:
        if a.canal and a.canal not in canales:
            canales[a.canal] = a.tipo
    op = p.descripcion_op()
    if p.op is not None and p.op.tipo == "computar":
        op = f"compute ({p.op_restante} rest.)"
    return {
        "pid": p.pid, "rol": p.rol, "estado": p.estado.value, "vivo": p.vivo,
        "operacion": op, "op_tipo": p.op.tipo if p.op else None,
        "op_canal": p.op.canal if p.op else None,
        "enviados": p.enviados, "recibidos": p.recibidos, "errores": p.errores,
        "ticks_bloqueado": p.ticks_bloqueado, "ticks_espera_activa": p.ticks_espera_activa,
        "lento": p.lento, "motivo": p.motivo, "canales": canales,
    }


def _estado(sim: Simulador, desde: int | None = None) -> dict:
    total = sim.eventos_total
    if isinstance(desde, bool) or not isinstance(desde, int) or desde < 0 or desde > total:
        desde = max(0, total - MAX_EVENTOS_RESPUESTA)
    faltan = min(total - desde, len(sim.eventos), MAX_EVENTOS_RESPUESTA)
    eventos = sim.eventos[len(sim.eventos) - faltan:] if faltan else []
    return {
        "ok": True,
        "tick": sim.tick,
        "finalizado": sim.finalizado,
        "estancado": sim.estancado,
        "diagnostico": sim.diagnostico,
        "config": asdict(sim.config),
        "procesos": [_serializar_proceso(p) for p in sim.procesos],
        "canales": [_serializar_canal(n, c) for n, c in sim.canales.items()],
        "metricas": sim.metricas(),
        "historial": sim.historial[-MAX_HISTORIAL:],
        "eventos": [{"tick": e.tick, "origen": e.origen, "texto": e.texto, "nivel": e.nivel}
                    for e in eventos],
        "eventos_total": total,
        "eventos_reinicio": desde < total - faltan,   # se perdieron eventos intermedios
    }


# ------------------------------------------------------------------ rutas
@app.get("/")
def inicio():
    return render_template("index.html", integrantes=INTEGRANTES,
                           asignatura=ASIGNATURA, docente=DOCENTE)


@app.get("/api/escenarios")
def escenarios():
    return jsonify([{
        "clave": e.clave, "titulo": e.titulo, "tipo": e.tipo, "descripcion": e.descripcion,
        "esperado": e.esperado, "config": asdict(ConfigSimulacion(**e.config)),
        "fallos": e.fallos, "topologia_propia": e.constructor is not None,
    } for e in ESCENARIOS])


def _crear(clave, config_json) -> Simulador:
    esc = None
    if clave:
        esc = POR_CLAVE.get(clave)
        if esc is None:
            raise ErrorEntrada([f"Escenario desconocido: «{clave}»."])
    try:
        if esc and config_json is None:
            return esc.crear()
        cfg = _config_desde_json(config_json)
        if esc and asdict(cfg) == asdict(ConfigSimulacion(**esc.config)):
            return esc.crear()                    # sin cambios: incluye sus fallos programados
        if esc and esc.constructor:
            return esc.constructor(cfg)           # misma topología, otros parámetros
        return Simulador(cfg)
    except ValueError as e:
        raise ErrorEntrada(str(e).split("\n"))


def _reconstruir(datos: dict) -> tuple[Simulador, str]:
    """Crea la simulación de la receta y reproduce sus operaciones en orden.
    Devuelve la simulación y el mensaje de la última operación (si fue un fallo)."""
    sim = _crear(datos.get("escenario"), datos.get("config"))
    ops = datos.get("ops", [])
    if not isinstance(ops, list) or len(ops) > MAX_OPS:
        raise ErrorEntrada([f"«ops» debe ser una lista de hasta {MAX_OPS} operaciones."])
    pasos, mensaje = 0, ""
    for i, op in enumerate(ops):
        if not isinstance(op, list) or not op or op[0] not in ("p", "e", "f"):
            raise ErrorEntrada([f"Operación inválida en la posición {i}: {op!r}."])
        mensaje = ""
        if op[0] == "p":
            n = op[1] if len(op) == 2 else None
            if isinstance(n, bool) or not isinstance(n, int) or not 1 <= n <= 5000:
                raise ErrorEntrada([f"Operación de pasos inválida en la posición {i}."])
            pasos += n
            if pasos > MAX_PASOS:
                raise ErrorEntrada([f"La simulación supera el máximo de {MAX_PASOS} ticks reproducibles."])
            for _ in range(n):
                if not sim.paso():
                    break
        elif op[0] == "e":
            sim.ejecutar()
        else:
            if len(op) != 4 or op[2] not in ("caer", "no_responder", "lento", "recuperar") \
                    or isinstance(op[3], bool) or not isinstance(op[3], int) or not 2 <= op[3] <= 20:
                raise ErrorEntrada([f"Operación de fallo inválida en la posición {i}."])
            try:
                mensaje = sim.inyectar_fallo(op[1], op[2], op[3])
            except KeyError:
                raise ErrorEntrada([f"No existe el proceso «{op[1]}»."])
    return sim, mensaje


@app.post("/api/simular")
def simular():
    datos = _json()
    sim, mensaje = _reconstruir(datos)
    estado = _estado(sim, datos.get("desde"))
    estado["mensaje"] = mensaje
    return jsonify(estado)


@app.post("/api/exportar")
def exportar():
    datos = _json()
    sim, _ = _reconstruir(datos)
    formato = datos.get("formato", "csv")
    nombre = f"ipc_messenger_tick{sim.tick}"
    if formato == "json":
        cuerpo = {"software": "IPC Messenger", "desarrollado_por": INTEGRANTES,
                  "asignatura": ASIGNATURA, "docente": f"Ing. {DOCENTE}",
                  "programa": "Ingeniería de Sistemas · Universidad Simón Bolívar, sede Cúcuta",
                  "tipo": "simulación (ticks lógicos, no mediciones reales)",
                  "configuracion": asdict(sim.config), "metricas": sim.metricas()}
        r = jsonify(cuerpo)
        r.headers["Content-Disposition"] = f"attachment; filename={nombre}_metricas.json"
        return r
    salida = io.StringIO()
    w = csv.writer(salida, delimiter=";")
    w.writerow(["tick", "origen", "nivel", "evento"])
    for e in sim.eventos:
        w.writerow([e.tick, e.origen, e.nivel, e.texto])
    return Response("\ufeff" + salida.getvalue(), mimetype="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f"attachment; filename={nombre}_eventos.csv"})


@app.post("/api/experimento")
def experimento():
    datos = _json()
    base = _config_desde_json(datos.get("config"), ConfigSimulacion(
        n_emisores=3, n_receptores=2, mensajes_por_emisor=6, capacidad=4,
        tiempo_receptor=2, max_ticks=5000))
    fallo_tick = _entero(datos, "fallo_tick", 0, 0, 500)
    try:
        filas = comparar(base, fallo_receptor_tick=fallo_tick)
    except ValueError as e:
        raise ErrorEntrada(str(e).split("\n"))
    return jsonify({
        "ok": True, "columnas": COLUMNAS,
        "filas": [{k: v for k, v in f.items() if not k.startswith("_")} |
                  {"entregados_n": f["_entregados"], "programados": f["_programados"]} for f in filas],
        "conclusiones": conclusiones(filas, base),
        "config": asdict(base), "fallo_tick": fallo_tick,
    })


@app.post("/api/ipc-real")
def ipc_real_ruta():
    datos = _json()
    n = _entero(datos, "n", 20000, 100, 200000)
    if not _candado_real.acquire(blocking=False):
        raise ErrorEntrada(["Ya hay una prueba de IPC real en ejecución. Espera a que termine."])
    try:
        from ipc_sim import ipc_real
        lineas: list[str] = []
        t0 = time.perf_counter()
        filas = ipc_real.ejecutar_todo(n, reportar=lineas.append)
        return jsonify({"ok": True, "n": n, "tam_mensaje": ipc_real.TAM_MSG, "filas": filas,
                        "salida": lineas, "duracion": round(time.perf_counter() - t0, 3)})
    except Exception as e:  # noqa: BLE001 — se informa al cliente
        raise ErrorEntrada([f"Error ejecutando IPC real: {type(e).__name__}: {e}"])
    finally:
        _candado_real.release()


def ejecutar(host: str = "127.0.0.1", puerto: int = 5000, abrir_navegador: bool = True):
    if abrir_navegador:
        import webbrowser
        threading.Timer(1.2, lambda: webbrowser.open(f"http://{host}:{puerto}")).start()
    print(f"\n  IPC Messenger disponible en  http://{host}:{puerto}\n  (Ctrl+C para detener)\n")
    app.run(host=host, port=puerto, debug=False, threaded=True)
