"""
Pruebas automatizadas de IPC Messenger.
Cada prueba lleva el ID de la matriz de pruebas (docs/matriz_pruebas.md).

    python -m unittest -v
"""
import unittest

from ipc_sim import (Accion, ConfigSimulacion, Estado, EventoFallo, Mensaje, POR_CLAVE,
                     Proceso, Simulador, crear_mecanismo)
from ipc_sim.experimento import comparar


def correr(clave):
    s = POR_CLAVE[clave].crear().ejecutar()
    return s, s.metricas()["canales"]


class Normales(unittest.TestCase):
    def test_N01_cola_entrega_todo(self):
        s, c = correr("normal_cola")
        self.assertFalse(s.estancado)
        self.assertEqual(c["C1"]["entregados"], 10)
        self.assertEqual(c["C1"]["perdidos"], 0)
        self.assertTrue(all(p.estado == Estado.TERMINADO for p in s.procesos))

    def test_N02_cola_fifo_un_receptor(self):
        cfg = ConfigSimulacion(n_emisores=1, n_receptores=1, mensajes_por_emisor=6, capacidad=3)
        s = Simulador(cfg).ejecutar()
        recibidos = [e.texto for e in s.eventos if e.texto.startswith("📥")]
        orden = [int(t.split("#")[1].split()[0]) for t in recibidos]
        self.assertEqual(orden, sorted(orden), "la cola debe respetar el orden FIFO")

    def test_N03_tuberia_reensambla(self):
        s, c = correr("tuberia_normal")
        self.assertEqual(c["C1"]["entregados"], 8)
        self.assertEqual(c["C1"]["corruptos"], 0)
        self.assertIn("EOF", s.proceso("R1").motivo)

    def test_N04_memoria_sincronizada_sin_perdidas(self):
        s, c = correr("memoria_sync")
        self.assertEqual(c["C1"]["entregados"], 12)
        self.assertEqual(c["C1"]["sobrescritos"] + c["C1"]["lecturas_invalidas"], 0)

    def test_N05_sin_interbloqueo(self):
        s, _ = correr("sin_interbloqueo")
        self.assertFalse(s.estancado)
        self.assertTrue(all(p.estado == Estado.TERMINADO for p in s.procesos))

    def test_N06_reproducible_con_semilla(self):
        cfg = ConfigSimulacion(variacion=2, semilla=7, n_emisores=3, n_receptores=2)
        a = Simulador(cfg).ejecutar().metricas()
        b = Simulador(cfg).ejecutar().metricas()
        self.assertEqual(a, b)

    def test_N07_prioridad(self):
        cola = crear_mecanismo("cola", "C", 5, por_prioridad=True)

        class SimFalso:
            tick = 0
        for i, pr in enumerate([0, 3, 1]):
            cola.enviar(None, Mensaje(i, "E", f"m{i}", 0, pr), SimFalso)
        self.assertEqual([m.prioridad for m in cola.buf], [3, 1, 0])


class Limites(unittest.TestCase):
    def test_L01_cola_llena_bloquea_sin_perder(self):
        s, c = correr("cola_llena")
        self.assertGreater(s.metricas()["ticks_bloqueado"], 0)
        self.assertEqual(c["C1"]["max_ocupacion"], 2)          # nunca excede la capacidad
        self.assertEqual(c["C1"]["entregados"], 12)

    def test_L02_no_bloqueante_eagain(self):
        s, c = correr("cola_no_bloq")
        self.assertGreater(c["C1"]["rechazados_eagain"], 0)
        self.assertEqual(c["C1"]["enviados"] + c["C1"]["rechazados_eagain"], 12)

    def test_L03_lecturas_parciales(self):
        s, c = correr("tuberia_parcial")
        self.assertEqual(c["C1"]["entregados"], 5)
        parciales = [e for e in s.eventos if "lectura parcial" in e.texto]
        self.assertTrue(parciales)

    def test_L04_capacidad_minima(self):
        cfg = ConfigSimulacion(capacidad=1, n_emisores=2, n_receptores=1, mensajes_por_emisor=3)
        s = Simulador(cfg).ejecutar()
        self.assertEqual(s.metricas()["canales"]["C1"]["entregados"], 6)

    def test_L05_receptor_congelado_y_recupera(self):
        s, c = correr("receptor_congelado")
        self.assertEqual(c["C1"]["entregados"], 10)
        self.assertFalse(s.estancado)


