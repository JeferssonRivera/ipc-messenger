"""
Pruebas de la API web (Flask). IDs W01–W08 en docs/matriz_pruebas.md.

    python -m unittest -v
"""
import unittest

try:
    from web.servidor import app
except ImportError:          # Flask no instalado: se omiten estas pruebas
    app = None


@unittest.skipIf(app is None, "Flask no está instalado")
class ApiWeb(unittest.TestCase):
    def setUp(self):
        self.c = app.test_client()

    def simular(self, **receta):
        r = self.c.post("/api/simular", json=receta)
        return r, r.get_json()

    def test_W01_pagina_con_creditos_y_logo(self):
        html = self.c.get("/").get_data(as_text=True)
        for texto in ("Software desarrollado por", "Jefersson Hernando Rivera Peñaranda",
                      "Victor Manuel Ortega Blanco", "Cristian Miranda Zuluaga",
                      "Sistemas Operativos", "Álvaro Salamanca", "logo_usb.png",
                      "logo_sistemas_verde.png", "ticks lógicos", 'data-idioma="en"', "i18n.js"):
            self.assertIn(texto, html)
        for recurso in ("img/logo_usb.png", "img/logo_sistemas_verde.png",
                        "img/logo_sistemas_blanco.png", "js/i18n.js"):
            self.assertEqual(self.c.get(f"/static/{recurso}").status_code, 200, recurso)

    def test_W02_escenarios(self):
        datos = self.c.get("/api/escenarios").get_json()
        self.assertEqual(len(datos), 15)
        self.assertIn("config", datos[0])

    def test_W03_receta_avanzar_y_terminar(self):
        r, d = self.simular(escenario="normal_cola", ops=[])
        self.assertEqual(r.status_code, 200)
        self.assertEqual(d["tick"], 0)
        _, d = self.simular(escenario="normal_cola", ops=[["p", 3]])
        self.assertEqual(d["tick"], 3)
        _, d = self.simular(escenario="normal_cola", ops=[["p", 3], ["e"]])
        self.assertTrue(d["finalizado"])
        self.assertEqual(d["metricas"]["canales"]["C1"]["entregados"], 10)

    def test_W04_reproduccion_determinista(self):
        """Sin estado en el servidor: la misma receta da exactamente el mismo resultado."""
        receta = dict(escenario="memoria_sin_sync", ops=[["p", 7], ["f", "R1", "lento", 3], ["p", 10]])
        _, a = self.simular(**receta)
        _, b = self.simular(**receta)
        self.assertEqual(a["metricas"], b["metricas"])
        self.assertEqual(a["eventos_total"], b["eventos_total"])
        # paso a paso == de una sola vez
        _, c = self.simular(escenario="cola_llena", ops=[["p", 1]] * 12)
        _, d = self.simular(escenario="cola_llena", ops=[["p", 12]])
        self.assertEqual(c["metricas"], d["metricas"])

    def test_W05_fallos_y_estancamiento(self):
        _, d = self.simular(escenario="normal_cola", ops=[["f", "R1", "caer", 3]])
        self.assertEqual(d["mensaje"], "")
        _, d = self.simular(escenario="normal_cola",
                            ops=[["f", "R1", "caer", 3], ["f", "R2", "caer", 3], ["e"]])
        self.assertTrue(d["estancado"])
        _, d = self.simular(escenario="normal_cola", ops=[["f", "R1", "caer", 3], ["f", "R1", "caer", 3]])
        self.assertIn("ya no está activo", d["mensaje"])
        r, _ = self.simular(escenario="normal_cola", ops=[["f", "ZZ", "caer", 3]])
        self.assertEqual(r.status_code, 400)

    def test_W06_validacion_de_entradas(self):
        for cfg in ({"capacidad": "abc"}, {"n_emisores": 0}, {"mecanismo": "socket"},
                    {"bloqueante": "si"}, {"campo_raro": 1}):
            r, d = self.simular(config=cfg, ops=[])
            self.assertEqual(r.status_code, 400, cfg)
            self.assertFalse(d["ok"])
            self.assertTrue(d["errores"])
        for ops in ("x", [["z"]], [["p", 0]], [["p", True]], [["f", "R1", "borrar", 3]],
                    [["p", 5000]] * 6):
            r, _ = self.simular(escenario="normal_cola", ops=ops)
            self.assertEqual(r.status_code, 400, ops)
        r, _ = self.simular(escenario="no_existe", ops=[])
        self.assertEqual(r.status_code, 400)

    def test_W07_exportar(self):
        receta = {"escenario": "cola_llena", "ops": [["e"]]}
        csv = self.c.post("/api/exportar", json=receta | {"formato": "csv"})
        self.assertIn("tick;origen;nivel;evento", csv.get_data(as_text=True))
        js = self.c.post("/api/exportar", json=receta | {"formato": "json"}).get_json()
        self.assertIn("metricas", js)
        self.assertEqual(len(js["desarrollado_por"]), 3)
        self.assertEqual(js["docente"], "Ing. Álvaro Salamanca")

    def test_W08_experimento(self):
        d = self.c.post("/api/experimento", json={"config": {"n_emisores": 2, "n_receptores": 1},
                                                  "fallo_tick": 6}).get_json()
        self.assertEqual(len(d["filas"]), 4)
        finales = {f["Mecanismo"]: f["Final"] for f in d["filas"]}
        self.assertEqual(finales["Tubería"], "SIGPIPE")


if __name__ == "__main__":
    unittest.main(verbosity=2)
