"""
Motor de simulación por ticks (tiempo discreto).

En cada tick, cada proceso vivo ejecuta como máximo UN paso de su
operación actual. El orden de atención rota en cada tick para no
favorecer siempre al mismo proceso. Los procesos bloqueados reintentan su
operación en cada tick (equivale a ser despertados cuando cambia el
recurso). El simulador detecta "estancamiento" cuando pasa una ventana de
ticks sin ningún progreso y explica qué espera cada proceso.

NOTA: los tiempos son ticks lógicos de la simulación, NO mediciones reales.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Optional

from .mecanismos import Mecanismo, crear_mecanismo, MemoriaCompartida
from .modelo import Accion, Estado, Mensaje, Proceso, Resultado


@dataclass
class ConfigSimulacion:
    mecanismo: str = "cola"          # cola | tuberia | memoria
    capacidad: int = 4               # mensajes (cola), bytes (tubería), ranuras (memoria)
    n_emisores: int = 2
    n_receptores: int = 1
    mensajes_por_emisor: int = 5
    intervalo_emisor: int = 1        # ticks de cómputo entre envíos
    tiempo_receptor: int = 2         # ticks de procesamiento por mensaje recibido
    bloqueante: bool = True
    timeout: int = 0                 # 0 = sin timeout (espera indefinida)
    sincronizada: bool = True        # sólo memoria compartida
    tam_lectura: int = 64            # sólo tubería
    por_prioridad: bool = False      # sólo cola
    variacion: int = 0               # +/- ticks aleatorios en los cómputos
    semilla: int = 42
    max_ticks: int = 500
    ventana_estancamiento: int = 8

    def validar(self) -> list[str]:
        errores = []
        if self.mecanismo not in ("cola", "tuberia", "memoria"):
            errores.append("Mecanismo inválido.")
        lim = {"capacidad": (1, 4096), "n_emisores": (1, 8), "n_receptores": (1, 8),
               "mensajes_por_emisor": (1, 200), "intervalo_emisor": (1, 50),
               "tiempo_receptor": (1, 50), "timeout": (0, 500), "tam_lectura": (1, 4096),
               "variacion": (0, 10), "max_ticks": (10, 20000),
               "ventana_estancamiento": (2, 100)}
        for campo, (lo, hi) in lim.items():
            v = getattr(self, campo)
            if not isinstance(v, int) or isinstance(v, bool):
                errores.append(f"'{campo}' debe ser un número entero.")
            elif not lo <= v <= hi:
                errores.append(f"'{campo}' debe estar entre {lo} y {hi} (recibido {v}).")
        if self.mecanismo == "tuberia" and isinstance(self.capacidad, int) and self.capacidad < 20:
            errores.append("La tubería necesita al menos 20 bytes para contener un mensaje.")
        return errores


@dataclass
class EventoFallo:
    tick: int
    pid: str
    tipo: str          # 'caer' | 'no_responder' | 'recuperar' | 'lento'
    factor: int = 3


@dataclass
class Evento:
    tick: int
    origen: str
    texto: str
    nivel: str = "info"   # info | ok | bloqueo | alerta | error


class Simulador:
    def __init__(self, config: Optional[ConfigSimulacion] = None, *,
                 procesos: Optional[list[Proceso]] = None,
                 canales: Optional[dict[str, Mecanismo]] = None,
                 fallos: Optional[list[EventoFallo]] = None):
        self.config = config or ConfigSimulacion()
        errores = self.config.validar()
        if errores:
            raise ValueError("\n".join(errores))
        self.rng = random.Random(self.config.semilla)
        self.tick = 0
        self.eventos: list[Evento] = []
        self.eventos_total = 0          # contador global (los eventos viejos se recortan)
        self.fallos_programados = list(fallos or [])
        self.ultimo_progreso = 0
        self.estancado = False
        self.diagnostico = ""
        self.finalizado = False
        self._id_msg = 0
        self.historial: list[dict] = []   # ocupación por tick (para gráficas)
        if procesos is not None and canales is not None:
            self.procesos = procesos
            self.canales = canales
        else:
            self.canales, self.procesos = self._construir_productor_consumidor()
        self._roles_canal = self._calcular_roles()
        self.log(f"Simulación creada: {len(self.procesos)} procesos, "
                 f"canales: {', '.join(self.canales)}", origen="SIM")

    # ------------------------------------------------------------------ montaje
    def _construir_productor_consumidor(self):
        c = self.config
        canal = crear_mecanismo(c.mecanismo, "C1", c.capacidad,
                                sincronizada=c.sincronizada, tam_lectura=c.tam_lectura,
                                por_prioridad=c.por_prioridad)
        procesos = []
        for i in range(1, c.n_emisores + 1):
            prog = []
            for k in range(1, c.mensajes_por_emisor + 1):
                prog.append(Accion("enviar", "C1", f"E{i}-m{k}"))
                if k < c.mensajes_por_emisor:
                    prog.append(Accion("computar", ticks=c.intervalo_emisor))
            procesos.append(Proceso(f"E{i}", "emisor", prog))
        for j in range(1, c.n_receptores + 1):
            prog = [Accion("recibir", "C1"), Accion("computar", ticks=c.tiempo_receptor)]
            procesos.append(Proceso(f"R{j}", "receptor", prog, repetir=True))
        return {"C1": canal}, procesos

    def _calcular_roles(self):
        roles = {n: {"emisores": set(), "receptores": set()} for n in self.canales}
        for p in self.procesos:
            for a in p.programa:
                if a.tipo == "enviar":
                    if a.canal not in self.canales:
                        raise ValueError(f"{p.pid} usa el canal inexistente '{a.canal}'")
                    roles[a.canal]["emisores"].add(p.pid)
                elif a.tipo == "recibir":
                    if a.canal not in self.canales:
                        raise ValueError(f"{p.pid} usa el canal inexistente '{a.canal}'")
                    roles[a.canal]["receptores"].add(p.pid)
        return roles

    # ------------------------------------------------------------ consultas
    def proceso(self, pid: str) -> Proceso:
        for p in self.procesos:
            if p.pid == pid:
                return p
        raise KeyError(f"No existe el proceso {pid}")

    def emisores_terminados(self, canal: str) -> bool:
        """True si ningún emisor del canal puede volver a escribir.
        (Un proceso 'No responde' sigue vivo: podría recuperarse.)"""
        return all(not self.proceso(pid).vivo for pid in self._roles_canal[canal]["emisores"])

    def receptores_vivos(self, canal: str) -> bool:
        return any(self.proceso(pid).vivo for pid in self._roles_canal[canal]["receptores"])

    def log(self, texto: str, nivel: str = "info", origen: str = "") -> None:
        self.eventos.append(Evento(self.tick, origen, texto, nivel))
        self.eventos_total += 1
        if len(self.eventos) > 5000:
            del self.eventos[:1000]

    # --------------------------------------------------------------- fallos
    def inyectar_fallo(self, pid: str, tipo: str, factor: int = 3) -> str:
        p = self.proceso(pid)
        if tipo == "caer":
            if not p.vivo:
                return f"{pid} ya no está activo ({p.estado.value})."
            p.estado = Estado.CAIDO
            p.motivo = "fallo inyectado (crash)"
            extra = ""
            for canal in self.canales.values():
                if isinstance(canal, MemoriaCompartida) and canal.mutex == pid:
                    extra = " ¡Murió con el mutex tomado!"
            self.log(f"💥 {pid} se cae (crash).{extra}", "error", pid)
        elif tipo == "no_responder":
            if not p.vivo or p.estado == Estado.NO_RESPONDE:
                return f"{pid} no puede pasar a 'No responde' desde {p.estado.value}."
            p.datos["estado_previo"] = p.estado
            p.estado = Estado.NO_RESPONDE
            p.motivo = "congelado (no responde)"
            self.log(f"🧊 {pid} deja de responder.", "alerta", pid)
        elif tipo == "recuperar":
            if p.estado == Estado.NO_RESPONDE:
                p.estado = p.datos.pop("estado_previo", Estado.LISTO)
                if p.estado == Estado.EJECUCION:
                    p.estado = Estado.LISTO
                p.motivo = ""
                self.log(f"✅ {pid} vuelve a responder.", "ok", pid)
            elif p.lento > 1:
                p.lento = 1
                self.log(f"✅ {pid} recupera su velocidad normal.", "ok", pid)
            else:
                return f"{pid} no tiene un fallo recuperable (un proceso caído no se recupera)."
        elif tipo == "lento":
            if not p.vivo:
                return f"{pid} no está activo."
            p.lento = max(2, factor)
            self.log(f"🐢 {pid} se vuelve lento (1 paso cada {p.lento} ticks).", "alerta", pid)
        else:
            return f"Tipo de fallo desconocido: {tipo}"
        self.estancado = False
        self.ultimo_progreso = self.tick
        return ""

    # ------------------------------------------------------------- ejecución
    def _nuevo_id(self) -> int:
        self._id_msg += 1
        return self._id_msg

    def _variar(self, n: int) -> int:
        if self.config.variacion:
            n += self.rng.randint(-self.config.variacion, self.config.variacion)
        return max(1, n)

    def _siguiente_accion(self, p: Proceso) -> bool:
        if p.pc >= len(p.programa):
            if p.repetir and p.programa:
                p.pc = 0
            else:
                p.estado = Estado.TERMINADO
                p.motivo = "programa completado"
                self.log(f"🏁 {p.pid} terminó su programa.", "ok", p.pid)
                return False
        p.op = p.programa[p.pc]
        p.pc += 1
        p.espera = 0
        p.ctx.clear()
        if p.op.tipo == "computar":
            p.op_restante = self._variar(p.op.ticks)
        elif p.op.tipo == "enviar":
            p.seq += 1
            canal = self.canales[p.op.canal]
            prioridad = self.rng.randint(0, 3) if getattr(canal, "por_prioridad", False) else 0
            p.op_mensaje = Mensaje(self._nuevo_id(), p.pid, p.op.contenido, self.tick, prioridad)
        return True

    def _terminar_op(self, p: Proceso) -> None:
        p.op = None
        p.op_mensaje = None
        p.espera = 0
        p.ctx.clear()

    def paso(self) -> bool:
        """Avanza un tick. Devuelve False si la simulación ya no puede avanzar."""
        if self.finalizado:
            return False
        self.tick += 1
        progreso = False

        for f in [f for f in self.fallos_programados if f.tick == self.tick]:
            msg = self.inyectar_fallo(f.pid, f.tipo, f.factor)
            if msg:
                self.log(msg, "alerta", "SIM")

        for p in self.procesos:
            if p.estado == Estado.EJECUCION:
                p.estado = Estado.LISTO

        n = len(self.procesos)
        inicio = (self.tick - 1) % n
        orden = self.procesos[inicio:] + self.procesos[:inicio]

        for p in orden:
            if not p.vivo or p.estado == Estado.NO_RESPONDE:
                continue
            if p.lento > 1 and self.tick % p.lento != 0:
                continue
            if p.estado == Estado.NUEVO:
                p.estado = Estado.LISTO
                self.log(f"{p.pid} admitido (Nuevo → Listo).", "info", p.pid)
                progreso = True
                continue
            if p.op is None and not self._siguiente_accion(p):
                progreso = True
                continue
            if self._ejecutar(p):
                progreso = True

        ocup = {n: c.ocupacion() for n, c in self.canales.items()}
        self.historial.append({"tick": self.tick, **ocup})

        if progreso:
            self.ultimo_progreso = self.tick
            self.estancado = False
        vivos = [p for p in self.procesos if p.vivo]
        if not vivos:
            self.finalizado = True
            self.log("■ Todos los procesos finalizaron.", "ok", "SIM")
            return False
        if self.tick - self.ultimo_progreso >= self.config.ventana_estancamiento and not self.estancado:
            self.estancado = True
            self.diagnostico = self._diagnosticar()
            self.log("⛔ ESTANCAMIENTO: " + self.diagnostico, "error", "SIM")
        if self.tick >= self.config.max_ticks:
            self.finalizado = True
            self.log(f"■ Se alcanzó el límite de {self.config.max_ticks} ticks.", "alerta", "SIM")
            return False
        return not self.estancado

    def _ejecutar(self, p: Proceso) -> bool:
        op = p.op
        if op.tipo == "computar":
            p.estado = Estado.EJECUCION
            p.op_restante -= 1
            if p.op_restante <= 0:
                self._terminar_op(p)
            return True

        canal = self.canales[op.canal]
        if op.tipo == "enviar":
            res, info = canal.enviar(p, p.op_mensaje, self)
        else:
            res, info = canal.recibir(p, self)

        if res == Resultado.OK:
            p.estado = Estado.EJECUCION
            if op.tipo == "enviar":
                p.enviados += 1
                self.log(f"📤 {info}", "ok", p.pid)
            else:
                p.recibidos += 1
                self.log(f"📥 recibe {info} (latencia {self.tick - info.tick_envio} ticks)", "ok", p.pid)
            self._terminar_op(p)
            return True

        if res == Resultado.SIGUE:
            p.estado = Estado.EJECUCION
            p.espera = 0
            self.log(info, "info", p.pid)
            return True

        if res == Resultado.EOF:
            p.estado = Estado.TERMINADO
            p.motivo = "EOF: " + info
            self.log(f"🏁 {p.pid} termina: {info}", "ok", p.pid)
            self._terminar_op(p)
            return True

        if res == Resultado.ERROR:
            p.errores += 1
            if "EPIPE" in info:
                canal.cancelar(p)
                p.estado = Estado.TERMINADO
                p.motivo = "terminado por SIGPIPE"
                self.log(f"☠ {p.pid}: {info}", "error", p.pid)
            else:
                p.estado = Estado.EJECUCION
                self.log(f"✖ {p.pid}: {info}", "error", p.pid)
            self._terminar_op(p)
            return True

        # BLOQUEA o ESPERA_ACTIVA
        if res == Resultado.BLOQUEA and not self.config.bloqueante:
            if op.tipo == "enviar":
                canal.stats.rechazados += 1
                canal.cancelar(p)
                p.errores += 1
                self.log(f"↩ EAGAIN: {info}; mensaje {p.op_mensaje} descartado", "alerta", p.pid)
                p.estado = Estado.EJECUCION
                self._terminar_op(p)
                return True
            res = Resultado.ESPERA_ACTIVA   # recepción no bloqueante = sondeo
            info = f"sondeo (EAGAIN): {info}"

        p.espera += 1
        if res == Resultado.ESPERA_ACTIVA:
            p.estado = Estado.ESPERA_ACTIVA
            p.ticks_espera_activa += 1
        else:
            p.estado = Estado.BLOQUEADO
            p.ticks_bloqueado += 1
        if p.espera == 1:
            self.log(f"⏸ {p.pid} espera: {info}", "bloqueo", p.pid)
        p.motivo = info

        if self.config.timeout and p.espera >= self.config.timeout:
            canal.cancelar(p)
            p.errores += 1
            p.estado = Estado.LISTO
            p.motivo = ""
            if op.tipo == "enviar":
                canal.stats.descartados_timeout += 1
                self.log(f"⌛ TIMEOUT tras {p.espera} ticks: {p.op_mensaje} descartado "
                         f"(¿receptor no responde?)", "alerta", p.pid)
            else:
                self.log(f"⌛ TIMEOUT tras {p.espera} ticks esperando mensaje", "alerta", p.pid)
            self._terminar_op(p)
            return True
        return False

    def ejecutar(self, max_pasos: Optional[int] = None) -> "Simulador":
        """Corre hasta terminar, estancarse o alcanzar max_pasos."""
        pasos = 0
        while self.paso():
            pasos += 1
            if max_pasos and pasos >= max_pasos:
                break
        return self

    # --------------------------------------------------------- diagnóstico
    def _diagnosticar(self) -> str:
        partes = []
        esperas = {}
        for p in self.procesos:
            if p.estado in (Estado.BLOQUEADO, Estado.ESPERA_ACTIVA):
                partes.append(f"{p.pid} → {p.descripcion_op()} [{p.motivo}]")
                esperas[p.pid] = p
            elif p.estado == Estado.NO_RESPONDE:
                partes.append(f"{p.pid} no responde")
        causas = []
        for canal_n, canal in self.canales.items():
            roles = self._roles_canal[canal_n]
            rec_vivos = [pid for pid in roles["receptores"] if self.proceso(pid).vivo
                         and self.proceso(pid).estado != Estado.NO_RESPONDE]
            emi_bloq = [pid for pid in roles["emisores"] if pid in esperas
                        and esperas[pid].op and esperas[pid].op.tipo == "enviar"]
            if emi_bloq and not rec_vivos:
                causas.append(f"en {canal_n} los emisores esperan espacio pero ningún receptor "
                              f"está atendiendo (caído o sin responder)")
            if isinstance(canal, MemoriaCompartida) and canal.mutex:
                dueno = self.proceso(canal.mutex)
                if not dueno.vivo or dueno.estado == Estado.NO_RESPONDE:
                    causas.append(f"el mutex de {canal_n} lo retiene {dueno.pid} "
                                  f"({dueno.estado.value}) y nunca será liberado")
        ciclo = self._ciclo_espera()
        if ciclo:
            causas.append("INTERBLOQUEO (espera circular): " + " → ".join(ciclo))
        texto = "; ".join(partes) if partes else "sin procesos activos que avancen"
        if causas:
            texto += ". Causa: " + "; ".join(causas)
        return texto

    def _ciclo_espera(self) -> list[str]:
        """Grafo de espera: P espera a Q si P recibe de un canal donde sólo Q emite
        (o P envía a un canal lleno que sólo Q lee). Busca un ciclo."""
        grafo: dict[str, set[str]] = {}
        for p in self.procesos:
            if p.estado != Estado.BLOQUEADO or not p.op:
                continue
            canal = self.canales[p.op.canal]
            if isinstance(canal, MemoriaCompartida) and canal.mutex and canal.mutex != p.pid \
                    and "mutex" in p.motivo:
                grafo[p.pid] = {canal.mutex}      # espera al dueño del mutex
                continue
            roles = self._roles_canal[p.op.canal]
            otros = roles["emisores"] if p.op.tipo == "recibir" else roles["receptores"]
            grafo[p.pid] = {q for q in otros if q != p.pid}
        visitado, pila = set(), []

        def dfs(u):
            if u in pila:
                return pila[pila.index(u):] + [u]
            if u in visitado:
                return None
            visitado.add(u)
            pila.append(u)
            for v in grafo.get(u, ()):
                if v in grafo:
                    r = dfs(v)
                    if r:
                        return r
            pila.pop()
            return None

        for nodo in grafo:
            r = dfs(nodo)
            if r:
                return r
        return []

    # ----------------------------------------------------------- métricas
    def metricas(self) -> dict:
        canales = {}
        for n, c in self.canales.items():
            s = c.stats
            canales[n] = {
                "mecanismo": c.tipo,
                "enviados": s.enviados,
                "entregados": s.entregados,
                "en_transito": c.en_transito(),
                "rechazados_eagain": s.rechazados,
                "descartados_timeout": s.descartados_timeout,
                "epipe": s.epipe,
                "corruptos": s.corruptos,
                "sobrescritos": s.sobrescritos,
                "lecturas_invalidas": s.lecturas_invalidas,
                "duplicados": s.duplicados,
                "perdidos": max(0, s.enviados - s.entregados - c.en_transito()),
                "max_ocupacion": s.max_ocupacion,
                "capacidad": c.capacidad,
                "latencia_prom": round(s.latencia_prom, 2),
                "latencia_max": s.latencia_max,
            }
        intentos = sum(1 for p in self.procesos for a in p.programa if a.tipo == "enviar" and not p.repetir)
        return {
            "ticks": self.tick,
            "estancado": self.estancado,
            "diagnostico": self.diagnostico,
            "mensajes_programados": intentos,
            "ticks_bloqueado": sum(p.ticks_bloqueado for p in self.procesos),
            "ticks_espera_activa": sum(p.ticks_espera_activa for p in self.procesos),
            "procesos": {p.pid: {"estado": p.estado.value, "enviados": p.enviados,
                                 "recibidos": p.recibidos, "bloqueado": p.ticks_bloqueado,
                                 "espera_activa": p.ticks_espera_activa,
                                 "errores": p.errores, "motivo": p.motivo}
                         for p in self.procesos},
            "canales": canales,
        }