class Errores(unittest.TestCase):
    def test_E01_receptor_cae_estanca(self):
        s, _ = correr("receptor_cae")
        self.assertTrue(s.estancado)
        self.assertIn("ningún receptor", s.diagnostico)

    def test_E02_timeout_detecta_caida(self):
        s, c = correr("receptor_cae_timeout")
        self.assertFalse(s.estancado)
        self.assertGreater(c["C1"]["descartados_timeout"], 0)

    def test_E03_tuberia_rota_sigpipe(self):
        s, c = correr("tuberia_rota")
        self.assertEqual(c["C1"]["epipe"], 1)
        self.assertEqual(s.proceso("E1").motivo, "terminado por SIGPIPE")

    def test_E04_tuberia_multilector_corrompe(self):
        _, c = correr("tuberia_multilector")
        self.assertGreater(c["C1"]["corruptos"], 0)

    def test_E05_memoria_sin_sync_carrera(self):
        _, c = correr("memoria_sin_sync")
        self.assertGreater(c["C1"]["sobrescritos"] + c["C1"]["lecturas_invalidas"], 0)
        self.assertGreater(c["C1"]["perdidos"], 0)

    def test_E06_mutex_huerfano(self):
        s, _ = correr("mutex_huerfano")
        self.assertTrue(s.estancado)
        self.assertIn("nunca será liberado", s.diagnostico)

    def test_E07_interbloqueo_detectado(self):
        s, _ = correr("interbloqueo")
        self.assertTrue(s.estancado)
        self.assertIn("INTERBLOQUEO", s.diagnostico)

    def test_E08_config_invalida(self):
        for malo in (dict(capacidad=0), dict(n_emisores=99), dict(mecanismo="socket"),
                     dict(mecanismo="tuberia", capacidad=5), dict(timeout=-1)):
            with self.assertRaises(ValueError, msg=str(malo)):
                Simulador(ConfigSimulacion(**malo))

    def test_E09_accion_invalida(self):
        with self.assertRaises(ValueError):
            Accion("borrar", "C1")
        with self.assertRaises(ValueError):
            Accion("enviar")

    def test_E10_canal_inexistente(self):
        canales = {"C1": crear_mecanismo("cola", "C1", 2)}
        p = Proceso("X", "emisor", [Accion("enviar", "NOEXISTE", "hola")])
        with self.assertRaises(ValueError):
            Simulador(ConfigSimulacion(), procesos=[p], canales=canales)

    def test_E11_mensaje_mayor_que_tuberia(self):
        canales = {"T": crear_mecanismo("tuberia", "T", 20)}
        e = Proceso("E", "emisor", [Accion("enviar", "T", "x" * 40)])
        r = Proceso("R", "receptor", [Accion("recibir", "T")], repetir=True)
        s = Simulador(ConfigSimulacion(mecanismo="tuberia", capacidad=20),
                      procesos=[e, r], canales=canales).ejecutar()
        self.assertEqual(s.proceso("E").errores, 1)

    def test_E12_fallos_no_aplicables(self):
        s = Simulador(ConfigSimulacion())
        s.inyectar_fallo("R1", "caer")
        self.assertIn("ya no está activo", s.inyectar_fallo("R1", "caer"))
        self.assertIn("no tiene un fallo recuperable", s.inyectar_fallo("R1", "recuperar"))
        with self.assertRaises(KeyError):
            s.inyectar_fallo("Z9", "caer")


class Experimento(unittest.TestCase):
    def test_X01_comparacion_misma_carga(self):
        base = ConfigSimulacion(n_emisores=3, n_receptores=2, mensajes_por_emisor=6, capacidad=4)
        filas = comparar(base)
        self.assertEqual(len(filas), 4)
        self.assertTrue(all(f["_programados"] == 18 for f in filas))
        cola = filas[0]
        self.assertEqual(cola["Perdidos"], 0)

    def test_X02_comparacion_con_fallo(self):
        base = ConfigSimulacion(n_emisores=2, n_receptores=1, mensajes_por_emisor=6, capacidad=3)
        filas = comparar(base, fallo_receptor_tick=6)
        finales = {f["Mecanismo"]: f["Final"] for f in filas}
        self.assertEqual(finales["Tubería"], "SIGPIPE")
        self.assertEqual(finales["Cola de mensajes"], "Estancado")


if __name__ == "__main__":
    unittest.main(verbosity=2)
