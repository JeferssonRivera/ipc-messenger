"""
IPC REAL con procesos del sistema operativo (módulo multiprocessing).

A diferencia del simulador, aquí SÍ se crean procesos reales y los tiempos
SON mediciones del equipo donde se ejecuta (varían entre ejecuciones y
máquinas). Se usa como complemento para contrastar con la simulación:

  1. Rendimiento: N mensajes por Queue, Pipe y memoria compartida (+semáforos).
  2. Fallo: el lector de una tubería muere -> el escritor recibe BrokenPipeError.
  3. Fallo: el receptor de una cola muere -> el emisor sólo lo nota por timeout.

Todas las funciones objetivo están en el nivel superior del módulo para que
funcionen con el método 'spawn' (Windows / macOS).
"""
from __future__ import annotations

import multiprocessing as mp
import os
import queue as _queue
import time

TAM_MSG = 32


# ----------------------------------------------------------- procesos hijos
def _consumidor_cola(q, n):
    for _ in range(n):
        q.get()


def _consumidor_pipe(conn, n):
    for _ in range(n):
        conn.recv_bytes()
    conn.close()


def _consumidor_shm(buf, ranuras, idx_out, vacios, llenos, mutex, n, recibidos):
    cap = len(ranuras)
    for _ in range(n):
        llenos.acquire()
        with mutex:
            _ = ranuras[idx_out.value]
            idx_out.value = (idx_out.value + 1) % cap
        vacios.release()
        with recibidos.get_lock():
            recibidos.value += 1


def _lector_que_muere(conn):
    conn.recv_bytes()
    os._exit(1)          # muere abruptamente sin cerrar ordenadamente


def _receptor_cola_que_muere(q):
    q.get()
    os._exit(1)


# ----------------------------------------------------------- pruebas
def medir_cola(n: int) -> float:
    q = mp.Queue(maxsize=64)
    p = mp.Process(target=_consumidor_cola, args=(q, n))
    p.start()
    dato = b"x" * TAM_MSG
    t0 = time.perf_counter()
    for _ in range(n):
        q.put(dato)
    p.join()
    return time.perf_counter() - t0


def medir_pipe(n: int) -> float:
    lectura, escritura = mp.Pipe(duplex=False)
    p = mp.Process(target=_consumidor_pipe, args=(lectura, n))
    p.start()
    lectura.close()
    dato = b"x" * TAM_MSG
    t0 = time.perf_counter()
    for _ in range(n):
        escritura.send_bytes(dato)
    p.join()
    escritura.close()
    return time.perf_counter() - t0


def medir_memoria(n: int, capacidad: int = 64) -> float:
    ranuras = mp.Array("i", capacidad, lock=False)
    idx_out = mp.Value("i", 0, lock=False)
    vacios = mp.Semaphore(capacidad)
    llenos = mp.Semaphore(0)
    mutex = mp.Lock()
    recibidos = mp.Value("i", 0)
    p = mp.Process(target=_consumidor_shm,
                   args=(None, ranuras, idx_out, vacios, llenos, mutex, n, recibidos))
    p.start()
    idx_in = 0
    t0 = time.perf_counter()
    for i in range(n):
        vacios.acquire()
        with mutex:
            ranuras[idx_in] = i
            idx_in = (idx_in + 1) % capacidad
        llenos.release()
    p.join()
    return time.perf_counter() - t0


def demo_tuberia_rota() -> str:
    lectura, escritura = mp.Pipe(duplex=False)
    p = mp.Process(target=_lector_que_muere, args=(lectura,))
    p.start()
    lectura.close()                      # el padre no lee: sólo queda el hijo como lector
    escritura.send_bytes(b"hola")
    p.join()
    try:
        for _ in range(1000):
            escritura.send_bytes(b"x" * 1024)
        return "No se detectó error (el SO aún tenía búfer disponible)."
    except (BrokenPipeError, OSError) as e:
        return f"Escritor detectó la caída del lector: {type(e).__name__}: {e}"
    finally:
        escritura.close()


def demo_cola_receptor_muerto(timeout: float = 1.0) -> str:
    q = mp.Queue(maxsize=2)
    p = mp.Process(target=_receptor_cola_que_muere, args=(q,))
    p.start()
    q.put(b"1")
    p.join()
    enviados = 1
    try:
        while True:
            q.put(b"x", timeout=timeout)
            enviados += 1
    except _queue.Full:
        return (f"La cola no avisa la caída del receptor: se aceptaron {enviados} mensajes "
                f"y luego put() expiró tras {timeout}s (cola llena).")


def ejecutar_todo(n: int = 20000, reportar=print) -> list[dict]:
    """Ejecuta las mediciones y demostraciones. Si el entorno no admite algún
    mecanismo (p. ej. funciones serverless sin /dev/shm, donde no existen los
    semáforos POSIX), esa fila se marca como no disponible en lugar de fallar."""
    if n < 1 or n > 1_000_000:
        raise ValueError("n debe estar entre 1 y 1.000.000")
    reportar(f"=== IPC REAL (procesos del SO, PID padre {os.getpid()}) — {n} mensajes de {TAM_MSG} B ===")
    reportar("Mediciones reales de ESTE equipo: varían según hardware y carga.")
    filas = []
    for nombre, fn in (("multiprocessing.Queue", medir_cola),
                       ("multiprocessing.Pipe", medir_pipe),
                       ("Memoria compartida + semáforos", medir_memoria)):
        try:
            t = fn(n)
        except Exception as e:  # noqa: BLE001 — el entorno no soporta el mecanismo
            filas.append({"Mecanismo": nombre, "Tiempo (s)": None, "Mensajes/s": 0,
                          "Disponible": False, "Detalle": f"{type(e).__name__}: {e}"})
            reportar(f"  {nombre:32s} NO DISPONIBLE en este servidor ({type(e).__name__}: {e})")
            continue
        fila = {"Mecanismo": nombre, "Tiempo (s)": round(t, 4),
                "Mensajes/s": int(n / t) if t > 0 else 0, "Disponible": True, "Detalle": ""}
        filas.append(fila)
        reportar(f"  {nombre:32s} {t:8.4f} s   {fila['Mensajes/s']:>10,} msg/s")
    reportar("--- Fallos reales ---")
    for etiqueta, demo in (("Tubería", demo_tuberia_rota), ("Cola", demo_cola_receptor_muerto)):
        try:
            reportar(f"  {etiqueta + ':':9s}" + demo())
        except Exception as e:  # noqa: BLE001
            reportar(f"  {etiqueta + ':':9s}No disponible en este servidor ({type(e).__name__}: {e})")
    return filas


if __name__ == "__main__":
    mp.freeze_support()
    ejecutar_todo()
