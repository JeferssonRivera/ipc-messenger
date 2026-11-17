/* =========================================================================
   IPC Messenger · Internacionalización (español / inglés)

   - El español es el idioma fuente: el HTML y el motor (Python) están en español.
   - Elementos con data-i18n="clave": su HTML en inglés está en I18N_HTML.
   - Textos del JavaScript: t("texto en español", {variables}) busca en I18N_FRASES.
   - Textos generados por el motor (eventos, diagnósticos, conclusiones):
     tr(texto) aplica la tabla de patrones I18N_PATRONES.
   ========================================================================= */
"use strict";

const IDIOMAS = ["es", "en"];
let idioma = "es";
try {
  const guardado = localStorage.getItem("ipc-idioma");
  if (IDIOMAS.includes(guardado)) idioma = guardado;   // por defecto: español
} catch (e) { /* almacenamiento no disponible: español */ }

// ------------------------------------------------------------------ HTML
const I18N_HTML = {
  "franja.programa": "School of Engineering · Systems Engineering Program",
  "nav.inicio": "Home", "nav.simulador": "Simulator", "nav.experimento": "Experiment",
  "nav.real": "Real IPC", "nav.conceptos": "Concepts",
  "app.sub": "Inter-process communication",

  "heroe.etiqueta": "Academic software · Operating Systems",
  "heroe.programa": "Systems Engineering",
  "heroe.lema": "Visualize how processes exchange messages through <b>queues</b>, <b>pipes</b> and <b>shared memory</b>; trigger failures, detect deadlocks and compare mechanisms under the same workload.",
  "heroe.btnSim": "Open the simulator →",
  "heroe.btnExp": "See the experiment",
  "heroe.aviso": "Simulator times are <b>logical ticks</b>, not real measurements. The «Real IPC» section does use operating-system processes.",

  "inicio.titulo": "What can you do?",
  "card.cola.t": "Message queue",
  "card.cola.p": "Discrete messages in FIFO or priority order. Watch senders block when the queue is full, or get <code>EAGAIN</code> in non-blocking mode.",
  "card.tub.t": "Pipe",
  "card.tub.p": "Byte stream with partial reads, end of stream (<code>EOF</code>) and broken pipe (<code>EPIPE</code> / <code>SIGPIPE</code>) when the reader disappears.",
  "card.mem.t": "Shared memory",
  "card.mem.p": "Producer–consumer circular buffer with and without <b>mutex + semaphores</b>: race conditions, busy waiting and orphaned mutex.",
  "card.fallos.t": "Failures and deadlocks",
  "card.fallos.p": "Crash, freeze or slow down processes; use <i>timeouts</i> and let the system diagnose stalls and deadlocks.",
  "dato.mecanismos": "IPC mechanisms", "dato.escenarios": "reproducible scenarios",
  "dato.estados": "process states", "dato.pruebas": "automated tests",

  "creditos.etiqueta": "Software developed by",
  "creditos.titulo": "Development team",
  "creditos.sub": "6th-semester Systems Engineering students · Universidad Simón Bolívar, Cúcuta campus",
  "integrante.rol": "Systems Engineering · 6th semester",
  "curso.asignatura": "Course", "curso.docente": "Professor", "curso.periodo": "Academic term",
  "curso.materia": "Operating Systems", "curso.titulo": "Eng.",
  "curso.proyecto": "Project 9 · IPC Messenger", "curso.proyectoLbl": "Project",

  "sim.aviso": "⚠ <b>Discrete-time simulation:</b> times are measured in <b>logical ticks</b>; they are not real operating-system measurements.",
  "sim.escenario": "Scenario", "sim.config": "Configuration",
  "f.mecanismo": "IPC mechanism",
  "opt.cola": "Message queue", "opt.tuberia": "Pipe", "opt.memoria": "Shared memory",
  "f.capacidad": "Capacity", "f.emisores": "Senders", "f.receptores": "Receivers",
  "f.mensajes": "Messages / sender", "f.intervalo": "Ticks between sends", "f.trec": "Receiver ticks",
  "f.timeout": "Timeout", "f.lectura": "Bytes per read()", "f.variacion": "Variation ±ticks", "f.semilla": "Seed",
  "f.bloqueante": "Blocking operations", "f.sync": "Memory: mutex + semaphores", "f.prio": "Queue: random priority",
  "f.aplicar": "⟲ Apply and restart",
  "b.ejecutar": "▶ Run", "b.paso": "⏭ Step", "b.final": "⏩ To the end",
  "b.velocidad": "Speed", "b.tick": "Tick",
  "b.falloEn": "Inject failure into",
  "b.caer": "💥 Crash", "b.congelar": "🧊 Freeze", "b.lento": "🐢 Slow", "b.recuperar": "✅ Recover",
  "sim.grafica": "Channel occupancy per tick",
  "sim.metricas": "Metrics", "sim.registro": "Event log", "sim.soloAlertas": "alerts only",

  "exp.etiqueta": "Experimentation challenge",
  "exp.titulo": "Same workload, four mechanisms",
  "exp.desc": "The <b>same</b> configuration of senders and receivers is run on a message queue, a pipe and shared memory (with and without synchronization). Results are in simulated ticks.",
  "exp.carga": "Common workload",
  "e.capacidad": "Capacity (msg)", "e.fallo": "Tick when R1 crashes", "e.falloSub": "(0 = no failure)",
  "exp.ejecutar": "▶ Run comparison", "exp.csv": "⬇ Export table as CSV",
  "exp.vacio": "Set up the workload and press <b>Run comparison</b>.",
  "exp.g1": "Delivered vs. lost", "exp.g2": "Average latency and total ticks",
  "exp.conclusiones": "Automatic conclusions",

  "real.etiqueta": "Real operating-system processes",
  "real.titulo": "Real IPC with <code>multiprocessing</code>",
  "real.desc": "Unlike the simulator, here the server <b>creates real processes</b> and measures real times on the machine where it runs (they change on every run). Two real failures are also shown: a pipe reader that dies (<code>BrokenPipeError</code>) and a queue receiver that dies (only detected by <i>timeout</i>).",
  "real.n": "Messages to send (32 B each)", "real.ejecutar": "▶ Run real IPC",
  "real.rend": "Measured performance", "real.salida": "Parent process output",

  "con.etiqueta": "Fundamentals",
  "con.titulo": "Operating-system concepts represented",
  "con.desc": "Inter-process communication (IPC) groups the mechanisms through which processes with isolated memory exchange data and coordinate. There are two families: <b>message passing</b> (the kernel copies the data) and <b>shared memory</b> (processes access the same region and must synchronize).",
  "con.cola.t": "📨 Message queue",
  "con.cola.li": "<li>Keeps each message's boundaries and FIFO order (optionally by priority).</li><li>Limited capacity: when the queue is full the sender <b>blocks</b> or gets <code>EAGAIN</code>.</li><li>Supports several senders and receivers without corrupting messages.</li><li>If the receiver dies, the queue does not warn: it just fills up.</li>",
  "con.tub.t": "🔗 Pipe",
  "con.tub.sub": "<code>pipe()</code> · one-way byte stream",
  "con.tub.li": "<li>There are no «messages»: the reader must delimit them (here with <code>\\n</code>).</li><li><code>read()</code> may return fewer bytes than requested.</li><li>Writing with no readers → <code>EPIPE</code> + <code>SIGPIPE</code>. Reading with no writers → <code>EOF</code>.</li><li>With several readers, partial reads interleave.</li>",
  "con.mem.t": "🧠 Shared memory",
  "con.mem.sub": "<code>shmget</code> / <code>mmap</code> + synchronization",
  "con.mem.li": "<li>No kernel copy, but <b>no built-in synchronization</b>.</li><li>Writing is not atomic: read index → write slot → update counter.</li><li><code>empty</code>/<code>full</code> semaphores + a <code>mutex</code> solve producer–consumer.</li><li>If a process dies holding the mutex, nobody else can enter.</li>",
  "con.est.t": "🔄 Process states",
  "con.est.li": "<li><b>Blocked</b>: sleeps waiting for a resource (does not use CPU).</li><li><b>Busy waiting</b>: polls the resource, consuming CPU.</li><li><b>Not responding</b> (recoverable) and <b>Crashed</b> (permanent) are injected failures.</li>",
  "con.fal.t": "⛔ Failures, timeouts and deadlock",
  "con.fal.li": "<li>A receiver that does not respond leaves the senders blocked indefinitely.</li><li>A <b>timeout</b> lets the sender detect the lack of response and drop the message.</li><li>Deadlock: A waits to receive from B and B from A (circular wait). A wait-for graph is built and searched for a cycle.</li>",
  "con.simp.t": "📐 Model simplifications",
  "con.simp.li": "<li>Discrete-time simulation: times are <b>ticks</b>, not real measurements.</li><li>Each live process takes at most one step per tick; there is no CPU scheduler.</li><li>Service order rotates every tick and is deterministic for the same seed.</li><li>Blocked processes retry every tick.</li><li>IPC keys, permissions and kernel limits are not modeled.</li>",

  "pie.etiqueta": "Software developed by:",
  "pie.estudiantes": "6th-semester Systems Engineering students · Universidad Simón Bolívar, Cúcuta campus",
  "pie.proyecto": "Project 9 · Operating Systems",
  "pie.periodo": "Academic term 2026-2",
};

