"""
Mecanismos de comunicación entre procesos (simulados).

  * ColaMensajes      -> estilo System V / POSIX mq: mensajes discretos, FIFO
                         (o por prioridad), capacidad en número de mensajes.
  * Tuberia           -> estilo pipe(): flujo de BYTES unidireccional, capacidad
                         en bytes, lecturas parciales, EOF y EPIPE/SIGPIPE.
  * MemoriaCompartida -> búfer circular en una región compartida. Puede operar
                         SIN sincronización (condiciones de carrera reales del
                         modelo) o CON mutex + semáforos contadores.

Cada mecanismo expone:
    enviar(proc, msg, sim)  -> (Resultado, info)
    recibir(proc, sim)      -> (Resultado, Mensaje | info)
    cancelar(proc)          -> deshace recursos tomados a medias (timeout)
    ocupacion()             -> elementos/bytes en el búfer
    contenido_visual()      -> lista para dibujar en la interfaz
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

from .modelo import Mensaje, Proceso, Resultado


@dataclass
class Estadisticas:
    enviados: int = 0          # mensajes aceptados por el mecanismo
    entregados: int = 0        # mensajes recibidos íntegros
    rechazados: int = 0        # envío no bloqueante con búfer lleno (EAGAIN)
    descartados_timeout: int = 0
    epipe: int = 0             # escrituras en tubería sin lectores
    corruptos: int = 0         # tubería: líneas inválidas por lecturas intercaladas
    sobrescritos: int = 0      # memoria sin sincronizar: dato pisado
    lecturas_invalidas: int = 0  # memoria sin sincronizar: ranura vacía/duplicada
    duplicados: int = 0
    max_ocupacion: int = 0
    latencias: list = field(default_factory=list)

    @property
    def latencia_prom(self) -> float:
        return sum(self.latencias) / len(self.latencias) if self.latencias else 0.0

    @property
    def latencia_max(self) -> int:
        return max(self.latencias) if self.latencias else 0


class Mecanismo:
    tipo = "base"
    unidad = "msg"

    def __init__(self, nombre: str, capacidad: int):
        if capacidad < 1:
            raise ValueError("La capacidad debe ser al menos 1")
        self.nombre = nombre
        self.capacidad = capacidad
        self.stats = Estadisticas()
        self._entregados_ids: set[int] = set()

    # --- utilidades comunes -------------------------------------------------
    def _registrar_entrega(self, msg: Mensaje, tick: int) -> None:
        if msg.id in self._entregados_ids:
            self.stats.duplicados += 1
            return
        self._entregados_ids.add(msg.id)
        self.stats.entregados += 1
        self.stats.latencias.append(tick - msg.tick_envio)

    def _actualizar_max(self) -> None:
        self.stats.max_ocupacion = max(self.stats.max_ocupacion, self.ocupacion())

    def cancelar(self, proc: Proceso) -> None:
        proc.ctx.clear()

    # --- interfaz -------------------------------------------------------------
    def enviar(self, proc, msg, sim):
        raise NotImplementedError

    def recibir(self, proc, sim):
        raise NotImplementedError

    def ocupacion(self) -> int:
        raise NotImplementedError

    def contenido_visual(self) -> list:
        raise NotImplementedError

    def en_transito(self) -> int:
        """Mensajes completos todavía dentro del mecanismo."""
        return self.ocupacion()


# =============================================================================
class ColaMensajes(Mecanismo):
    """Cola de mensajes del núcleo: conserva los límites de cada mensaje."""
    tipo = "cola"
    unidad = "msg"

    def __init__(self, nombre: str, capacidad: int, por_prioridad: bool = False):
        super().__init__(nombre, capacidad)
        self.buf: deque[Mensaje] = deque()
        self.por_prioridad = por_prioridad

    def enviar(self, proc, msg, sim):
        if len(self.buf) >= self.capacidad:
            return Resultado.BLOQUEA, f"cola '{self.nombre}' llena ({len(self.buf)}/{self.capacidad})"
        self.buf.append(msg)
        if self.por_prioridad:
            # mayor prioridad primero, FIFO entre iguales (sort estable)
            self.buf = deque(sorted(self.buf, key=lambda m: -m.prioridad))
        self.stats.enviados += 1
        self._actualizar_max()
        return Resultado.OK, f"msgsnd -> {msg} en '{self.nombre}'"

    def recibir(self, proc, sim):
        if self.buf:
            msg = self.buf.popleft()
            self._registrar_entrega(msg, sim.tick)
            return Resultado.OK, msg
        if sim.emisores_terminados(self.nombre):
            return Resultado.EOF, f"cola '{self.nombre}' vacía y sin emisores activos"
        return Resultado.BLOQUEA, f"cola '{self.nombre}' vacía"

    def ocupacion(self) -> int:
        return len(self.buf)

    def contenido_visual(self) -> list:
        return [str(m) for m in self.buf]


# =============================================================================
class Tuberia(Mecanismo):
    """Tubería anónima: flujo de bytes sin límites de mensaje.

    - Escritura atómica si len(datos) <= capacidad (como PIPE_BUF).
    - Si no quedan lectores vivos -> EPIPE y el emisor recibe SIGPIPE (termina).
    - La lectura toma hasta `tam_lectura` bytes; el receptor debe reensamblar
      las líneas. Con VARIOS lectores las lecturas parciales se intercalan y
      los mensajes llegan corruptos (limitación real de las tuberías).
    """
    tipo = "tuberia"
    unidad = "bytes"

    def __init__(self, nombre: str, capacidad: int, tam_lectura: int = 64):
        super().__init__(nombre, capacidad)
        if tam_lectura < 1:
            raise ValueError("El tamaño de lectura debe ser >= 1 byte")
        self.buf = ""
        self.tam_lectura = tam_lectura
        self._por_id: dict[int, Mensaje] = {}
        self._mensajes_en_buf = 0

    def enviar(self, proc, msg, sim):
        if not sim.receptores_vivos(self.nombre):
            self.stats.epipe += 1
            return Resultado.ERROR, "EPIPE: tubería rota (no hay lectores) -> SIGPIPE"
        datos = msg.serializar()
        if len(datos) > self.capacidad:
            return Resultado.ERROR, (f"mensaje de {len(datos)} B excede la capacidad "
                                     f"de la tubería ({self.capacidad} B)")
        libre = self.capacidad - len(self.buf)
        if len(datos) > libre:
            return Resultado.BLOQUEA, f"tubería '{self.nombre}' sin espacio ({libre} B libres)"
        self.buf += datos
        self._por_id[msg.id] = msg
        self._mensajes_en_buf += 1
        self.stats.enviados += 1
        self._actualizar_max()
        return Resultado.OK, f"write({len(datos)} B) -> {msg}"

    def _extraer_linea(self, proc, sim):
        rx = proc.datos.get("rx", "")
        if "\n" not in rx:
            return None
        linea, rx = rx.split("\n", 1)
        proc.datos["rx"] = rx
        partes = linea.split("|")
        msg = None
        if len(partes) == 4 and partes[0].isdigit():
            candidato = self._por_id.get(int(partes[0]))
            if candidato is not None and candidato.serializar() == linea + "\n":
                msg = candidato
        if msg is None:
            self.stats.corruptos += 1
            return Resultado.ERROR, f"línea corrupta recibida: '{linea[:30]}'"
        self._registrar_entrega(msg, sim.tick)
        return Resultado.OK, msg

    def recibir(self, proc, sim):
        # 1) ¿quedó una línea completa en el búfer privado del lector?
        r = self._extraer_linea(proc, sim)
        if r:
            return r
        # 2) leer del flujo compartido
        if self.buf:
            trozo = self.buf[: self.tam_lectura]
            self.buf = self.buf[self.tam_lectura:]
            self._mensajes_en_buf = self.buf.count("\n")
            proc.datos["rx"] = proc.datos.get("rx", "") + trozo
            r = self._extraer_linea(proc, sim)
            if r:
                return r
            return Resultado.SIGUE, f"read({len(trozo)} B): lectura parcial, mensaje incompleto"
        if sim.emisores_terminados(self.nombre):
            return Resultado.EOF, "read() = 0 -> EOF (todos los escritores cerraron)"
        return Resultado.BLOQUEA, f"tubería '{self.nombre}' vacía"

    def ocupacion(self) -> int:
        return len(self.buf)

    def en_transito(self) -> int:
        return self.buf.count("\n")

    def contenido_visual(self) -> list:
        return [l + "⏎" for l in self.buf.split("\n") if l] if self.buf else []


# =============================================================================
class MemoriaCompartida(Mecanismo):
    """Búfer circular en memoria compartida (productor-consumidor).

    Escribir/leer NO es atómico: se modela en fases de un tick cada una,
    (leer índice -> escribir ranura y actualizar índice/contador).
    Sin sincronización, dos procesos pueden leer el mismo índice en el
    mismo tick y pisarse (condición de carrera). Con sincronización se usan
    semáforos 'vacios'/'llenos' y un mutex para la sección crítica.
    """
    tipo = "memoria"
    unidad = "ranuras"

    def __init__(self, nombre: str, capacidad: int, sincronizada: bool = True):
        super().__init__(nombre, capacidad)
        self.sincronizada = sincronizada
        self.ranuras: list = [None] * capacidad
        self.idx_in = 0
        self.idx_out = 0
        self.contador = 0            # variable compartida (sujeta a carreras)
        self.sem_vacios = capacidad
        self.sem_llenos = 0
        self.mutex: str | None = None   # pid del dueño

    # --- recursos de sincronización ----------------------------------------
    def _tomar(self, proc, sem_attr: str, flag: str):
        """P(sem) + lock(mutex). Devuelve None si ya tiene ambos."""
        ctx = proc.ctx
        if not ctx.get(flag):
            if getattr(self, sem_attr) == 0:
                return Resultado.BLOQUEA, f"wait({sem_attr.replace('sem_', '')}) = 0"
            setattr(self, sem_attr, getattr(self, sem_attr) - 1)
            ctx[flag] = True
        if not ctx.get("mutex"):
            if self.mutex is not None and self.mutex != proc.pid:
                return Resultado.BLOQUEA, f"mutex ocupado por {self.mutex}"
            self.mutex = proc.pid
            ctx["mutex"] = True
            ctx["fase"] = 1
            return Resultado.SIGUE, "entra a la sección crítica (mutex tomado)"
        return None

    def cancelar(self, proc):
        ctx = proc.ctx
        if ctx.get("vacio"):
            self.sem_vacios += 1
        if ctx.get("lleno"):
            self.sem_llenos += 1
        if ctx.get("mutex") and self.mutex == proc.pid:
            self.mutex = None
        ctx.clear()

    # --- escritura -----------------------------------------------------------
    def enviar(self, proc, msg, sim):
        ctx = proc.ctx
        fase = ctx.get("fase", 0)
        if self.sincronizada:
            if fase == 0:
                return self._tomar(proc, "sem_vacios", "vacio")
            if fase == 1:
                ctx["idx"] = self.idx_in
                ctx["fase"] = 2
                return Resultado.SIGUE, f"lee idx_in = {ctx['idx']}"
            idx = ctx["idx"]
            self.ranuras[idx] = msg
            self.idx_in = (idx + 1) % self.capacidad
            self.contador += 1
            self.mutex = None
            self.sem_llenos += 1
            ctx.clear()
            self.stats.enviados += 1
            self._actualizar_max()
            return Resultado.OK, f"escribe {msg} en ranura {idx}; signal(mutex), signal(llenos)"
        # ---------- sin sincronización ----------
        if fase == 0:
            if self.contador >= self.capacidad:
                return Resultado.ESPERA_ACTIVA, "búfer lleno: while(contador == N) {} (sondeo)"
            ctx.update(fase=1, idx=self.idx_in, cont=self.contador)
            return Resultado.SIGUE, f"lee idx_in = {ctx['idx']}, contador = {ctx['cont']}"
        idx = ctx["idx"]
        if self.ranuras[idx] is not None:
            self.stats.sobrescritos += 1
            sim.log(f"⚠ CARRERA: {proc.pid} sobrescribe {self.ranuras[idx]} en ranura {idx}",
                    nivel="alerta", origen=self.nombre)
        self.ranuras[idx] = msg
        self.idx_in = (idx + 1) % self.capacidad
        self.contador = ctx["cont"] + 1      # actualización perdida si otro escribió en medio
        ctx.clear()
        self.stats.enviados += 1
        self._actualizar_max()
        return Resultado.OK, f"escribe {msg} en ranura {idx}"

    # --- lectura -------------------------------------------------------------
    def recibir(self, proc, sim):
        ctx = proc.ctx
        fase = ctx.get("fase", 0)
        if self.sincronizada:
            if fase == 0:
                if not ctx.get("lleno") and self.sem_llenos == 0 and sim.emisores_terminados(self.nombre):
                    return Resultado.EOF, "búfer vacío y sin productores activos"
                return self._tomar(proc, "sem_llenos", "lleno")
            if fase == 1:
                ctx["idx"] = self.idx_out
                ctx["fase"] = 2
                return Resultado.SIGUE, f"lee idx_out = {ctx['idx']}"
            idx = ctx["idx"]
            msg = self.ranuras[idx]
            self.ranuras[idx] = None
            self.idx_out = (idx + 1) % self.capacidad
            self.contador -= 1
            self.mutex = None
            self.sem_vacios += 1
            ctx.clear()
            self._registrar_entrega(msg, sim.tick)
            return Resultado.OK, msg
        # ---------- sin sincronización ----------
        if fase == 0:
            if self.contador <= 0:
                if sim.emisores_terminados(self.nombre) and all(r is None for r in self.ranuras):
                    return Resultado.EOF, "búfer vacío y sin productores activos"
                if sim.emisores_terminados(self.nombre) and self.contador <= 0:
                    # el contador quedó inconsistente por una carrera: hay datos "invisibles"
                    self.contador = sum(r is not None for r in self.ranuras)
                    sim.log("⚠ contador inconsistente detectado y corregido al final",
                            nivel="alerta", origen=self.nombre)
                    if self.contador == 0:
                        return Resultado.EOF, "búfer vacío"
                return Resultado.ESPERA_ACTIVA, "búfer vacío: while(contador == 0) {} (sondeo)"
            ctx.update(fase=1, idx=self.idx_out, cont=self.contador)
            return Resultado.SIGUE, f"lee idx_out = {ctx['idx']}, contador = {ctx['cont']}"
        idx = ctx["idx"]
        msg = self.ranuras[idx]
        self.ranuras[idx] = None
        self.idx_out = (idx + 1) % self.capacidad
        self.contador = ctx["cont"] - 1
        ctx.clear()
        if msg is None:
            self.stats.lecturas_invalidas += 1
            return Resultado.ERROR, f"⚠ CARRERA: lee ranura {idx} vacía (otro consumidor ya la tomó)"
        self._registrar_entrega(msg, sim.tick)
        return Resultado.OK, msg

    def ocupacion(self) -> int:
        return sum(r is not None for r in self.ranuras)

    def contenido_visual(self) -> list:
        return [str(r) if r is not None else "·" for r in self.ranuras]


def crear_mecanismo(tipo: str, nombre: str, capacidad: int, **opciones) -> Mecanismo:
    if tipo == "cola":
        return ColaMensajes(nombre, capacidad, por_prioridad=opciones.get("por_prioridad", False))
    if tipo == "tuberia":
        return Tuberia(nombre, capacidad, tam_lectura=opciones.get("tam_lectura", 64))
    if tipo == "memoria":
        return MemoriaCompartida(nombre, capacidad, sincronizada=opciones.get("sincronizada", True))
    raise ValueError(f"Mecanismo desconocido: {tipo}")


NOMBRES_MECANISMO = {
    "cola": "Cola de mensajes",
    "tuberia": "Tubería (pipe)",
    "memoria": "Memoria compartida",
}
