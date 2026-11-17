"""
Interfaz gráfica de IPC Messenger (Tkinter, incluido con Python).

La interfaz SÓLO dibuja y recoge datos; toda la lógica de simulación vive
en el paquete ipc_sim (separación lógica / interfaz).
"""
from __future__ import annotations

import csv
import json
import queue
import threading
import tkinter as tk
from dataclasses import asdict
from tkinter import filedialog, messagebox, ttk

from ipc_sim import ESCENARIOS, POR_CLAVE, ConfigSimulacion, Estado, Simulador
from ipc_sim.experimento import COLUMNAS, comparar, conclusiones
from ipc_sim.mecanismos import ColaMensajes, MemoriaCompartida, NOMBRES_MECANISMO, Tuberia

# ------------------------------------------------------------------ estilo
FONDO = "#f5f7fb"
PANEL = "#ffffff"
TINTA = "#1e293b"
TENUE = "#64748b"
BORDE = "#cbd5e1"
ACENTO = "#1d4ed8"
COLOR_ESTADO = {
    Estado.NUEVO: "#94a3b8", Estado.LISTO: "#3b82f6", Estado.EJECUCION: "#16a34a",
    Estado.BLOQUEADO: "#f59e0b", Estado.ESPERA_ACTIVA: "#ea580c",
    Estado.NO_RESPONDE: "#8b5cf6", Estado.CAIDO: "#dc2626", Estado.TERMINADO: "#475569",
}
COLOR_LOG = {"info": "#334155", "ok": "#15803d", "bloqueo": "#b45309",
             "alerta": "#c2410c", "error": "#b91c1c"}
MECANISMO_DE_TEXTO = {v: k for k, v in NOMBRES_MECANISMO.items()}
PERSONALIZADO = "— Personalizado —"

CONCEPTOS = """IPC MESSENGER — CONCEPTOS DE SISTEMAS OPERATIVOS REPRESENTADOS

▌ ¿Qué es IPC?
La comunicación entre procesos (Inter-Process Communication) son los mecanismos que ofrece el sistema operativo para que procesos con espacios de memoria aislados intercambien datos y se coordinen. Existen dos familias: PASO DE MENSAJES (el núcleo copia los datos: colas, tuberías) y MEMORIA COMPARTIDA (los procesos acceden a la misma región y deben sincronizarse ellos mismos).

▌ Cola de mensajes (System V msgsnd/msgrcv, POSIX mq_send/mq_receive)
• Conserva los límites de cada mensaje y su orden FIFO (opcionalmente por prioridad).
• Capacidad limitada: con la cola llena el emisor se BLOQUEA (o recibe EAGAIN si es no bloqueante).
• Admite varios emisores y varios receptores sin corromper mensajes.
• Limitación: si el receptor muere la cola no avisa; los mensajes se acumulan hasta llenarla.

▌ Tubería (pipe)
• Flujo de BYTES unidireccional; no existen "mensajes": el lector debe delimitarlos (aquí con '\\n').
• read() puede devolver menos bytes de los pedidos (lecturas parciales).
• Escritura sin lectores vivos → error EPIPE y señal SIGPIPE (termina al escritor por defecto).
• Lectura sin escritores y sin datos → read() = 0 (EOF).
• Con varios lectores las lecturas parciales se intercalan y los mensajes se corrompen.

▌ Memoria compartida (shmget/mmap) + sincronización
• Es la más rápida (no hay copia por el núcleo) pero NO trae sincronización.
• Se modela un búfer circular productor–consumidor. Escribir/leer NO es atómico: leer índice → escribir ranura → actualizar índice y contador.
• Sin sincronización: dos procesos leen el mismo índice en el mismo tick y se pisan (CONDICIÓN DE CARRERA), además esperan sondeando (ESPERA ACTIVA).
• Con sincronización: semáforo 'vacíos' (espacios libres), semáforo 'llenos' (datos disponibles) y un MUTEX para la sección crítica. Los procesos DUERMEN (Bloqueado) en lugar de sondear.
• Peligro: si un proceso muere con el mutex tomado, nadie más entra (mutex huérfano).

▌ Estados de proceso usados
Nuevo → Listo → Ejecución → (Bloqueado | Espera activa) → … → Terminado.
Fallos inyectables: Caído (crash permanente), No responde (congelado, recuperable), Lento.

▌ Fallos, timeouts e interbloqueo
• Un receptor que deja de responder provoca que los emisores se bloqueen indefinidamente.
• Un TIMEOUT permite al emisor detectar la falta de respuesta y descartar el mensaje.
• Interbloqueo: A espera recibir de B y B espera recibir de A (espera circular). El simulador construye un grafo de espera y detecta el ciclo.

▌ Simplificaciones del modelo (declaradas explícitamente)
• Es una SIMULACIÓN de tiempo discreto: los tiempos son TICKS lógicos, no mediciones reales.
• Cada proceso vivo ejecuta como máximo un paso por tick (concurrencia idealizada, sin planificador de CPU ni cambios de contexto).
• El orden de atención rota cada tick; es determinista con la misma semilla (resultados reproducibles).
• Un proceso bloqueado reintenta en cada tick (equivale a ser despertado al cambiar el recurso).
• No se modelan permisos, claves IPC, tamaños máximos del sistema ni copias de memoria.
• La pestaña "IPC real" sí usa procesos reales del SO (multiprocessing) para contrastar.
"""


class Campo:
    """Etiqueta + Spinbox entero con validación."""

    def __init__(self, padre, fila, texto, desde, hasta, valor, ayuda=""):
        ttk.Label(padre, text=texto).grid(row=fila, column=0, sticky="w", pady=2)
        self.var = tk.StringVar(value=str(valor))
        self.spin = ttk.Spinbox(padre, from_=desde, to=hasta, textvariable=self.var, width=6)
        self.spin.grid(row=fila, column=1, sticky="e", pady=2)
        self.texto, self.desde, self.hasta = texto, desde, hasta
        if ayuda:
            Tooltip(self.spin, ayuda)

    def valor(self) -> int:
        bruto = self.var.get().strip()
        try:
            v = int(bruto)
        except ValueError:
            raise ValueError(f"«{self.texto}» debe ser un número entero (escribiste «{bruto}»).")
        if not self.desde <= v <= self.hasta:
            raise ValueError(f"«{self.texto}» debe estar entre {self.desde} y {self.hasta}.")
        return v

    def poner(self, v):
        self.var.set(str(v))