const I18N_ATRIBUTOS = {
  "t.capacidad": "Queue: number of messages · Pipe: bytes · Memory: slots",
  "t.intervalo": "Computation ticks between two sends",
  "t.trec": "Ticks the receiver takes to process each message",
  "t.timeout": "0 = wait indefinitely",
  "t.lectura": "Pipe only",
  "t.variacion": "Reproducible random variation in computation steps",
  "t.proceso": "You can also click on a process in the diagram",
  "t.csv": "Export the event log (evidence)",
  "t.json": "Export metrics and configuration",
  "t.ecap": "Converted to bytes for the pipe (≈18 B per message)",
  "t.menu": "Open menu",
  "t.idioma": "Cambiar idioma / Change language",
};

// ---------------------------------------------------------- frases del JS
const I18N_FRASES = {
  // estados
  "Nuevo": "New", "Listo": "Ready", "Ejecución": "Running", "Bloqueado": "Blocked",
  "Espera activa": "Busy waiting", "No responde": "Not responding", "Caído": "Crashed", "Terminado": "Terminated",
  // roles y fallos
  "emisor": "sender", "receptor": "receiver", "envía / recibe": "sends / receives",
  "Caída": "Crash", "Congelado": "Freeze", "Lento": "Slowdown", "Recuperación": "Recovery",
  "{f} de {pid} en el tick {t}": "{f} of {pid} at tick {t}",
  // tipos de escenario
  "normal": "normal", "límite": "edge case", "error": "error",
  "Personalizado": "Custom", "— Personalizado —": "— Custom —",
  "Configuración libre. Ajusta los parámetros y pulsa <b>Aplicar y reiniciar</b>.":
    "Free configuration. Adjust the parameters and press <b>Apply and restart</b>.",
  "Esperado:": "Expected:", "Fallos programados:": "Scheduled failures:",
  "<b>✎ Cambios sin aplicar.</b> Pulsa «Aplicar y reiniciar».": "<b>✎ Unapplied changes.</b> Press «Apply and restart».",
  // validación
  "«{e}» debe ser un número entero.": "«{e}» must be an integer.",
  "«{e}» debe estar entre {min} y {max}.": "«{e}» must be between {min} and {max}.",
  "Revisa la configuración": "Check the configuration",
  "Revisa la carga de trabajo": "Check the workload",
  "Configuración inválida": "Invalid configuration",
  // avisos
  "No hay conexión con el servidor. ¿Sigue en ejecución «python main.py»?":
    "No connection to the server. Is «python main.py» still running?",
  "No se pudieron cargar los escenarios": "Scenarios could not be loaded",
  "⛔ Estancamiento detectado": "⛔ Stall detected",
  "⛔ Estancamiento detectado:": "⛔ Stall detected:",
  "La simulación terminó en el tick {t}.": "The simulation finished at tick {t}.",
  "■ Finalizada": "■ Finished",
  "La simulación está estancada. Recupera un proceso o reinicia.": "The simulation is stalled. Recover a process or restart.",
  "La simulación ya terminó. Pulsa «Aplicar y reiniciar».": "The simulation has already finished. Press «Apply and restart».",
  "No hay más pasos que ejecutar.": "There are no more steps to run.",
  "No se pudo exportar": "Export failed", "Exportar": "Export",
  "Fallo no aplicable": "Failure not applicable",
  "{f} aplicada a {pid}.": "{f} applied to {pid}.",
  // insignia
  "⛔ Estancado": "⛔ Stalled", "■ Finalizado": "■ Finished", "● En ejecución": "● Running",
  "Listo para iniciar": "Ready to start", "En pausa": "Paused",
  // canal
  "Cola de mensajes": "Message queue", "Tubería (pipe)": "Pipe", "Memoria compartida": "Shared memory",
  "msg": "msg", "bytes": "bytes", "ranuras": "slots",
  "ocupación {o}/{c} {u}": "occupancy {o}/{c} {u}",
  " · ordenada por prioridad": " · ordered by priority", " · FIFO": " · FIFO",
  " · read() de {n} B": " · read() of {n} B",
  "con mutex + semáforos": "with mutex + semaphores", "⚠ SIN sincronización": "⚠ NO synchronization",
  "(vacía)": "(empty)", "vacía": "empty", "#{id} {texto} (de {o})": "#{id} {texto} (from {o})",
  "escritura → flujo de bytes → lectura · ": "write → byte stream → read · ",
  "mensajes en tránsito: {n}": "messages in transit: {n}",
  "+{n} ranuras no mostradas": "+{n} slots not shown",
  "◀ frente (se recibe)": "◀ front (received here)", "final (se envía) ◀": "back (sent here) ◀",
  "mutex: libre": "mutex: free", "libre": "free",
  "vacíos = {n}": "empty = {n}", "llenos = {n}": "full = {n}", "contador = {n}": "counter = {n}",
  "contador compartido = {n} (sin protección: sujeto a carreras)": "shared counter = {n} (unprotected: subject to races)",
  "contador = {n} (sin protección)": "counter = {n} (unprotected)",
  "env {e} · rec {r} · err {x}": "sent {e} · recv {r} · err {x}",
  "{e} env · {r} rec": "{e} sent · {r} recv",
  "mensaje en tránsito": "message in transit",
  "Ejecuta la simulación para ver la evolución del canal": "Run the simulation to see how the channel evolves",
  // métricas
  "Enviados": "Sent", "Entregados": "Delivered", "Pendientes en el canal": "Pending in channel", "Perdidos": "Lost",
  "Rechazados (EAGAIN)": "Rejected (EAGAIN)", "Descartados por timeout": "Dropped by timeout", "EPIPE": "EPIPE",
  "Corruptos": "Corrupted", "Sobrescritos (carrera)": "Overwritten (race)", "Lecturas inválidas": "Invalid reads",
  "Duplicados": "Duplicates", "Ocupación máxima": "Max occupancy", "Latencia promedio (ticks)": "Average latency (ticks)",
  "Latencia máxima (ticks)": "Max latency (ticks)",
  "ticks": "ticks", "entregados": "delivered", "perdidos": "lost", "ticks bloqueado (Σ)": "blocked ticks (Σ)",
  "ticks espera activa": "busy-wait ticks", "procesos activos": "active processes",
  "Canal {n} · {t}": "Channel {n} · {t}", "Ocupación {o}/{c}": "Occupancy {o}/{c}",
  "Procesos": "Processes", "Estado": "State", "Env": "Sent", "Rec": "Recv", "Err": "Err",
  // experimento
  "Mecanismo": "Mechanism", "Corruptos/carrera": "Corrupted/race", "EAGAIN/timeout": "EAGAIN/timeout",
  "Lat. prom": "Avg lat.", "Lat. máx": "Max lat.", "Ticks bloqueado": "Blocked ticks",
  "Ticks totales": "Total ticks", "Final": "Outcome",
  "Completado": "Completed", "Estancado": "Stalled", "SIGPIPE": "SIGPIPE",
  "Tubería": "Pipe", "Memoria compartida + semáforos": "Shared memory + semaphores",
  "Memoria compartida sin sincronizar": "Unsynchronized shared memory",
  "entregados · {f}": "delivered · {f}",
  "Ticks hasta terminar": "Ticks to finish",
  // IPC real
  "⏳ Creando procesos reales y midiendo… (puede tardar unos segundos)": "⏳ Creating real processes and measuring… (may take a few seconds)",
  "No disponible en este servidor": "Not available on this server",
  "{n} mensajes de {b} B · medición real del servidor; varía entre ejecuciones.":
    "{n} messages of {b} B · real server measurement; varies between runs.",
  "ℹ Algunos mecanismos necesitan semáforos POSIX (<code>/dev/shm</code>), que las plataformas <i>serverless</i> como Vercel no ofrecen. Ejecuta la aplicación en local (<code>python main.py</code>) para medirlos.":
    "ℹ Some mechanisms need POSIX semaphores (<code>/dev/shm</code>), which <i>serverless</i> platforms such as Vercel do not provide. Run the app locally (<code>python main.py</code>) to measure them.",
  "✔ Completado en {s} s": "✔ Completed in {s} s",
  "IPC real": "Real IPC",
  "▶ Ejecutar": "▶ Run", "⏸ Pausa": "⏸ Pause",
};

