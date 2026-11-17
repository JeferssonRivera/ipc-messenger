"""IPC Messenger — simulador de comunicación entre procesos (Sistemas Operativos)."""
from .modelo import Accion, Estado, Mensaje, Proceso, Resultado
from .mecanismos import ColaMensajes, MemoriaCompartida, Tuberia, crear_mecanismo, NOMBRES_MECANISMO
from .simulador import ConfigSimulacion, EventoFallo, Simulador
from .escenarios import ESCENARIOS, POR_CLAVE

__version__ = "1.0.0"