class Tooltip:
    def __init__(self, widget, texto):
        self.widget, self.texto, self.tip = widget, texto, None
        widget.bind("<Enter>", self.mostrar)
        widget.bind("<Leave>", self.ocultar)

    def mostrar(self, _):
        x, y = self.widget.winfo_rootx() + 20, self.widget.winfo_rooty() + 24
        self.tip = tk.Toplevel(self.widget)
        self.tip.wm_overrideredirect(True)
        self.tip.wm_geometry(f"+{x}+{y}")
        tk.Label(self.tip, text=self.texto, bg="#fffbe6", relief="solid", bd=1,
                 font=("Segoe UI", 9), wraplength=260, justify="left").pack()

    def ocultar(self, _):
        if self.tip:
            self.tip.destroy()
            self.tip = None


# ===========================================================================
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("IPC Messenger — Comunicación entre procesos · Sistemas Operativos")
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"{min(1400, sw - 20)}x{min(860, sh - 70)}+5+5")
        self.minsize(1000, 640)
        self.configure(bg=FONDO)
        self._estilos()
        self.sim: Simulador | None = None
        self.corriendo = False
        self.seleccion = None
        self.cajas = {}   # pid -> bbox en canvas
        self._ultimo_log = 0

        self._encabezado()
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.tab_sim = ttk.Frame(nb, style="Fondo.TFrame")
        self.tab_exp = ttk.Frame(nb, style="Fondo.TFrame")
        self.tab_real = ttk.Frame(nb, style="Fondo.TFrame")
        self.tab_con = ttk.Frame(nb, style="Fondo.TFrame")
        nb.add(self.tab_sim, text="  🧪 Simulador  ")
        nb.add(self.tab_exp, text="  📊 Experimento comparativo  ")
        nb.add(self.tab_real, text="  ⚙ IPC real (procesos del SO)  ")
        nb.add(self.tab_con, text="  📘 Conceptos y simplificaciones  ")
        self._construir_simulador()
        self._construir_experimento()
        self._construir_real()
        self._construir_conceptos()
        self.cargar_escenario(ESCENARIOS[0].titulo)
        try:
            self.state("zoomed")          # Windows: abrir maximizada
        except tk.TclError:
            pass

    # ----------------------------------------------------------- estilo base
    def _estilos(self):
        st = ttk.Style(self)
        try:
            st.theme_use("clam")
        except tk.TclError:
            pass
        st.configure(".", font=("Segoe UI", 10), background=FONDO, foreground=TINTA)
        st.configure("Fondo.TFrame", background=FONDO)
        st.configure("Panel.TFrame", background=PANEL)
        st.configure("Panel.TLabelframe", background=PANEL)
        st.configure("Panel.TLabelframe.Label", background=PANEL, foreground=ACENTO,
                     font=("Segoe UI", 10, "bold"))
        st.configure("TLabel", background=PANEL)
        st.configure("Tenue.TLabel", foreground=TENUE, background=PANEL, font=("Segoe UI", 9))
        st.configure("Acento.TButton", font=("Segoe UI", 10, "bold"))
        st.configure("Treeview", rowheight=22, font=("Segoe UI", 9))
        st.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"))
        st.configure("TCheckbutton", background=PANEL)

    def _encabezado(self):
        f = tk.Frame(self, bg="#0f2a4a")
        f.pack(fill="x", padx=10, pady=10)
        tk.Label(f, text="IPC Messenger", bg="#0f2a4a", fg="white",
                 font=("Segoe UI", 18, "bold")).pack(side="left", padx=14, pady=8)
        tk.Label(f, text="Proyecto 9 · Comunicación entre procesos · Sistemas Operativos",
                 bg="#0f2a4a", fg="#cbd5e1", font=("Segoe UI", 10)).pack(side="left")
        tk.Label(f, text="⚠ SIMULACIÓN: los tiempos son ticks lógicos, no mediciones reales",
                 bg="#fde68a", fg="#78350f", font=("Segoe UI", 9, "bold"),
                 padx=8, pady=3).pack(side="right", padx=12)

    # ======================================================= pestaña SIMULADOR
    def _construir_simulador(self):
        raiz = self.tab_sim
        raiz.columnconfigure(1, weight=1)
        raiz.rowconfigure(0, weight=1)

        # ---------------- panel izquierdo: configuración
        contenedor = ttk.Frame(raiz, style="Panel.TFrame")
        contenedor.grid(row=0, column=0, sticky="ns", padx=(0, 8))
        contenedor.rowconfigure(0, weight=1)
        lienzo = tk.Canvas(contenedor, bg=PANEL, highlightthickness=0, width=300)
        barra_y = ttk.Scrollbar(contenedor, orient="vertical", command=lienzo.yview)
        lienzo.configure(yscrollcommand=barra_y.set)
        lienzo.grid(row=0, column=0, sticky="ns")
        barra_y.grid(row=0, column=1, sticky="ns")
        izq = ttk.Frame(lienzo, style="Panel.TFrame", padding=8)
        lienzo.create_window((0, 0), window=izq, anchor="nw")

        def _ajustar(_e=None):
            lienzo.configure(scrollregion=lienzo.bbox("all"), width=izq.winfo_reqwidth())
        izq.bind("<Configure>", _ajustar)
        lienzo.bind("<Enter>", lambda e: lienzo.bind_all(
            "<MouseWheel>", lambda ev: lienzo.yview_scroll(int(-ev.delta / 120), "units")))
        lienzo.bind("<Leave>", lambda e: lienzo.unbind_all("<MouseWheel>"))

        lf = ttk.LabelFrame(izq, text="Escenario", style="Panel.TLabelframe", padding=8)
        lf.pack(fill="x")
        self.var_escenario = tk.StringVar()
        cb = ttk.Combobox(lf, textvariable=self.var_escenario, state="readonly", width=40,
                          values=[PERSONALIZADO] + [e.titulo for e in ESCENARIOS])
        cb.configure(width=30)
        cb.pack(fill="x")
        cb.bind("<<ComboboxSelected>>", lambda e: self.cargar_escenario(self.var_escenario.get()))
        self.lbl_desc = ttk.Label(lf, text="", style="Tenue.TLabel", wraplength=240, justify="left")
        self.lbl_desc.pack(fill="x", pady=(6, 0))

        ttk.Button(izq, text="⟲  Aplicar cambios y reiniciar", style="Acento.TButton",
                   command=self.reiniciar).pack(fill="x", pady=(8, 0))
        lf = ttk.LabelFrame(izq, text="Configuración", style="Panel.TLabelframe", padding=8)
        lf.pack(fill="x", pady=8)
        lf.columnconfigure(0, weight=1)
        ttk.Label(lf, text="Mecanismo IPC").grid(row=0, column=0, sticky="w")
        self.var_mec = tk.StringVar(value=NOMBRES_MECANISMO["cola"])
        cbm = ttk.Combobox(lf, textvariable=self.var_mec, state="readonly", width=17,
                           values=list(NOMBRES_MECANISMO.values()))
        cbm.grid(row=0, column=1, sticky="e")
        cbm.bind("<<ComboboxSelected>>", lambda e: self._personalizado())
        self.f_cap = Campo(lf, 1, "Capacidad", 1, 4096, 4,
                           "Cola: nº de mensajes. Tubería: bytes. Memoria: ranuras del búfer.")
        self.f_em = Campo(lf, 2, "Emisores", 1, 8, 2)
        self.f_rec = Campo(lf, 3, "Receptores", 1, 8, 1)
        self.f_msg = Campo(lf, 4, "Mensajes por emisor", 1, 200, 5)
        self.f_int = Campo(lf, 5, "Ticks entre envíos", 1, 50, 1)
        self.f_trec = Campo(lf, 6, "Ticks proceso receptor", 1, 50, 2,
                           "Ticks que tarda el receptor en procesar cada mensaje.")
        self.f_to = Campo(lf, 7, "Timeout (0 = sin)", 0, 500, 0,
                          "Ticks que un proceso espera antes de abandonar la operación.")
        self.f_lec = Campo(lf, 8, "Bytes por read()", 1, 4096, 64)
        self.f_var = Campo(lf, 9, "Variación ±ticks", 0, 10, 0,
                          "Variación aleatoria (reproducible con la semilla) en los cómputos.")
        self.f_sem = Campo(lf, 10, "Semilla", 0, 999999, 42)
        self.var_bloq = tk.BooleanVar(value=True)
        self.var_sync = tk.BooleanVar(value=True)
        self.var_prio = tk.BooleanVar(value=False)
        ttk.Checkbutton(lf, text="Operaciones bloqueantes", variable=self.var_bloq).grid(
            row=11, column=0, columnspan=2, sticky="w")
        ttk.Checkbutton(lf, text="Memoria: mutex+semáforos", variable=self.var_sync).grid(
            row=12, column=0, columnspan=2, sticky="w")
        ttk.Checkbutton(lf, text="Cola: prioridad aleatoria", variable=self.var_prio).grid(
            row=13, column=0, columnspan=2, sticky="w")

        # ---------------- centro: controles + lienzo
        centro = ttk.Frame(raiz, style="Fondo.TFrame")
        centro.grid(row=0, column=1, sticky="nsew")
        centro.rowconfigure(2, weight=1)
        centro.columnconfigure(0, weight=1)
        barra = ttk.Frame(centro, style="Panel.TFrame", padding=6)
        barra.grid(row=0, column=0, sticky="ew")
        self.btn_run = ttk.Button(barra, text="▶ Ejecutar", style="Acento.TButton", command=self.alternar, width=10)
        self.btn_run.pack(side="left")
        ttk.Button(barra, text="⏭ Paso", command=self.un_paso, width=8).pack(side="left", padx=4)
        ttk.Button(barra, text="⏩ Al final", command=self.hasta_final, width=9).pack(side="left")
        ttk.Label(barra, text="  Velocidad").pack(side="left")
        self.var_vel = tk.IntVar(value=350)
        ttk.Scale(barra, from_=900, to=40, variable=self.var_vel, length=80).pack(side="left", padx=4)
        ttk.Button(barra, text="💾 Exportar", command=self.exportar, width=10).pack(side="right")

        barra2 = ttk.Frame(centro, style="Panel.TFrame", padding=(6, 0, 6, 6))
        barra2.grid(row=1, column=0, sticky="ew")
        ttk.Label(barra2, text="Fallo en", foreground=ACENTO,
                  font=("Segoe UI", 10, "bold")).pack(side="left")
        self.var_proc = tk.StringVar()
        self.cb_proc = ttk.Combobox(barra2, textvariable=self.var_proc, state="readonly", width=6)
        self.cb_proc.pack(side="left", padx=4)
        for txt, tipo in [("💥 Caer", "caer"), ("🧊 Congelar", "no_responder"),
                          ("🐢 Lento", "lento"), ("✅ Recuperar", "recuperar")]:
            ttk.Button(barra2, text=txt, command=lambda t=tipo: self.fallo(t)).pack(side="left", padx=1, ipadx=0)
        self.lbl_estado = ttk.Label(barra2, text="", foreground=TENUE)
        self.lbl_estado.pack(side="right")
        self.lbl_tick = ttk.Label(barra2, text="Tick 0", font=("Segoe UI", 11, "bold"))
        self.lbl_tick.pack(side="right", padx=10)

        self.canvas = tk.Canvas(centro, bg="white", highlightthickness=1, highlightbackground=BORDE)
        self.canvas.grid(row=2, column=0, sticky="nsew", pady=(6, 0))
        self.canvas.bind("<Configure>", lambda e: self.dibujar())
        self.canvas.bind("<Button-1>", self._clic_canvas)

        # ---------------- derecha: métricas + registro
        der = ttk.Frame(raiz, style="Panel.TFrame", padding=8)
        der.grid(row=0, column=2, sticky="ns", padx=(8, 0))
        der.rowconfigure(3, weight=1)
        ttk.Label(der, text="Métricas", font=("Segoe UI", 11, "bold"), foreground=ACENTO).grid(
            row=0, column=0, sticky="w")
        self.tree_met = ttk.Treeview(der, columns=("v",), show="tree headings", height=13)
        self.tree_met.heading("#0", text="Indicador")
        self.tree_met.heading("v", text="Valor")
        self.tree_met.column("#0", width=175)
        self.tree_met.column("v", width=70, anchor="e")
        self.tree_met.grid(row=1, column=0, sticky="ew")
        ttk.Label(der, text="Registro de eventos", font=("Segoe UI", 11, "bold"),
                  foreground=ACENTO).grid(row=2, column=0, sticky="w", pady=(8, 0))
        marco = ttk.Frame(der, style="Panel.TFrame")
        marco.grid(row=3, column=0, sticky="nsew")
        marco.rowconfigure(0, weight=1)
        self.txt_log = tk.Text(marco, width=38, wrap="word", font=("Consolas", 9),
                               bg="#f8fafc", relief="flat", state="disabled")
        sb = ttk.Scrollbar(marco, command=self.txt_log.yview)
        self.txt_log.configure(yscrollcommand=sb.set)
        self.txt_log.grid(row=0, column=0, sticky="nsew")
        sb.grid(row=0, column=1, sticky="ns")
        for n, c in COLOR_LOG.items():
            self.txt_log.tag_configure(n, foreground=c)
        self.txt_log.tag_configure("tick", foreground="#94a3b8")

    # -------------------------------------------------------- config / escenarios
    def _personalizado(self):
        self.var_escenario.set(PERSONALIZADO)
        self.lbl_desc.configure(text="Configuración libre. Pulsa «Aplicar y reiniciar».")

    def _leer_config(self) -> ConfigSimulacion:
        return ConfigSimulacion(
            mecanismo=MECANISMO_DE_TEXTO[self.var_mec.get()],
            capacidad=self.f_cap.valor(), n_emisores=self.f_em.valor(),
            n_receptores=self.f_rec.valor(), mensajes_por_emisor=self.f_msg.valor(),
            intervalo_emisor=self.f_int.valor(), tiempo_receptor=self.f_trec.valor(),
            timeout=self.f_to.valor(), tam_lectura=self.f_lec.valor(),
            variacion=self.f_var.valor(), semilla=self.f_sem.valor(),
            bloqueante=self.var_bloq.get(), sincronizada=self.var_sync.get(),
            por_prioridad=self.var_prio.get())

    def _poner_config(self, c: ConfigSimulacion):
        self.var_mec.set(NOMBRES_MECANISMO[c.mecanismo])
        for campo, v in ((self.f_cap, c.capacidad), (self.f_em, c.n_emisores),
                         (self.f_rec, c.n_receptores), (self.f_msg, c.mensajes_por_emisor),
                         (self.f_int, c.intervalo_emisor), (self.f_trec, c.tiempo_receptor),
                         (self.f_to, c.timeout), (self.f_lec, c.tam_lectura),
                         (self.f_var, c.variacion), (self.f_sem, c.semilla)):
            campo.poner(v)
        self.var_bloq.set(c.bloqueante)
        self.var_sync.set(c.sincronizada)
        self.var_prio.set(c.por_prioridad)

    def cargar_escenario(self, titulo):
        self.pausar()
        self.var_escenario.set(titulo)
        esc = next((e for e in ESCENARIOS if e.titulo == titulo), None)
        if not esc:
            self._personalizado()
            return
        self._poner_config(ConfigSimulacion(**esc.config))
        fallos = ", ".join(f"{f['tipo']} {f['pid']} @tick {f['tick']}" for f in esc.fallos)
        self.lbl_desc.configure(text=f"[{esc.tipo.upper()}] {esc.descripcion}\n"
                                     f"Esperado: {esc.esperado}"
                                     + (f"\nFallos programados: {fallos}" if fallos else ""))
        try:
            self._instalar(esc.crear())
        except ValueError as e:
            messagebox.showerror("Escenario inválido", str(e))

    def reiniciar(self):
        self.pausar()
        esc = next((e for e in ESCENARIOS if e.titulo == self.var_escenario.get()), None)
        try:
            cfg = self._leer_config()
            if esc and asdict(cfg) == asdict(ConfigSimulacion(**esc.config)):
                sim = esc.crear()          # sin cambios: se respeta el escenario (fallos incluidos)
            elif esc and esc.constructor:
                sim = esc.constructor(cfg)  # misma topología con otros parámetros
            else:
                if esc:
                    self._personalizado()
                sim = Simulador(cfg)
        except ValueError as e:
            messagebox.showerror("Datos inválidos", str(e))
            return
        self._instalar(sim)

    def _instalar(self, sim: Simulador):
        self.sim = sim
        self._ultimo_log = 0
        self.txt_log.configure(state="normal")
        self.txt_log.delete("1.0", "end")
        self.txt_log.configure(state="disabled")
        pids = [p.pid for p in sim.procesos]
        self.cb_proc.configure(values=pids)
        self.var_proc.set(pids[-1])
        self.seleccion = pids[-1]
        self.refrescar()

    # ---------------------------------------------------------- ejecución
    def alternar(self):
        if self.corriendo:
            self.pausar()
        else:
            if not self.sim or self.sim.finalizado:
                self.reiniciar()
            self.corriendo = True
            self.btn_run.configure(text="⏸ Pausa")
            self._bucle()

    def pausar(self):
        self.corriendo = False
        if hasattr(self, "btn_run"):
            self.btn_run.configure(text="▶ Ejecutar")

    def _bucle(self):
        if not self.corriendo or not self.sim:
            return
        sigue = self.sim.paso()
        self.refrescar()
        if not sigue:
            self.pausar()
            if self.sim.estancado:
                messagebox.showwarning("Estancamiento detectado", self.sim.diagnostico +
                                       "\n\nPuedes recuperar un proceso y continuar.")
            return
        self.after(int(self.var_vel.get()), self._bucle)

    def un_paso(self):
        if not self.sim:
            return
        self.pausar()
        self.sim.paso()
        self.refrescar()

    def hasta_final(self):
        if not self.sim:
            return
        self.pausar()
        self.sim.ejecutar()
        self.refrescar()
        if self.sim.estancado:
            messagebox.showwarning("Estancamiento detectado", self.sim.diagnostico)

    def fallo(self, tipo):
        if not self.sim:
            return
        pid = self.var_proc.get()
        if not pid:
            messagebox.showinfo("Fallo", "Selecciona un proceso.")
            return
        error = self.sim.inyectar_fallo(pid, tipo)
        if error:
            messagebox.showinfo("No aplicable", error)
        self.refrescar()

    def _clic_canvas(self, ev):
        for pid, (x0, y0, x1, y1) in self.cajas.items():
            if x0 <= ev.x <= x1 and y0 <= ev.y <= y1:
                self.var_proc.set(pid)
                self.seleccion = pid
                self.dibujar()
                return

    # ----------------------------------------------------------- refresco
    def refrescar(self):
        s = self.sim
        if not s:
            return
        self.lbl_tick.configure(text=f"Tick {s.tick}")
        if s.estancado:
            txt, col = "⛔ Estancado", "#b91c1c"
        elif s.finalizado:
            txt, col = "■ Finalizado", "#15803d"
        else:
            txt, col = ("● En ejecución" if self.corriendo else "● Listo para avanzar"), TENUE
        self.lbl_estado.configure(text=txt, foreground=col)
        self._metricas()
        self._log()
        self.dibujar()

    def _metricas(self):
        t = self.tree_met
        t.delete(*t.get_children())
        m = self.sim.metricas()
        g = t.insert("", "end", text="General", open=True)
        for k, v in (("Ticks", m["ticks"]), ("Ticks bloqueado (Σ)", m["ticks_bloqueado"]),
                     ("Ticks espera activa", m["ticks_espera_activa"])):
            t.insert(g, "end", text=k, values=(v,))
        nombres = {"enviados": "Enviados", "entregados": "Entregados",
                   "en_transito": "Pendientes en canal", "perdidos": "Perdidos",
                   "rechazados_eagain": "Rechazados (EAGAIN)",
                   "descartados_timeout": "Descartados por timeout", "epipe": "EPIPE",
                   "corruptos": "Corruptos", "sobrescritos": "Sobrescritos (carrera)",
                   "lecturas_invalidas": "Lecturas inválidas", "max_ocupacion": "Ocupación máxima",
                   "latencia_prom": "Latencia prom. (ticks)", "latencia_max": "Latencia máx."}
        for n, c in m["canales"].items():
            nodo = t.insert("", "end", text=f"Canal {n} · {NOMBRES_MECANISMO[c['mecanismo']]}", open=True)
            for k, etiqueta in nombres.items():
                if c[k] or k in ("enviados", "entregados", "en_transito", "perdidos"):
                    t.insert(nodo, "end", text=etiqueta, values=(c[k],))
        nodo = t.insert("", "end", text="Procesos (env/rec)", open=False)
        for pid, p in m["procesos"].items():
            t.insert(nodo, "end", text=f"{pid} · {p['estado']}",
                     values=(f"{p['enviados']}/{p['recibidos']}",))

    def _log(self):
        nuevos = self.sim.eventos[self._ultimo_log:]
        if not nuevos:
            return
        self._ultimo_log = len(self.sim.eventos)
        self.txt_log.configure(state="normal")
        for ev in nuevos:
            self.txt_log.insert("end", f"[{ev.tick:>3}] ", "tick")
            self.txt_log.insert("end", f"{ev.origen + ': ' if ev.origen else ''}{ev.texto}\n", ev.nivel)
        self.txt_log.see("end")
        self.txt_log.configure(state="disabled")

    # -------------------------------------------------------------- dibujo
    def dibujar(self):
        cv = self.canvas
        cv.delete("all")
        self.cajas = {}
        if not self.sim:
            return
        W, H = max(cv.winfo_width(), 520), max(cv.winfo_height(), 380)
        s = self.sim
        alto_graf = 100
        area_h = H - alto_graf - 75

        izq = [p for p in s.procesos if p.rol == "emisor"]
        der = [p for p in s.procesos if p.rol == "receptor"]
        mixtos = [p for p in s.procesos if p.rol == "mixto"]
        for i, p in enumerate(mixtos):
            (izq if i % 2 == 0 else der).append(p)

        cw, ch = int(min(180, max(135, W * 0.21))), 80
        margen = 14
        xs = {"izq": margen, "der": W - margen - cw}
        hueco = max(30, int(W * 0.05))
        canal_x0, canal_x1 = xs["izq"] + cw + hueco, xs["der"] - hueco

        # canales
        n_can = len(s.canales)
        pos_canal = {}
        alto_canal = min(150, (area_h - 20) / n_can - 20)
        for i, (nombre, canal) in enumerate(s.canales.items()):
            y0 = 15 + i * (area_h / n_can) + (area_h / n_can - alto_canal) / 2
            pos_canal[nombre] = (canal_x0, y0, canal_x1, y0 + alto_canal)
            self._dibujar_canal(canal, canal_x0, y0, canal_x1, y0 + alto_canal)

        # procesos
        for lado, lista in (("izq", izq), ("der", der)):
            n = len(lista)
            if not n:
                continue
            paso = min(ch + 18, (area_h - 10) / n)
            y_ini = 15 + (area_h - paso * n) / 2
            for i, p in enumerate(lista):
                x0, y0 = xs[lado], y_ini + i * paso
                self.cajas[p.pid] = (x0, y0, x0 + cw, y0 + ch)
                self._conexiones(p, lado, x0, y0, cw, ch, pos_canal)
        for p in s.procesos:
            if p.pid in self.cajas:
                self._dibujar_proceso(p, *self.cajas[p.pid])

        self._leyenda(W, H - alto_graf - 48)
        self._grafica(20, H - alto_graf - 10, W - 20, H - 12)

    def _conexiones(self, p, lado, x0, y0, cw, ch, pos_canal):
        usados = {a.canal: a.tipo for a in p.programa if a.canal}
        for canal, tipo in usados.items():
            cx0, cy0, cx1, cy1 = pos_canal[canal]
            activo = p.op is not None and p.op.canal == canal
            color = COLOR_ESTADO[p.estado] if activo and p.vivo else "#cbd5e1"
            ancho = 3 if activo and p.vivo else 1.5
            py = y0 + ch / 2
            cy = (cy0 + cy1) / 2
            if lado == "izq":
                a, b = (x0 + cw, py), (cx0, cy)
            else:
                a, b = (x0, py), (cx1, cy)
            # flecha en la dirección del flujo de datos
            ini, fin = (a, b) if tipo == "enviar" else (b, a)
            self.canvas.create_line(*ini, *fin, fill=color, width=ancho, arrow="last",
                                    arrowshape=(10, 12, 4), dash=() if activo else (4, 3))

    def _dibujar_proceso(self, p, x0, y0, x1, y1):
        cv = self.canvas
        col = COLOR_ESTADO[p.estado]
        sel = p.pid == self.seleccion
        cv.create_rectangle(x0 + 3, y0 + 3, x1 + 3, y1 + 3, fill="#e2e8f0", outline="")
        cv.create_rectangle(x0, y0, x1, y1, fill="white", outline=ACENTO if sel else col,
                            width=3 if sel else 2)
        cv.create_rectangle(x0, y0, x0 + 7, y1, fill=col, outline="")
        rol = {"emisor": "emisor", "receptor": "receptor", "mixto": "envía/recibe"}[p.rol]
        cv.create_text(x0 + 14, y0 + 12, anchor="w", text=p.pid, font=("Segoe UI", 11, "bold"), fill=TINTA)
        cv.create_text(x1 - 6, y0 + 12, anchor="e", text=rol, font=("Segoe UI", 8), fill=TENUE)
        ancho_pill = 12 + 6.5 * len(p.estado.value)
        cv.create_rectangle(x0 + 14, y0 + 24, x0 + 14 + ancho_pill, y0 + 40, fill=col, outline="")
        cv.create_text(x0 + 14 + ancho_pill / 2, y0 + 32, text=p.estado.value, fill="white",
                       font=("Segoe UI", 8, "bold"))
        if p.lento > 1:
            cv.create_text(x1 - 6, y0 + 32, anchor="e", text=f"lento ×{p.lento}",
                           font=("Segoe UI", 8, "bold"), fill="#7c3aed")
        op = p.descripcion_op()
        if p.op and p.op.tipo == "computar":
            op = f"compute ({p.op_restante} rest.)"
        max_c = max(10, int((x1 - x0 - 20) / 6.2))
        cv.create_text(x0 + 14, y0 + 52, anchor="w", text=op[:max_c], font=("Consolas", 8), fill=TENUE)
        cv.create_text(x0 + 14, y0 + 68, anchor="w",
                       text=f"env {p.enviados} · rec {p.recibidos} · err {p.errores}",
                       font=("Segoe UI", 8), fill=TINTA)

    def _dibujar_canal(self, c, x0, y0, x1, y1):
        cv = self.canvas
        cv.create_rectangle(x0, y0, x1, y1, fill="#f8fafc", outline="#94a3b8", width=2)
        titulo = f"{c.nombre} · {NOMBRES_MECANISMO[c.tipo]}"
        extra = ""
        sub = f"ocupación {c.ocupacion()}/{c.capacidad} {c.unidad}"
        if isinstance(c, MemoriaCompartida):
            sub = ("con mutex + semáforos" if c.sincronizada else "⚠ SIN sincronización") + " · " + sub
        cv.create_text(x0 + 10, y0 + 13, anchor="w", text=titulo,
                       font=("Segoe UI", 10, "bold"), fill=ACENTO)
        cv.create_text(x0 + 10, y0 + 29, anchor="w", text=sub, font=("Segoe UI", 8), fill=TENUE)
        zona_y0, zona_y1 = y0 + 48, y1 - 30
        ancho = x1 - x0 - 20
        if isinstance(c, Tuberia):
            frac = c.ocupacion() / c.capacidad
            cv.create_rectangle(x0 + 10, zona_y0, x1 - 10, zona_y1, outline="#94a3b8", fill="white")
            cv.create_rectangle(x0 + 10, zona_y0, x0 + 10 + ancho * frac, zona_y1,
                                outline="", fill="#bfdbfe")
            texto = c.buf.replace("\n", "⏎")
            max_chars = max(8, int(ancho / 7))
            cv.create_text(x0 + 14, (zona_y0 + zona_y1) / 2, anchor="w",
                           text=(texto[:max_chars] + ("…" if len(texto) > max_chars else "")) or "(vacía)",
                           font=("Consolas", 9), fill=TINTA)
            extra = f"flujo de bytes · read() de {c.tam_lectura} B"
        else:
            n = c.capacidad
            visibles = min(n, max(4, int(ancho // 38)))
            cel = ancho / visibles
            items = c.contenido_visual()
            for i in range(visibles):
                cx0 = x0 + 10 + i * cel
                if isinstance(c, ColaMensajes):
                    val = items[i] if i < len(items) else ""
                else:
                    val = items[i] if items[i] != "·" else ""
                lleno = bool(val)
                cv.create_rectangle(cx0 + 2, zona_y0, cx0 + cel - 2, zona_y1,
                                    fill="#dcfce7" if lleno else "white", outline="#94a3b8")
                if lleno:
                    partes = val.split(" ")
                    txt = partes[0] + "\n" + " ".join(partes[1:]) if cel > 44 else partes[0]
                    cv.create_text(cx0 + cel / 2, (zona_y0 + zona_y1) / 2, text=txt, justify="center",
                                   font=("Segoe UI", 8), fill=TINTA)
                if isinstance(c, MemoriaCompartida):
                    cv.create_text(cx0 + cel / 2, zona_y1 + 8, text=str(i), font=("Segoe UI", 7), fill=TENUE)
                    if i == c.idx_in:
                        cv.create_text(cx0 + 8, zona_y0 - 6, text="in▼", font=("Segoe UI", 7, "bold"), fill="#15803d")
                    if i == c.idx_out:
                        cv.create_text(cx0 + cel - 8, zona_y0 - 6, text="out▼", font=("Segoe UI", 7, "bold"), fill="#b91c1c")
            if n > visibles:
                cv.create_text(x1 - 12, zona_y1 + 8, anchor="e", text=f"(+{n - visibles} no mostradas)",
                               font=("Segoe UI", 7), fill=TENUE)
            if isinstance(c, ColaMensajes):
                extra = "FIFO" + (" por prioridad" if c.por_prioridad else "") + "  · frente ← … ← final"
            else:
                if c.sincronizada:
                    extra = (f"mutex: {c.mutex or 'libre'} · vacíos={c.sem_vacios} · llenos={c.sem_llenos}"
                             f" · contador={c.contador}")
                else:
                    extra = f"contador compartido = {c.contador} (sin protección)"
        cv.create_text(x0 + 10, y1 - 12, anchor="w", text=extra, font=("Segoe UI", 8), fill=TENUE)

    def _leyenda(self, W, y):
        x = 20
        for est, col in COLOR_ESTADO.items():
            if x + 30 + len(est.value) * 6 > W - 10:
                x, y = 20, y + 16
            self.canvas.create_rectangle(x, y - 6, x + 12, y + 6, fill=col, outline="")
            self.canvas.create_text(x + 16, y, anchor="w", text=est.value, font=("Segoe UI", 8), fill=TINTA)
            x += 30 + len(est.value) * 6

    def _grafica(self, x0, y0, x1, y1):
        cv = self.canvas
        cv.create_rectangle(x0, y0, x1, y1, outline="#e2e8f0")
        cv.create_text(x0 + 6, y0 + 8, anchor="w", text="Ocupación del canal por tick",
                       font=("Segoe UI", 8, "bold"), fill=TENUE)
        h = self.sim.historial
        if len(h) < 2:
            return
        colores = ["#2563eb", "#db2777", "#16a34a"]
        n = len(h)
        for i, (nombre, canal) in enumerate(self.sim.canales.items()):
            pts = []
            for k, fila in enumerate(h):
                px = x0 + 10 + (x1 - x0 - 20) * k / (n - 1)
                py = y1 - 6 - (y1 - y0 - 22) * fila[nombre] / canal.capacidad
                pts += [px, py]
            cv.create_line(*pts, fill=colores[i % 3], width=2)
            cv.create_text(x1 - 8, y0 + 8 + 12 * i, anchor="e", text=nombre,
                           fill=colores[i % 3], font=("Segoe UI", 8, "bold"))

    # -------------------------------------------------------------- exportar
    def exportar(self):
        if not self.sim:
            return
        ruta = filedialog.asksaveasfilename(
            title="Exportar evidencia de la simulación", defaultextension=".csv",
            filetypes=[("Registro CSV", "*.csv")], initialfile=f"ipc_tick{self.sim.tick}.csv")
        if not ruta:
            return
        try:
            with open(ruta, "w", newline="", encoding="utf-8-sig") as f:
                w = csv.writer(f, delimiter=";")
                w.writerow(["tick", "origen", "nivel", "evento"])
                for ev in self.sim.eventos:
                    w.writerow([ev.tick, ev.origen, ev.nivel, ev.texto])
            ruta_json = ruta.rsplit(".", 1)[0] + "_metricas.json"
            with open(ruta_json, "w", encoding="utf-8") as f:
                json.dump({"configuracion": asdict(self.sim.config), "metricas": self.sim.metricas()},
                          f, ensure_ascii=False, indent=2)
        except OSError as e:
            messagebox.showerror("Error al exportar", str(e))
            return
        messagebox.showinfo("Exportado", f"Registro: {ruta}\nMétricas: {ruta_json}")

    # ================================================== pestaña EXPERIMENTO
    def _construir_experimento(self):
        raiz = self.tab_exp
        raiz.columnconfigure(1, weight=1)
        raiz.rowconfigure(0, weight=1)
        izq = ttk.Frame(raiz, style="Panel.TFrame", padding=10)
        izq.grid(row=0, column=0, sticky="ns", padx=(0, 8))
        ttk.Label(izq, text="Carga de trabajo común", font=("Segoe UI", 11, "bold"),
                  foreground=ACENTO).grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(izq, text="Se ejecuta la MISMA carga sobre los cuatro mecanismos.",
                  style="Tenue.TLabel", wraplength=260).grid(row=1, column=0, columnspan=2, sticky="w")
        self.e_em = Campo(izq, 2, "Emisores", 1, 8, 3)
        self.e_rec = Campo(izq, 3, "Receptores", 1, 8, 2)
        self.e_msg = Campo(izq, 4, "Mensajes por emisor", 1, 200, 6)
        self.e_cap = Campo(izq, 5, "Capacidad (en mensajes)", 1, 200, 4,
                           "En la tubería se convierte a bytes (≈18 B por mensaje).")
        self.e_int = Campo(izq, 6, "Ticks entre envíos", 1, 50, 1)
        self.e_trec = Campo(izq, 7, "Ticks de proceso receptor", 1, 50, 2)
        self.e_to = Campo(izq, 8, "Timeout (0 = sin límite)", 0, 500, 0)
        self.e_fallo = Campo(izq, 9, "Tick en que cae R1 (0 = sin fallo)", 0, 500, 0)
        self.e_sem = Campo(izq, 10, "Semilla", 0, 999999, 42)
        ttk.Button(izq, text="▶ Ejecutar comparación", style="Acento.TButton",
                   command=self.correr_experimento).grid(row=11, column=0, columnspan=2,
                                                         sticky="ew", pady=(10, 4))
        ttk.Button(izq, text="💾 Exportar tabla CSV", command=self.exportar_experimento).grid(
            row=12, column=0, columnspan=2, sticky="ew")

        der = ttk.Frame(raiz, style="Panel.TFrame", padding=10)
        der.grid(row=0, column=1, sticky="nsew")
        der.columnconfigure(0, weight=1)
        der.rowconfigure(2, weight=1)
        self.tree_exp = ttk.Treeview(der, columns=COLUMNAS, show="headings", height=5)
        for c in COLUMNAS:
            self.tree_exp.heading(c, text=c)
            self.tree_exp.column(c, width=215 if c == "Mecanismo" else 74, minwidth=50,
                                 anchor="w" if c == "Mecanismo" else "center", stretch=True)
        self.tree_exp.grid(row=0, column=0, sticky="ew")
        self.cv_exp = tk.Canvas(der, height=210, bg="white", highlightthickness=0)
        self.cv_exp.grid(row=1, column=0, sticky="ew", pady=8)
        self.txt_exp = tk.Text(der, wrap="word", font=("Segoe UI", 10), relief="flat", bg="#f8fafc",
                               height=10)
        self.txt_exp.grid(row=2, column=0, sticky="nsew")
        self.txt_exp.tag_configure("titulo", font=("Segoe UI", 10, "bold"), foreground=ACENTO)
        self.filas_exp = []

    def correr_experimento(self):
        try:
            base = ConfigSimulacion(
                n_emisores=self.e_em.valor(), n_receptores=self.e_rec.valor(),
                mensajes_por_emisor=self.e_msg.valor(), capacidad=self.e_cap.valor(),
                intervalo_emisor=self.e_int.valor(), tiempo_receptor=self.e_trec.valor(),
                timeout=self.e_to.valor(), semilla=self.e_sem.valor(), max_ticks=5000)
            fallo = self.e_fallo.valor()
            filas = comparar(base, fallo_receptor_tick=fallo)
        except ValueError as e:
            messagebox.showerror("Datos inválidos", str(e))
            return
        self.filas_exp = filas
        self.tree_exp.delete(*self.tree_exp.get_children())
        for f in filas:
            self.tree_exp.insert("", "end", values=[f[c] for c in COLUMNAS])
        self.txt_exp.delete("1.0", "end")
        self.txt_exp.insert("end", "Conclusiones automáticas (ticks simulados)\n", "titulo")
        self.txt_exp.insert("end", "\n".join(conclusiones(filas, base)))
        self._grafica_experimento(filas)

    def _grafica_experimento(self, filas):
        cv = self.cv_exp
        cv.delete("all")
        cv.update_idletasks()
        W, H = max(cv.winfo_width(), 600), 210
        cv.create_text(10, 12, anchor="w", text="Mensajes entregados vs. perdidos (misma carga)",
                       font=("Segoe UI", 10, "bold"), fill=TINTA)
        maximo = max(f["_programados"] for f in filas) or 1
        zona = max(120, W - 480)
        for i, f in enumerate(filas):
            y = 38 + i * 42
            cv.create_text(10, y + 12, anchor="w", text=f["Mecanismo"], font=("Segoe UI", 9), fill=TINTA)
            x = 260
            ent = zona * f["_entregados"] / maximo
            per = zona * f["Perdidos"] / maximo
            cv.create_rectangle(x, y, x + ent, y + 24, fill="#16a34a", outline="")
            cv.create_rectangle(x + ent, y, x + ent + per, y + 24, fill="#dc2626", outline="")
            cv.create_text(x + ent + per + 8, y + 12, anchor="w",
                           text=f"{f['_entregados']} ✔  {f['Perdidos']} ✖  · {f['Final']}",
                           font=("Segoe UI", 9), fill=TENUE)

    def exportar_experimento(self):
        if not self.filas_exp:
            messagebox.showinfo("Sin datos", "Primero ejecuta la comparación.")
            return
        ruta = filedialog.asksaveasfilename(defaultextension=".csv", initialfile="experimento_ipc.csv",
                                            filetypes=[("CSV", "*.csv")])
        if not ruta:
            return
        try:
            with open(ruta, "w", newline="", encoding="utf-8-sig") as f:
                w = csv.writer(f, delimiter=";")
                w.writerow(COLUMNAS)
                for fila in self.filas_exp:
                    w.writerow([fila[c] for c in COLUMNAS])
        except OSError as e:
            messagebox.showerror("Error al exportar", str(e))
            return
        messagebox.showinfo("Exportado", ruta)

    # ===================================================== pestaña IPC REAL
    def _construir_real(self):
        raiz = self.tab_real
        f = ttk.Frame(raiz, style="Panel.TFrame", padding=12)
        f.pack(fill="both", expand=True)
        ttk.Label(f, text="IPC real con procesos del sistema operativo (multiprocessing)",
                  font=("Segoe UI", 12, "bold"), foreground=ACENTO).pack(anchor="w")
        ttk.Label(f, style="Tenue.TLabel", wraplength=900, justify="left", text=(
            "Esta pestaña SÍ crea procesos reales y mide tiempos reales en este equipo (varían entre "
            "ejecuciones). Compara Queue, Pipe y memoria compartida con semáforos, y demuestra dos "
            "fallos reales: lector de tubería que muere (BrokenPipeError) y receptor de cola que muere "
            "(sólo se detecta por timeout).")).pack(anchor="w", pady=(2, 8))
        fila = ttk.Frame(f, style="Panel.TFrame")
        fila.pack(anchor="w")
        self.r_n = Campo(fila, 0, "Mensajes a enviar", 100, 1000000, 20000)
        self.btn_real = ttk.Button(fila, text="▶ Ejecutar IPC real", style="Acento.TButton",
                                   command=self.correr_real)
        self.btn_real.grid(row=0, column=2, padx=10)
        self.txt_real = tk.Text(f, font=("Consolas", 10), bg="#0f172a", fg="#e2e8f0",
                                relief="flat", height=20)
        self.txt_real.pack(fill="both", expand=True, pady=8)
        self.cola_real: queue.Queue = queue.Queue()

    def correr_real(self):
        try:
            n = self.r_n.valor()
        except ValueError as e:
            messagebox.showerror("Dato inválido", str(e))
            return
        self.btn_real.configure(state="disabled")
        self.txt_real.delete("1.0", "end")

        def trabajo():
            from ipc_sim import ipc_real
            try:
                ipc_real.ejecutar_todo(n, reportar=self.cola_real.put)
            except Exception as e:  # noqa: BLE001 — se informa en pantalla
                self.cola_real.put(f"ERROR: {type(e).__name__}: {e}")
            self.cola_real.put(None)

        threading.Thread(target=trabajo, daemon=True).start()
        self._leer_real()

    def _leer_real(self):
        try:
            while True:
                linea = self.cola_real.get_nowait()
                if linea is None:
                    self.btn_real.configure(state="normal")
                    return
                self.txt_real.insert("end", linea + "\n")
                self.txt_real.see("end")
        except queue.Empty:
            pass
        self.after(100, self._leer_real)

    # ===================================================== pestaña CONCEPTOS
    def _construir_conceptos(self):
        t = tk.Text(self.tab_con, wrap="word", font=("Segoe UI", 10), padx=16, pady=12,
                    relief="flat", bg=PANEL)
        t.pack(fill="both", expand=True)
        t.insert("1.0", CONCEPTOS)
        t.configure(state="disabled")


def main():
    App().mainloop()