// ---------------------------------------------------- escenarios (por clave)
const I18N_ESCENARIOS = {
  normal_cola: ["1. Message queue – normal flow", "2 senders and 2 receivers share a 4-message queue.",
    "All 10 messages are delivered without losses and everyone ends with EOF."],
  cola_llena: ["2. Full queue (blocking)", "3 fast senders, 1 slow receiver, queue of capacity 2.",
    "Senders become Blocked when the queue is full; nothing is lost."],
  cola_no_bloq: ["3. Full queue (non-blocking, EAGAIN)", "Same as above but msgsnd with IPC_NOWAIT.",
    "Sends to a full queue fail with EAGAIN and those messages are dropped."],
  receptor_cae: ["4. Receiver crashes (no timeout)", "The only receiver crashes at tick 6.",
    "The queue fills up, senders stay blocked forever and a stall is detected."],
  receptor_cae_timeout: ["5. Receiver crashes (with timeout)", "Same as above but sends have a 5-tick timeout.",
    "Senders detect the lack of response, drop messages and finish."],
  receptor_congelado: ["6. Receiver stops responding and recovers", "R1 freezes at tick 5 and comes back at tick 25.",
    "Senders block while the failure lasts and then everything is delivered."],
  tuberia_normal: ["7. Pipe – normal flow", "1 writer and 1 reader; 64-byte pipe, 64-byte reads.",
    "All messages are reassembled correctly; the reader ends with EOF."],
  tuberia_parcial: ["8. Pipe – partial reads", "Reads of only 7 bytes: each message needs several read() calls.",
    "Messages arrive intact but with higher latency (byte stream)."],
  tuberia_rota: ["9. Broken pipe (reader crashes → SIGPIPE)", "The reader crashes at tick 6.",
    "The next write fails with EPIPE and the writer ends by SIGPIPE."],
  tuberia_multilector: ["10. Pipe with 2 readers", "Two readers share the same pipe and read 16 bytes at a time.",
    "Partial reads interleave and corrupted messages appear."],
  memoria_sin_sync: ["11. Shared memory WITHOUT synchronization", "2 producers and 2 consumers write/read the buffer without mutex or semaphores.",
    "Race condition: overwrites, invalid reads and lost messages."],
  memoria_sync: ["12. Shared memory WITH mutex + semaphores", "Same workload as scenario 11, protected with semaphores.",
    "Zero losses: the critical section is exclusive and processes block on full/empty buffer."],
  mutex_huerfano: ["13. Process crashes inside the critical section", "E1 crashes at tick 7, right when it holds the mutex.",
    "The mutex is never released: the rest block and the cause is diagnosed."],
  interbloqueo: ["14. Deadlock by crossed receives", "A waits for a message from B before replying and B waits for one from A.",
    "Both stay blocked; circular wait A → B → A is detected."],
  sin_interbloqueo: ["15. No deadlock (A sends first)", "A's order is changed: it sends first and then receives.",
    "The circular wait is broken and both finish."],
};

