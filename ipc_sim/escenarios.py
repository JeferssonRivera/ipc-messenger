"""Escenarios predefinidos (casos de prueba reproducibles y demostraciones)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

from .mecanismos import crear_mecanismo
from .modelo import Accion, Proceso
from .simulador import ConfigSimulacion, EventoFallo, Simulador


@dataclass
class Escenario:
    clave: str
    titulo: str
    tipo: str                    # normal | límite | error
    descripcion: str
    esperado: str
    config: dict = field(default_factory=dict)
    fallos: list = field(default_factory=list)
    constructor: Optional[Callable[[ConfigSimulacion], Simulador]] = None

    def crear(self) -> Simulador:
        cfg = ConfigSimulacion(**self.config)
        if self.constructor:
            return self.constructor(cfg)
        return Simulador(cfg, fallos=[EventoFallo(**f) for f in self.fallos])


def _interbloqueo(cfg: ConfigSimulacion) -> Simulador:
    """A espera un mensaje de B antes de enviarle; B espera uno de A. Espera circular."""
    canales = {"A→B": crear_mecanismo(cfg.mecanismo, "A→B", cfg.capacidad),
               "B→A": crear_mecanismo(cfg.mecanismo, "B→A", cfg.capacidad)}
    a = Proceso("A", "mixto", [Accion("recibir", "B→A"), Accion("enviar", "A→B", "respuesta de A")])
    b = Proceso("B", "mixto", [Accion("recibir", "A→B"), Accion("enviar", "B→A", "respuesta de B")])
    return Simulador(cfg, procesos=[a, b], canales=canales)


def _sin_interbloqueo(cfg: ConfigSimulacion) -> Simulador:
    """Misma pareja, pero A envía primero: se rompe la espera circular."""
    canales = {"A→B": crear_mecanismo(cfg.mecanismo, "A→B", cfg.capacidad),
               "B→A": crear_mecanismo(cfg.mecanismo, "B→A", cfg.capacidad)}
    a = Proceso("A", "mixto", [Accion("enviar", "A→B", "petición de A"), Accion("recibir", "B→A")])
    b = Proceso("B", "mixto", [Accion("recibir", "A→B"), Accion("enviar", "B→A", "respuesta de B")])
    return Simulador(cfg, procesos=[a, b], canales=canales)


ESCENARIOS: list[Escenario] = [
    Escenario("normal_cola", "1. Cola de mensajes – flujo normal", "normal",
              "2 emisores y 2 receptores comparten una cola de 4 mensajes.",
              "Se entregan los 10 mensajes sin pérdidas y todos terminan por EOF.",
              dict(mecanismo="cola", capacidad=4, n_emisores=2, n_receptores=2,
                   mensajes_por_emisor=5, intervalo_emisor=1, tiempo_receptor=2)),
    Escenario("cola_llena", "2. Cola llena (bloqueante)", "límite",
              "3 emisores rápidos, 1 receptor lento, cola de capacidad 2.",
              "Los emisores pasan a Bloqueado cuando la cola está llena; no se pierde nada.",
              dict(mecanismo="cola", capacidad=2, n_emisores=3, n_receptores=1,
                   mensajes_por_emisor=4, intervalo_emisor=1, tiempo_receptor=3)),
    Escenario("cola_no_bloq", "3. Cola llena (no bloqueante, EAGAIN)", "límite",
              "Igual al anterior pero msgsnd con IPC_NOWAIT.",
              "Los envíos con cola llena fallan con EAGAIN y esos mensajes se descartan.",
              dict(mecanismo="cola", capacidad=2, n_emisores=3, n_receptores=1,
                   mensajes_por_emisor=4, intervalo_emisor=1, tiempo_receptor=3, bloqueante=False)),
    Escenario("receptor_cae", "4. Receptor se cae (sin timeout)", "error",
              "El único receptor sufre un crash en el tick 6.",
              "La cola se llena, los emisores quedan bloqueados para siempre y se detecta estancamiento.",
              dict(mecanismo="cola", capacidad=3, n_emisores=2, n_receptores=1,
                   mensajes_por_emisor=6, intervalo_emisor=1, tiempo_receptor=1),
              [dict(tick=6, pid="R1", tipo="caer")]),
    Escenario("receptor_cae_timeout", "5. Receptor se cae (con timeout)", "error",
              "Igual al anterior pero los envíos tienen timeout de 5 ticks.",
              "Los emisores detectan la falta de respuesta, descartan mensajes y terminan.",
              dict(mecanismo="cola", capacidad=3, n_emisores=2, n_receptores=1,
                   mensajes_por_emisor=6, intervalo_emisor=1, tiempo_receptor=1, timeout=5),
              [dict(tick=6, pid="R1", tipo="caer")]),
    Escenario("receptor_congelado", "6. Receptor deja de responder y se recupera", "error",
              "R1 se congela en el tick 5 y vuelve en el tick 25.",
              "Los emisores se bloquean mientras dura el fallo y luego todo se entrega.",
              dict(mecanismo="cola", capacidad=3, n_emisores=2, n_receptores=1,
                   mensajes_por_emisor=5, intervalo_emisor=1, tiempo_receptor=1,
                   ventana_estancamiento=30),
              [dict(tick=5, pid="R1", tipo="no_responder"), dict(tick=25, pid="R1", tipo="recuperar")]),
    Escenario("tuberia_normal", "7. Tubería – flujo normal", "normal",
              "1 escritor y 1 lector; tubería de 64 bytes, lecturas de 64 bytes.",
              "Todos los mensajes se reensamblan correctamente; el lector termina por EOF.",
              dict(mecanismo="tuberia", capacidad=64, n_emisores=1, n_receptores=1,
                   mensajes_por_emisor=8, intervalo_emisor=1, tiempo_receptor=2, tam_lectura=64)),
    Escenario("tuberia_parcial", "8. Tubería – lecturas parciales", "límite",
              "Lecturas de sólo 7 bytes: cada mensaje requiere varias read().",
              "Los mensajes llegan íntegros pero con mayor latencia (flujo de bytes).",
              dict(mecanismo="tuberia", capacidad=64, n_emisores=1, n_receptores=1,
                   mensajes_por_emisor=5, intervalo_emisor=1, tiempo_receptor=1, tam_lectura=7)),
    Escenario("tuberia_rota", "9. Tubería rota (lector cae → SIGPIPE)", "error",
              "El lector se cae en el tick 6.",
              "La siguiente escritura falla con EPIPE y el escritor termina por SIGPIPE.",
              dict(mecanismo="tuberia", capacidad=64, n_emisores=1, n_receptores=1,
                   mensajes_por_emisor=8, intervalo_emisor=1, tiempo_receptor=2),
              [dict(tick=6, pid="R1", tipo="caer")]),
    Escenario("tuberia_multilector", "10. Tubería con 2 lectores", "error",
              "Dos lectores comparten la misma tubería y leen 16 bytes cada vez.",
              "Las lecturas parciales se intercalan y aparecen mensajes corruptos.",
              dict(mecanismo="tuberia", capacidad=96, n_emisores=2, n_receptores=2,
                   mensajes_por_emisor=5, intervalo_emisor=1, tiempo_receptor=1, tam_lectura=16)),
    Escenario("memoria_sin_sync", "11. Memoria compartida SIN sincronización", "error",
              "2 productores y 2 consumidores escriben/leen el búfer sin mutex ni semáforos.",
              "Condición de carrera: sobrescrituras, lecturas inválidas y mensajes perdidos.",
              dict(mecanismo="memoria", capacidad=4, n_emisores=2, n_receptores=2,
                   mensajes_por_emisor=6, intervalo_emisor=1, tiempo_receptor=1, sincronizada=False)),
    Escenario("memoria_sync", "12. Memoria compartida CON mutex + semáforos", "normal",
              "Misma carga que el escenario 11, protegida con semáforos.",
              "Cero pérdidas: la sección crítica es exclusiva y se bloquea con búfer lleno/vacío.",
              dict(mecanismo="memoria", capacidad=4, n_emisores=2, n_receptores=2,
                   mensajes_por_emisor=6, intervalo_emisor=1, tiempo_receptor=1, sincronizada=True)),
    Escenario("mutex_huerfano", "13. Proceso cae dentro de la sección crítica", "error",
              "E1 se cae en el tick 7, justo cuando posee el mutex.",
              "El mutex nunca se libera: el resto se bloquea y se diagnostica la causa.",
              dict(mecanismo="memoria", capacidad=4, n_emisores=2, n_receptores=1,
                   mensajes_por_emisor=4, intervalo_emisor=1, tiempo_receptor=1, sincronizada=True),
              [dict(tick=7, pid="E1", tipo="caer")]),
    Escenario("interbloqueo", "14. Interbloqueo por recepción cruzada", "error",
              "A espera un mensaje de B antes de responder y B espera uno de A.",
              "Ambos quedan bloqueados; se detecta espera circular A → B → A.",
              dict(mecanismo="cola", capacidad=2), constructor=_interbloqueo),
    Escenario("sin_interbloqueo", "15. Sin interbloqueo (A envía primero)", "normal",
              "Se cambia el orden de A: primero envía y luego recibe.",
              "Se rompe la espera circular y ambos terminan.",
              dict(mecanismo="cola", capacidad=2), constructor=_sin_interbloqueo),
]

POR_CLAVE = {e.clave: e for e in ESCENARIOS}
