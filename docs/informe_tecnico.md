# Informe técnico — IPC Messenger: comunicación entre procesos

**Universidad Simón Bolívar, sede Cúcuta** · **Asignatura:** Sistemas Operativos · **Proyecto 9** · 2026-2

**Docente:** Ing. Álvaro Salamanca

**Software desarrollado por:** Jefersson Hernando Rivera Peñaranda · Victor Manuel Ortega Blanco · Cristian Miranda Zuluaga — estudiantes de 6.º semestre de Ingeniería de Sistemas.

**Implementación:** aplicación web (Flask + HTML/CSS/JS) sobre un motor de simulación de tiempo discreto en Python **+** módulo de IPC real (`multiprocessing`).

---

## 1. Problema

Los procesos tienen espacios de memoria aislados, así que necesitan mecanismos del
sistema operativo para intercambiar datos y coordinarse (IPC). Cada mecanismo ofrece
garantías distintas sobre límites de mensaje, bloqueo, sincronización y detección de
fallos. El objetivo es construir una aplicación que **modele** ese intercambio,
muestre los mensajes pendientes y el estado de los procesos, permita **inyectar fallos**
(receptores que caen o dejan de responder) y **compare** mecanismos bajo la misma carga.

## 2. Conceptos de Sistemas Operativos aplicados

| Concepto | Cómo se representa |
|---|---|
| Paso de mensajes vs. memoria compartida | Cola y tubería (el núcleo copia los datos) frente a memoria compartida (los procesos se sincronizan solos) |
| Cola de mensajes (`msgsnd`/`msgrcv`) | Mensajes discretos, FIFO o por prioridad, capacidad en mensajes, envío bloqueante o con `EAGAIN` |
| Tubería (`pipe`) | Flujo de bytes, lecturas parciales, reensamblado por `\n`, EOF (`read()=0`), `EPIPE`/`SIGPIPE` |
| Memoria compartida | Búfer circular con índices `in`/`out` y contador compartido |
| Sección crítica, condición de carrera | Escribir/leer en fases no atómicas: dos procesos leen el mismo índice y se pisan |
| Mutex y semáforos contadores | `vacíos`, `llenos` y `mutex` (solución clásica productor–consumidor) |
| Bloqueo vs. espera activa | Estado *Bloqueado* (duerme) frente a *Espera activa* (sondea consumiendo CPU) |
| Estados de proceso | Nuevo → Listo → Ejecución → Bloqueado/Espera activa → Terminado; además Caído y No responde |
| Fallos y timeouts | Crash, congelamiento, lentitud; timeout para detectar receptores que no responden |
| Interbloqueo | Grafo de espera entre procesos; detección de ciclos (espera circular) |

## 3. Diseño

**Arquitectura en capas — lógica separada de la interfaz:**

```
 Navegador: web/templates + static (HTML, CSS, JS — diagrama SVG, validación)
      │  fetch JSON
      ▼
 web/servidor.py  (Flask: API REST, valida entradas, serializa el estado)
      │  usa
      ▼
 ipc_sim/
   simulador.py  ── motor por ticks, fallos, timeouts, estancamiento, métricas
   mecanismos.py ── ColaMensajes | Tuberia | MemoriaCompartida  (interfaz común)
   modelo.py     ── Estado, Mensaje, Accion, Proceso, Resultado
   escenarios.py ── 15 casos reproducibles     experimento.py ── comparación
   ipc_real.py   ── procesos reales del SO (multiprocessing)
```

**Decisiones técnicas principales**

0. **Aplicación web cliente–servidor sin estado.** El navegador conserva una «receta»
   (escenario + lista de acciones) y el servidor reconstruye la simulación reproduciéndola
   en cada petición (el motor es determinista); así puede desplegarse en Vercel como función
   serverless. La interfaz es bilingüe (español/inglés): los textos de la página y los
   mensajes del motor se traducen en el navegador. El servidor devuelve el estado completo en JSON
   (procesos, canales, métricas, eventos nuevos). Así la lógica se reutiliza sin cambios
   en la web, la consola y las pruebas. La interfaz sigue la paleta institucional.

1. **Interfaz común de mecanismos.** Cada mecanismo implementa `enviar()`, `recibir()`
   y `cancelar()` y responde con un `Resultado`: `OK`, `SIGUE` (avanzó una fase),
   `BLOQUEA`, `ESPERA_ACTIVA`, `ERROR` o `EOF`. El motor no conoce los detalles de cada
   mecanismo; así se pueden comparar con la misma carga.
2. **Programa por proceso.** Cada proceso ejecuta una lista de acciones (`send`,
   `receive`, `compute`). Los receptores repiten su ciclo hasta recibir EOF.
3. **Tiempo discreto.** En cada tick cada proceso vivo da a lo sumo un paso; el orden
   rota para ser justo y es determinista con la semilla (resultados reproducibles).
4. **Operaciones no atómicas en memoria compartida.** Escribir toma 2–3 ticks (tomar
   recursos → leer índice → escribir y liberar). Esto hace visible la condición de carrera.