// ------------------------------------------- patrones de textos del motor
const _P = (re, en) => [re, en];
const I18N_PATRONES = [
  // simulador
  _P(/Simulación creada: (\d+) procesos, canales: /g, "Simulation created: $1 processes, channels: "),
  _P(/ no puede pasar a 'No responde' desde /g, " cannot switch to 'Not responding' from "),
  _P(/ se cae \(crash\)\./g, " crashes."),
  _P(/ ¡Murió con el mutex tomado!/g, " It died holding the mutex!"),
  _P(/ deja de responder\./g, " stops responding."),
  _P(/ vuelve a responder\./g, " responds again."),
  _P(/ recupera su velocidad normal\./g, " recovers its normal speed."),
  _P(/ no tiene un fallo recuperable \(un proceso caído no se recupera\)\./g, " has no recoverable failure (a crashed process cannot recover)."),
  _P(/ ya no está activo /g, " is no longer active "),
  _P(/ no está activo\./g, " is not active."),
  _P(/ se vuelve lento \(1 paso cada (\d+) ticks\)\./g, " becomes slow (1 step every $1 ticks)."),
  _P(/Tipo de fallo desconocido: /g, "Unknown failure type: "),
  _P(/ terminó su programa\./g, " finished its program."),
  _P(/ admitido \(/g, " admitted ("),
  _P(/Todos los procesos finalizaron\./g, "All processes finished."),
  _P(/ESTANCAMIENTO: /g, "STALL: "),
  _P(/Se alcanzó el límite de (\d+) ticks\./g, "The limit of $1 ticks was reached."),
  _P(/📥 recibe (.+?) \(latencia (\d+) ticks\)/g, "📥 receives $1 (latency $2 ticks)"),
  _P(/ termina: /g, " terminates: "),
  _P(/; mensaje (.+?) descartado/g, "; message $1 dropped"),
  _P(/sondeo \(EAGAIN\): /g, "polling (EAGAIN): "),
  _P(/ espera: /g, " waits: "),
  _P(/TIMEOUT tras (\d+) ticks: (.+?) descartado \(¿receptor no responde\?\)/g, "TIMEOUT after $1 ticks: $2 dropped (receiver not responding?)"),
  _P(/TIMEOUT tras (\d+) ticks esperando mensaje/g, "TIMEOUT after $1 ticks waiting for a message"),
  _P(/en (\S+) los emisores esperan espacio pero ningún receptor está atendiendo \(caído o sin responder\)/g,
     "in $1 the senders are waiting for space but no receiver is serving (crashed or not responding)"),
  _P(/el mutex de (\S+) lo retiene (\S+) \((.+?)\) y nunca será liberado/g, "the mutex of $1 is held by $2 ($3) and will never be released"),
  _P(/INTERBLOQUEO \(espera circular\): /g, "DEADLOCK (circular wait): "),
  _P(/sin procesos activos que avancen/g, "no active processes making progress"),
  _P(/\. Causa: /g, ". Cause: "),
  _P(/congelado \(no responde\)/g, "frozen (not responding)"),
  _P(/fallo inyectado \(crash\)/g, "injected failure (crash)"),
  _P(/programa completado/g, "program completed"),
  _P(/terminado por SIGPIPE/g, "terminated by SIGPIPE"),
  _P(/(\S+) no responde(?=;|\.|$)/g, "$1 is not responding"),
  // mecanismos
  _P(/cola '([^']+)' llena \((\d+)\/(\d+)\)/g, "queue '$1' full ($2/$3)"),
  _P(/msgsnd -> (.+?) en '([^']+)'/g, "msgsnd -> $1 into '$2'"),
  _P(/cola '([^']+)' vacía y sin emisores activos/g, "queue '$1' empty and no active senders"),
  _P(/cola '([^']+)' vacía/g, "queue '$1' empty"),
  _P(/EPIPE: tubería rota \(no hay lectores\)/g, "EPIPE: broken pipe (no readers)"),
  _P(/mensaje de (\d+) B excede la capacidad de la tubería \((\d+) B\)/g, "message of $1 B exceeds the pipe capacity ($2 B)"),
  _P(/tubería '([^']+)' sin espacio \((\d+) B libres\)/g, "pipe '$1' has no space ($2 B free)"),
  _P(/línea corrupta recibida: /g, "corrupted line received: "),
  _P(/lectura parcial, mensaje incompleto/g, "partial read, incomplete message"),
  _P(/\(todos los escritores cerraron\)/g, "(all writers closed)"),
  _P(/tubería '([^']+)' vacía/g, "pipe '$1' empty"),
  _P(/mutex ocupado por /g, "mutex held by "),
  _P(/entra a la sección crítica \(mutex tomado\)/g, "enters the critical section (mutex acquired)"),
  _P(/\blee idx_/g, "reads idx_"),
  _P(/, contador = /g, ", counter = "),
  _P(/CARRERA: (\S+) sobrescribe (.+?) en ranura (\d+)/g, "RACE: $1 overwrites $2 in slot $3"),
  _P(/CARRERA: lee ranura (\d+) vacía \(otro consumidor ya la tomó\)/g, "RACE: reads empty slot $1 (another consumer already took it)"),
  _P(/escribe (.+?) en ranura (\d+)/g, "writes $1 into slot $2"),
  _P(/búfer lleno: while\(contador == N\) \{\} \(sondeo\)/g, "buffer full: while(count == N) {} (polling)"),
  _P(/búfer vacío: while\(contador == 0\) \{\} \(sondeo\)/g, "buffer empty: while(count == 0) {} (polling)"),
  _P(/búfer vacío y sin productores activos/g, "buffer empty and no active producers"),
  _P(/contador inconsistente detectado y corregido al final/g, "inconsistent counter detected and corrected at the end"),
  _P(/búfer vacío/g, "buffer empty"),
  _P(/compute \((\d+) rest\.\)/g, "compute ($1 left)"),
  // contenidos de mensajes del escenario de interbloqueo
  _P(/respuesta de (\w+)/g, "reply from $1"),
  _P(/petición de (\w+)/g, "request from $1"),
  // conclusiones del experimento
  _P(/Entregaron todo sin errores: (.+?)\. El que terminó en menos ticks fue «(.+?)» \((\d+) ticks\)\./g,
     "Delivered everything without errors: $1. The fastest to finish was «$2» ($3 ticks)."),
  _P(/Tubería: (\d+) mensajes corruptos\. Una tubería es un flujo de bytes sin límites de mensaje; con varios lectores las lecturas parciales se intercalan\./g,
     "Pipe: $1 corrupted messages. A pipe is a byte stream without message boundaries; with several readers, partial reads interleave."),
  _P(/: (\d+) eventos de carrera \(sobrescrituras\/lecturas inválidas\) y (\d+) mensajes perdidos\. La sección crítica no es atómica sin mutex\./g,
     ": $1 race events (overwrites/invalid reads) and $2 lost messages. The critical section is not atomic without a mutex."),
  _P(/Sin semáforos los procesos sondean el búfer \(espera activa: (\d+) ticks de CPU desperdiciados\) en lugar de dormir \(bloqueados: (\d+) ticks con semáforos\)\./g,
     "Without semaphores, processes poll the buffer (busy waiting: $1 wasted CPU ticks) instead of sleeping (blocked: $2 ticks with semaphores)."),
  _P(/: quedó estancado porque un proceso murió dentro de la sección crítica y el mutex nunca se liberó \(mutex huérfano\)\./g,
     ": got stuck because a process died inside the critical section and the mutex was never released (orphaned mutex)."),
  _P(/: quedó estancado \(receptor caído y emisores bloqueados sin timeout\)\. Se recomienda timeout o detección de fallos\./g,
     ": got stuck (receiver crashed and senders blocked without timeout). A timeout or failure detection is recommended."),
  _P(/: el emisor detectó de inmediato la caída del lector \(EPIPE\/SIGPIPE\), a diferencia de la cola, que sólo se llena\./g,
     ": the sender immediately detected the reader's crash (EPIPE/SIGPIPE), unlike the queue, which just fills up."),
  _P(/Con varios receptores la cola de mensajes conserva los límites de cada mensaje, por eso es la opción natural para productor–consumidor múltiple\./g,
     "With several receivers the message queue keeps each message's boundaries, which makes it the natural choice for multiple producer–consumer."),
  _P(/Recordatorio: son ticks de una SIMULACIÓN, no tiempos reales del sistema operativo\./g,
     "Reminder: these are SIMULATION ticks, not real operating-system times."),
  // IPC real
  _P(/=== IPC REAL \(procesos del SO, PID padre (\d+)\) — (\d+) mensajes de (\d+) B ===/g,
     "=== REAL IPC (OS processes, parent PID $1) — $2 messages of $3 B ==="),
  _P(/Mediciones reales de ESTE equipo: varían según hardware y carga\./g, "Real measurements on THIS machine: they vary with hardware and load."),
  _P(/NO DISPONIBLE en este servidor/g, "NOT AVAILABLE on this server"),
  _P(/No disponible en este servidor/g, "Not available on this server"),
  _P(/--- Fallos reales ---/g, "--- Real failures ---"),
  _P(/Escritor detectó la caída del lector: /g, "Writer detected the reader's crash: "),
  _P(/No se detectó error \(el SO aún tenía búfer disponible\)\./g, "No error detected (the OS still had buffer space)."),
  _P(/La cola no avisa la caída del receptor: se aceptaron (\d+) mensajes y luego put\(\) expiró tras ([\d.]+)s \(cola llena\)\./g,
     "The queue does not report the receiver's crash: $1 messages were accepted and then put() timed out after $2s (queue full)."),
  _P(/(^|\s)Cola:/g, "$1Queue:"),
  // nombres de mecanismos (los más largos primero)
  _P(/Memoria compartida sin sincronizar/g, "Unsynchronized shared memory"),
  _P(/Memoria compartida \+ semáforos/g, "Shared memory + semaphores"),
  _P(/Cola de mensajes/g, "Message queue"),
  _P(/(^|[\s«(])Tubería/g, "$1Pipe"),
];
// nombres de estado como palabras completas (al final)
[["Espera activa", "Busy waiting"], ["No responde", "Not responding"], ["Ejecución", "Running"],
 ["Bloqueado", "Blocked"], ["Terminado", "Terminated"], ["Caído", "Crashed"], ["Listo", "Ready"], ["Nuevo", "New"]]
  .forEach(([es, en]) => I18N_PATRONES.push([new RegExp(`(^|[^\\wÀ-ÿ])${es}(?![\\wÀ-ÿ])`, "g"), `$1${en}`]));

