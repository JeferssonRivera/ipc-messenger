"""
IPC Messenger — Proyecto 9 · Sistemas Operativos
Punto de entrada.

    python main.py                       -> aplicación WEB (abre el navegador en http://127.0.0.1:5000)
    python main.py --puerto 8080         -> aplicación web en otro puerto
    python main.py --escritorio          -> versión de escritorio (Tkinter)
    python main.py --listar              -> lista los escenarios
    python main.py --escenario NOMBRE    -> ejecuta un escenario en consola
    python main.py --todos               -> ejecuta todos los escenarios (resumen)
    python main.py --experimento         -> comparación de mecanismos (misma carga)
    python main.py --real [N]            -> IPC con procesos reales del SO
"""
import argparse
import multiprocessing
import sys

# Vercel (y cualquier servidor WSGI) busca una instancia Flask llamada «app» en main.py.
try:
    from web.servidor import app  # noqa: F401
except ImportError:               # Flask no instalado: los modos de consola siguen funcionando
    app = None


def _consola_utf8():
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass


def correr_escenario(clave: str, detalle: bool = True) -> dict:
    from ipc_sim import POR_CLAVE
    if clave not in POR_CLAVE:
        raise SystemExit(f"Escenario '{clave}' no existe. Usa --listar.")
    esc = POR_CLAVE[clave]
    sim = esc.crear().ejecutar()
    m = sim.metricas()
    if detalle:
        print(f"\n=== {esc.titulo}  [{esc.tipo}] ===")
        print(f"Descripción: {esc.descripcion}")
        print(f"Esperado:    {esc.esperado}\n")
        for ev in sim.eventos:
            print(f"[{ev.tick:>3}] {ev.origen:>4} | {ev.texto}")
        print("\n--- Métricas ---")
        for n, c in m["canales"].items():
            print(f"Canal {n}: " + ", ".join(f"{k}={v}" for k, v in c.items()))
        for pid, p in m["procesos"].items():
            print(f"  {pid}: {p['estado']:<12} env={p['enviados']} rec={p['recibidos']} "
                  f"bloq={p['bloqueado']} err={p['errores']} {p['motivo']}")
    return {"escenario": esc, "sim": sim, "m": m}


def main():
    _consola_utf8()
    ap = argparse.ArgumentParser(description="IPC Messenger — simulador de comunicación entre procesos")
    ap.add_argument("--listar", action="store_true", help="lista los escenarios disponibles")
    ap.add_argument("--escenario", metavar="CLAVE", help="ejecuta un escenario en consola")
    ap.add_argument("--todos", action="store_true", help="ejecuta todos los escenarios y resume")
    ap.add_argument("--experimento", action="store_true", help="compara los mecanismos con la misma carga")
    ap.add_argument("--fallo", type=int, default=0, help="(experimento) tick en que cae R1")
    ap.add_argument("--real", nargs="?", const=20000, type=int, metavar="N",
                    help="IPC real con procesos del SO (N mensajes)")
    ap.add_argument("--escritorio", action="store_true", help="abre la versión de escritorio (Tkinter)")
    ap.add_argument("--puerto", type=int, default=5000, help="puerto del servidor web (por defecto 5000)")
    ap.add_argument("--no-navegador", action="store_true", help="no abrir el navegador automáticamente")
    a = ap.parse_args()

    if a.listar:
        from ipc_sim import ESCENARIOS
        for e in ESCENARIOS:
            print(f"{e.clave:22s} [{e.tipo:6s}] {e.titulo}")
    elif a.escenario:
        correr_escenario(a.escenario)
    elif a.todos:
        from ipc_sim import ESCENARIOS
        print(f"{'Escenario':52s} {'Ticks':>5} {'Env':>4} {'Ent':>4}  Resultado")
        for e in ESCENARIOS:
            r = correr_escenario(e.clave, detalle=False)
            env = sum(c["enviados"] for c in r["m"]["canales"].values())
            ent = sum(c["entregados"] for c in r["m"]["canales"].values())
            fin = "ESTANCADO" if r["sim"].estancado else "fin"
            print(f"{e.titulo:52s} {r['m']['ticks']:>5} {env:>4} {ent:>4}  {fin}")
    elif a.experimento:
        from ipc_sim import ConfigSimulacion
        from ipc_sim.experimento import comparar, conclusiones, tabla_texto
        base = ConfigSimulacion(n_emisores=3, n_receptores=2, mensajes_por_emisor=6,
                                capacidad=4, tiempo_receptor=2, max_ticks=5000)
        filas = comparar(base, fallo_receptor_tick=a.fallo)
        print("Carga: 3 emisores × 6 mensajes, 2 receptores, capacidad 4"
              + (f", R1 cae en tick {a.fallo}" if a.fallo else "") + "\n")
        print(tabla_texto(filas))
        print("\n" + "\n".join(conclusiones(filas, base)))
    elif a.real is not None:
        from ipc_sim import ipc_real
        ipc_real.ejecutar_todo(a.real)
    elif not a.escritorio:
        try:
            from web.servidor import ejecutar
        except ImportError as e:
            raise SystemExit("Falta Flask. Instálalo con:  pip install -r requirements.txt\n"
                             f"Detalle: {e}")
        ejecutar(puerto=a.puerto, abrir_navegador=not a.no_navegador)
    else:
        try:
            from gui.app import main as gui_main
        except ImportError as e:
            raise SystemExit("No se pudo cargar Tkinter. Instálalo (en Linux: sudo apt install "
                             f"python3-tk) o usa los modos de consola (--help).\nDetalle: {e}")
        gui_main()


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
