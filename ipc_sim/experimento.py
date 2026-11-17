"""
Reto de experimentación: misma carga, distintos mecanismos.

Se ejecuta la MISMA configuración de emisores/receptores sobre:
  cola de mensajes, tubería, memoria compartida con y sin sincronización,
y se comparan entregas, pérdidas, latencias, bloqueos y espera activa.
"""
from __future__ import annotations

from dataclasses import asdict, replace

from .simulador import ConfigSimulacion, EventoFallo, Simulador

BYTES_POR_MENSAJE = 18   # tamaño aproximado de una línea serializada


VARIANTES = [
    ("Cola de mensajes", dict(mecanismo="cola")),
    ("Tubería", dict(mecanismo="tuberia")),
    ("Memoria compartida + semáforos", dict(mecanismo="memoria", sincronizada=True)),
    ("Memoria compartida sin sincronizar", dict(mecanismo="memoria", sincronizada=False)),
]

COLUMNAS = ["Mecanismo", "Entregados", "Perdidos", "Corruptos/carrera", "EAGAIN/timeout",
            "Lat. prom", "Lat. máx", "Ticks bloqueado", "Espera activa", "Ticks totales", "Final"]


def ejecutar_variante(nombre: str, base: ConfigSimulacion, cambios: dict,
                      fallo_receptor_tick: int = 0) -> dict:
    cfg = replace(base, **cambios)
    if cfg.mecanismo == "tuberia":
        # misma capacidad "en mensajes" expresada en bytes
        cfg = replace(cfg, capacidad=max(20, base.capacidad * BYTES_POR_MENSAJE))
    fallos = [EventoFallo(fallo_receptor_tick, "R1", "caer")] if fallo_receptor_tick else []
    sim = Simulador(cfg, fallos=fallos).ejecutar()
    m = sim.metricas()
    c = m["canales"]["C1"]
    programados = m["mensajes_programados"]
    if sim.estancado:
        final = "Estancado"
    elif any(p["motivo"] == "terminado por SIGPIPE" for p in m["procesos"].values()):
        final = "SIGPIPE"
    else:
        final = "Completado"
    return {
        "Mecanismo": nombre,
        "Entregados": f"{c['entregados']}/{programados}",
        "Perdidos": programados - c["entregados"],
        "Corruptos/carrera": c["corruptos"] + c["sobrescritos"] + c["lecturas_invalidas"],
        "EAGAIN/timeout": c["rechazados_eagain"] + c["descartados_timeout"] + c["epipe"],
        "Lat. prom": c["latencia_prom"],
        "Lat. máx": c["latencia_max"],
        "Ticks bloqueado": m["ticks_bloqueado"],
        "Espera activa": m["ticks_espera_activa"],
        "Ticks totales": m["ticks"],
        "Final": final,
        "_diagnostico": sim.diagnostico,
        "_entregados": c["entregados"],
        "_programados": programados,
    }


def comparar(base: ConfigSimulacion, fallo_receptor_tick: int = 0) -> list[dict]:
    errores = base.validar()
    if errores:
        raise ValueError("\n".join(errores))
    return [ejecutar_variante(n, base, cambios, fallo_receptor_tick) for n, cambios in VARIANTES]


def conclusiones(filas: list[dict], base: ConfigSimulacion) -> list[str]:
    out = []
    integros = [f for f in filas if f["Perdidos"] == 0 and f["Corruptos/carrera"] == 0
                and f["Final"] == "Completado"]
    if integros:
        mas_rapido = min(integros, key=lambda f: f["Ticks totales"])
        out.append(f"• Entregaron todo sin errores: {', '.join(f['Mecanismo'] for f in integros)}. "
                   f"El que terminó en menos ticks fue «{mas_rapido['Mecanismo']}» "
                   f"({mas_rapido['Ticks totales']} ticks).")
    for f in filas:
        if f["Corruptos/carrera"]:
            if f["Mecanismo"].startswith("Tubería"):
                out.append(f"• Tubería: {f['Corruptos/carrera']} mensajes corruptos. Una tubería es un "
                           "flujo de bytes sin límites de mensaje; con varios lectores las lecturas "
                           "parciales se intercalan.")
            else:
                out.append(f"• {f['Mecanismo']}: {f['Corruptos/carrera']} eventos de carrera "
                           f"(sobrescrituras/lecturas inválidas) y {f['Perdidos']} mensajes perdidos. "
                           "La sección crítica no es atómica sin mutex.")
    sync = next(f for f in filas if "semáforos" in f["Mecanismo"])
    nosync = next(f for f in filas if "sin sincronizar" in f["Mecanismo"])
    if nosync["Espera activa"] > sync["Espera activa"]:
        out.append(f"• Sin semáforos los procesos sondean el búfer (espera activa: "
                   f"{nosync['Espera activa']} ticks de CPU desperdiciados) en lugar de dormir "
                   f"(bloqueados: {sync['Ticks bloqueado']} ticks con semáforos).")
    for f in filas:
        if f["Final"] == "Estancado":
            if "mutex" in f["_diagnostico"] and "nunca será liberado" in f["_diagnostico"]:
                out.append(f"• {f['Mecanismo']}: quedó estancado porque un proceso murió dentro "
                           "de la sección crítica y el mutex nunca se liberó (mutex huérfano).")
            else:
                out.append(f"• {f['Mecanismo']}: quedó estancado (receptor caído y emisores "
                           "bloqueados sin timeout). Se recomienda timeout o detección de fallos.")
        if f["Final"] == "SIGPIPE":
            out.append(f"• {f['Mecanismo']}: el emisor detectó de inmediato la caída del lector "
                       "(EPIPE/SIGPIPE), a diferencia de la cola, que sólo se llena.")
    if base.n_receptores > 1:
        out.append("• Con varios receptores la cola de mensajes conserva los límites de cada "
                   "mensaje, por eso es la opción natural para productor–consumidor múltiple.")
    out.append("• Recordatorio: son ticks de una SIMULACIÓN, no tiempos reales del sistema operativo.")
    return out


def tabla_texto(filas: list[dict]) -> str:
    anchos = {c: max(len(c), *(len(str(f[c])) for f in filas)) for c in COLUMNAS}
    linea = " | ".join(c.ljust(anchos[c]) for c in COLUMNAS)
    sep = "-+-".join("-" * anchos[c] for c in COLUMNAS)
    cuerpo = "\n".join(" | ".join(str(f[c]).ljust(anchos[c]) for c in COLUMNAS) for f in filas)
    return f"{linea}\n{sep}\n{cuerpo}"