// ------------------------------------------------------------------- API
function t(texto, vars) {
  let r = idioma === "en" && Object.prototype.hasOwnProperty.call(I18N_FRASES, texto) ? I18N_FRASES[texto] : texto;
  if (vars) r = r.replace(/\{(\w+)\}/g, (m, k) => (k in vars ? vars[k] : m));
  return r;
}

function tr(texto) {
  if (idioma !== "en" || !texto) return texto;
  let r = String(texto);
  for (const [re, en] of I18N_PATRONES) { re.lastIndex = 0; r = r.replace(re, en); }
  return r;
}

function escTexto(e) {
  if (idioma === "en" && I18N_ESCENARIOS[e.clave]) {
    const [titulo, descripcion, esperado] = I18N_ESCENARIOS[e.clave];
    return { titulo, descripcion, esperado };
  }
  return { titulo: e.titulo, descripcion: e.descripcion, esperado: e.esperado };
}

const formatoNumero = (n) => Number(n).toLocaleString(idioma === "en" ? "en-US" : "es-CO");

function aplicarIdiomaEstatico() {
  document.documentElement.lang = idioma;
  document.querySelectorAll("[data-i18n]").forEach((el) => {
    if (el.dataset.i18nEs === undefined) el.dataset.i18nEs = el.innerHTML;
    const en = I18N_HTML[el.dataset.i18n];
    el.innerHTML = idioma === "en" && en !== undefined ? en : el.dataset.i18nEs;
  });
  document.querySelectorAll("[data-i18n-title]").forEach((el) => {
    if (el.dataset.i18nTitleEs === undefined) el.dataset.i18nTitleEs = el.getAttribute("title") || "";
    const en = I18N_ATRIBUTOS[el.dataset.i18nTitle];
    const valor = idioma === "en" && en !== undefined ? en : el.dataset.i18nTitleEs;
    el.setAttribute("title", valor);
    if (el.hasAttribute("aria-label")) el.setAttribute("aria-label", valor);
  });
  document.querySelectorAll("[data-idioma]").forEach((b) => {
    b.classList.toggle("activo", b.dataset.idioma === idioma);
    b.setAttribute("aria-pressed", String(b.dataset.idioma === idioma));
  });
  document.title = idioma === "en"
    ? "IPC Messenger · Universidad Simón Bolívar"
    : "IPC Messenger · Universidad Simón Bolívar";
}

function fijarIdioma(nuevo) {
  if (!IDIOMAS.includes(nuevo)) return;
  idioma = nuevo;
  try { localStorage.setItem("ipc-idioma", nuevo); } catch (e) { /* sin almacenamiento */ }
  aplicarIdiomaEstatico();
}