5. **Detección de estancamiento.** Si pasan *N* ticks sin progreso, el simulador explica
   qué espera cada proceso e identifica la causa: receptor caído, mutex huérfano o
   **ciclo** en el grafo de espera (DFS).
6. **Fallos y recuperación.** `caer` (permanente), `no_responder` (reversible), `lento`
   y `recuperar`; pueden programarse por tick o inyectarse en vivo desde la interfaz.
7. **Timeout.** Si una operación espera más de *T* ticks se cancela, se liberan los
   recursos tomados a medias (`cancelar`) y el mensaje se descarta.

**Simplificaciones del modelo:** no hay planificador de CPU ni cambios de contexto; los
bloqueados reintentan cada tick; no se modelan claves IPC, permisos ni límites del
núcleo; la tubería delimita con `\n`. Los ticks **no son mediciones reales**.

## 4. Pruebas

Se definieron **34 casos automatizados**: 26 del motor (7 normales, 5 límite, 12 de error,
2 de experimentación) y 8 de la API web (página y créditos, escenarios, ciclo completo,
fallos, validación de entradas, exportación y experimento). Además se probó la interfaz
en navegador (Chromium) a 1440, 1100 y 390 px de ancho sin errores de JavaScript.
Resultado: **34/34 OK**. Detalle en `docs/matriz_pruebas.md`.

## 5. Resultados del reto de experimentación

**Carga común:** 3 emisores × 6 mensajes, 2 receptores, capacidad 4, receptor tarda 2 ticks.

| Mecanismo | Entregados | Corruptos / carrera | Lat. prom. | Ticks bloqueado | Ticks totales |
|---|---|---|---|---|---|
| Cola de mensajes | **18/18** | 0 | **5.2** | 17 | **29** |
| Tubería | 15/18 | 3 | 7.3 | 9 | 30 |
| Memoria compartida + semáforos | **18/18** | 0 | 18.1 | 204 | 86 |
| Memoria compartida sin sincronizar | 6/18 | 20 | 4.5 | 0 | 31 |

**Con fallo** (mismo caso, R1 cae en el tick 8): cola y tubería entregan 18/18 gracias a
que R2 sigue vivo; la memoria con semáforos **se estanca** porque R1 murió con el mutex
tomado. Con un solo receptor (prueba X02): la tubería avisa de inmediato (`SIGPIPE`)
mientras la cola sólo se llena y deja a los emisores bloqueados.

**IPC real (5 000 mensajes de 32 B, equipo de desarrollo):** Pipe ≈ 191 k msg/s,
Queue ≈ 90 k msg/s, memoria compartida + semáforos ≈ 64 k msg/s. El lector de una
tubería que muere produce un `BrokenPipeError` real; el receptor de una cola que muere
**no** se detecta hasta que `put()` vence por timeout.

## 6. Ventajas, límites y posibles bloqueos

| Mecanismo | Ventajas | Límites | Bloqueos posibles |
|---|---|---|---|
| Cola de mensajes | Conserva límites de mensaje, varios productores/consumidores, prioridades | Capacidad fija; no avisa si el receptor muere | Emisores bloqueados con cola llena; recepción cruzada → interbloqueo |
| Tubería | Simple, rápida, detecta lector caído (EPIPE) y fin de flujo (EOF) | Flujo de bytes: hay que delimitar; unidireccional; con varios lectores se corrompe | Escritor bloqueado si el lector es lento; recepción cruzada → interbloqueo |
| Memoria compartida | Sin copia del núcleo (la más rápida en sistemas reales con datos grandes) | Toda la sincronización corre por cuenta del programador | Sin sync: carreras y espera activa. Con sync: serialización por mutex y **mutex huérfano** si un proceso muere en la sección crítica |

## 7. Conclusiones

1. La **cola de mensajes** fue la opción más robusta para productor–consumidor múltiple:
   cero pérdidas y la menor latencia simulada, porque conserva los límites de mensaje.
2. La **tubería** es adecuada para comunicación 1 a 1; con varios lectores las lecturas
   parciales se intercalan y aparecen mensajes corruptos. Su ventaja frente a fallos es
   que el escritor detecta de inmediato la caída del lector (`EPIPE`/`SIGPIPE`).
3. La **memoria compartida sin sincronización** pierde datos por condiciones de carrera
   (6/18 entregados). Con **mutex + semáforos** se recupera la corrección (18/18) a costa
   de serializar la sección crítica (más ticks y más tiempo bloqueado).
4. Un receptor que deja de responder bloquea indefinidamente a los emisores si no hay
   **timeout**; con timeout el sistema degrada de forma controlada (descarta y continúa).
5. El interbloqueo por recepción cruzada desaparece al **romper la espera circular**
   (cambiar el orden: enviar antes de recibir).
6. Los ticks permiten razonar sobre el comportamiento, pero **no son tiempos reales**; por
   eso se incluyó el módulo de IPC real como contraste.

## 8. Posibles mejoras

- Modelar un planificador de CPU (quantum) para que la espera activa compita por CPU.
- Agregar sockets locales y señales como mecanismos adicionales.
- Recuperación automática del mutex huérfano (mutex robusto, `EOWNERDEAD`).
- Exportar las gráficas como imagen para el informe.
