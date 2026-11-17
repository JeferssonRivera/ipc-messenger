"""
Modelo de datos del simulador IPC Messenger.

Define los estados de un proceso, los mensajes que viajan entre procesos,
las acciones que compone el "programa" de cada proceso y los resultados
que devuelve un mecanismo de IPC al intentar una operación.

IMPORTANTE: todo esto es una SIMULACIÓN de tiempo discreto (ticks).
No se crean procesos reales del sistema operativo en este módulo.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class Estado(str, Enum):
    """Estados que puede tener un proceso simulado."""
    NUEVO = "Nuevo"
    LISTO = "Listo"
    EJECUCION = "Ejecución"
    BLOQUEADO = "Bloqueado"          # dormido esperando un recurso (cola llena, mutex...)
    ESPERA_ACTIVA = "Espera activa"  # sondeo/busy-wait: consume CPU sin avanzar
    NO_RESPONDE = "No responde"      # fallo transitorio: vivo pero congelado
    CAIDO = "Caído"                  # fallo permanente (crash)
    TERMINADO = "Terminado"


ESTADOS_VIVOS = {Estado.NUEVO, Estado.LISTO, Estado.EJECUCION,
                 Estado.BLOQUEADO, Estado.ESPERA_ACTIVA, Estado.NO_RESPONDE}


class Resultado(Enum):
    """Respuesta de un mecanismo IPC a un intento de operación."""
    OK = "ok"                    # operación completada
    SIGUE = "sigue"              # avanzó una fase, necesita más ticks
    BLOQUEA = "bloquea"          # no puede continuar: debe dormir (o fallar si no es bloqueante)
    ESPERA_ACTIVA = "espera"     # no puede continuar y no hay primitiva de bloqueo: sondea
    ERROR = "error"              # error definitivo (EPIPE, mensaje demasiado grande...)
    EOF = "eof"                  # no hay más datos ni emisores: fin de flujo


@dataclass
class Mensaje:
    id: int
    origen: str
    contenido: str
    tick_envio: int
    prioridad: int = 0

    def serializar(self) -> str:
        """Formato de línea usado en la tubería (flujo de bytes)."""
        return f"{self.id}|{self.origen}|{self.contenido}|{self.tick_envio}\n"

    def __str__(self) -> str:
        prio = f" p{self.prioridad}" if self.prioridad else ""
        return f"#{self.id} {self.contenido}{prio}"


@dataclass
class Accion:
    """Instrucción del programa de un proceso."""
    tipo: str                       # 'enviar' | 'recibir' | 'computar'
    canal: Optional[str] = None
    contenido: str = ""
    ticks: int = 1                  # duración para 'computar'

    def __post_init__(self):
        if self.tipo not in ("enviar", "recibir", "computar"):
            raise ValueError(f"Acción desconocida: {self.tipo}")
        if self.tipo in ("enviar", "recibir") and not self.canal:
            raise ValueError("Las acciones de comunicación requieren un canal")
        if self.ticks < 1:
            raise ValueError("La duración de 'computar' debe ser >= 1")

    def describir(self) -> str:
        if self.tipo == "enviar":
            return f"send({self.canal}, '{self.contenido}')"
        if self.tipo == "recibir":
            return f"receive({self.canal})"
        return f"compute({self.ticks})"


@dataclass
class Proceso:
    pid: str
    rol: str                         # 'emisor' | 'receptor' | 'mixto'
    programa: list[Accion]
    repetir: bool = False            # receptores: ciclo infinito hasta EOF
    estado: Estado = Estado.NUEVO
    pc: int = 0
    op: Optional[Accion] = None      # operación en curso
    op_restante: int = 0             # ticks restantes de 'computar'
    op_mensaje: Optional[Mensaje] = None
    ctx: dict = field(default_factory=dict)    # estado interno de la operación (fases)
    datos: dict = field(default_factory=dict)  # memoria privada (p.ej. buffer de lectura de tubería)
    espera: int = 0                  # ticks consecutivos esperando en la operación actual
    motivo: str = ""                 # por qué está bloqueado / terminó
    lento: int = 1                   # factor de lentitud (1 = normal)
    # métricas
    enviados: int = 0
    recibidos: int = 0
    ticks_bloqueado: int = 0
    ticks_espera_activa: int = 0
    errores: int = 0
    seq: int = 0

    @property
    def vivo(self) -> bool:
        return self.estado in ESTADOS_VIVOS

    def descripcion_op(self) -> str:
        return self.op.describir() if self.op else "—"
