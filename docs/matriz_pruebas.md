# Matriz de pruebas — IPC Messenger

Todas las pruebas son **reproducibles** (semilla fija = 42) y están automatizadas en
`tests/test_ipc.py` y `tests/test_web.py` (`python -m unittest -v` → **34/34 OK**). Los escenarios con clave
pueden verse en la interfaz (pestaña Simulador → Escenario) o en consola con
`python main.py --escenario <clave>`.

Tiempos en **ticks simulados**.

## Escenarios normales

| ID | Escenario / entrada | Resultado esperado | Resultado observado | Estado |
|---|---|---|---|---|
| N01 | `normal_cola`: cola cap. 4, 2 emisores × 5 msg, 2 receptores | 10/10 entregados, todos terminan por EOF | 10/10 entregados, 0 pérdidas, 18 ticks, todos *Terminado* | ✅ |
| N02 | Cola cap. 3, 1 emisor × 6 msg, 1 receptor | Orden de recepción FIFO | IDs recibidos en orden creciente | ✅ |
| N03 | `tuberia_normal`: tubería 64 B, 1→1, 8 msg | Mensajes reensamblados, EOF al final | 8/8 íntegros, 0 corruptos, R1 termina por EOF (27 ticks) | ✅ |
| N04 | `memoria_sync`: 4 ranuras, 2 prod × 6, 2 cons, mutex + semáforos | Cero pérdidas y cero carreras | 12/12 entregados, 0 sobrescritos, 0 lecturas inválidas (58 ticks) | ✅ |
| N05 | `sin_interbloqueo`: A envía antes de recibir | Ambos terminan | A y B *Terminado* en 5 ticks | ✅ |
| N06 | Misma config. con variación ±2 y semilla 7, dos veces | Métricas idénticas | Métricas idénticas | ✅ |
| N07 | Cola por prioridad; envíos con prioridad 0, 3, 1 | Se extrae primero la mayor prioridad | Orden en cola: 3, 1, 0 | ✅ |

## Escenarios límite

| ID | Escenario / entrada | Resultado esperado | Resultado observado | Estado |
|---|---|---|---|---|
| L01 | `cola_llena`: cap. 2, 3 emisores rápidos, receptor lento | Emisores bloqueados, ocupación ≤ capacidad, sin pérdidas | 56 ticks‑bloqueo, ocupación máx. 2/2, 12/12 entregados | ✅ |
| L02 | `cola_no_bloq`: igual que L01 con envío no bloqueante | Envíos con cola llena fallan con EAGAIN | 4 aceptados + 8 rechazados (EAGAIN) = 12 intentos | ✅ |
| L03 | `tuberia_parcial`: lecturas de 7 bytes | Varias `read()` por mensaje, mensajes íntegros | 5/5 íntegros, eventos «lectura parcial» registrados | ✅ |
| L04 | Capacidad mínima = 1, 2 emisores × 3 | Funciona sin pérdidas | 6/6 entregados | ✅ |
| L05 | `receptor_congelado`: R1 no responde ticks 5–25 | Emisores bloqueados durante el fallo; luego todo se entrega | 10/10 entregados, latencia máx. 28 ticks, sin estancamiento | ✅ |

## Escenarios de error

| ID | Escenario / entrada | Resultado esperado | Resultado observado | Estado |
|---|---|---|---|---|
| E01 | `receptor_cae`: R1 cae en tick 6, sin timeout | Cola llena, emisores bloqueados, estancamiento detectado | Estancado en tick 15; diagnóstico: «ningún receptor está atendiendo» | ✅ |
| E02 | `receptor_cae_timeout`: igual con timeout = 5 | Emisores detectan la falta de respuesta | 7 mensajes descartados por timeout; todos terminan (29 ticks) | ✅ |
| E03 | `tuberia_rota`: lector cae en tick 6 | EPIPE y el escritor termina por SIGPIPE | 1 EPIPE; E1 «terminado por SIGPIPE» en tick 6 | ✅ |
| E04 | `tuberia_multilector`: 2 lectores, `read()` de 16 B | Mensajes corruptos por lecturas intercaladas | 6 íntegros, 4 corruptos | ✅ |
| E05 | `memoria_sin_sync`: igual a N04 sin mutex ni semáforos | Condición de carrera y pérdidas | 6 sobrescritos, 12 lecturas inválidas, 6 perdidos | ✅ |
| E06 | `mutex_huerfano`: E1 cae con el mutex tomado (tick 7) | Bloqueo permanente con causa diagnosticada | Estancado; «el mutex lo retiene E1 (Caído) y nunca será liberado» | ✅ |
| E07 | `interbloqueo`: A y B reciben antes de enviar | Espera circular detectada | Estancado en tick 9; «INTERBLOQUEO (espera circular): A → B → A» | ✅ |
| E08 | Config. inválida: capacidad 0, 99 emisores, mecanismo «socket», tubería de 5 B, timeout −1 | Rechazo con mensaje claro | `ValueError` con mensaje descriptivo en cada caso | ✅ |
| E09 | Acción desconocida / acción de envío sin canal | Rechazo | `ValueError` | ✅ |
| E10 | Proceso que usa un canal inexistente | Rechazo | `ValueError` | ✅ |
| E11 | Mensaje de 40+ B en tubería de 20 B | Error, no se escribe | Error registrado («excede la capacidad»), 1 error en E | ✅ |
| E12 | Fallos no aplicables: tirar un proceso ya caído, recuperar un caído, PID inexistente | Mensaje explicativo / excepción | Mensajes «ya no está activo», «no tiene un fallo recuperable»; `KeyError` | ✅ |
| E13 | Web: campo «Capacidad» vacío y «Emisores» = 99 | Campos marcados en rojo y mensaje claro; no se envía | Aviso «debe ser un número entero» / «debe estar entre 1 y 8» | ✅ |

## Experimentación

| ID | Entrada | Esperado | Observado | Estado |
|---|---|---|---|---|
| X01 | Misma carga (3×6 msg, 2 receptores, cap. 4) en 4 mecanismos | 4 filas comparables, cola sin pérdidas | Cola 18/18 · Tubería 15/18 · Memoria+sem 18/18 · Memoria sin sync 6/18 | ✅ |
| X02 | 2 emisores, 1 receptor, R1 cae en tick 6 | Tubería: SIGPIPE; Cola: estancamiento | Tubería → SIGPIPE · Cola → Estancado | ✅ |
| R01 | IPC real, 5 000 mensajes de 32 B | Los 3 mecanismos completan; BrokenPipeError real | Queue ≈ 90 k msg/s, Pipe ≈ 191 k msg/s, Memoria+sem ≈ 64 k msg/s*; `BrokenPipeError [Errno 32]` | ✅ |

\* Medición real en el equipo de desarrollo (Linux); los valores cambian en cada equipo y ejecución.

## Aplicación web (API y navegador)

| ID | Entrada | Esperado | Observado | Estado |
|---|---|---|---|---|
| W01 | `GET /` | Página con logos (USB e Ingeniería de Sistemas), «Software desarrollado por» con los 3 integrantes, asignatura y docente | Presentes; logos e `i18n.js` servidos (200) | ✅ |
| W02 | `GET /api/escenarios` | 15 escenarios con su configuración | 15 escenarios | ✅ |
| W03 | Receta `normal_cola`: sin ops, `["p",3]`, `["p",3],["e"]` | Tick 0, tick 3; final con 10/10 entregados | Tick 0 → 3 → finalizado, 10 entregados | ✅ |
| W04 | Misma receta dos veces; 12 × `["p",1]` vs `["p",12]` | Resultados idénticos (determinismo, servidor sin estado) | Métricas y nº de eventos idénticos | ✅ |
| W05 | Tirar R1 y R2 y ejecutar; tirar R1 dos veces; PID inexistente | Estancamiento; mensaje «ya no está activo»; 400 | Correcto en los tres casos | ✅ |
| W06 | Config. inválida (5 casos), ops inválidas (6 casos, incl. > 25 000 ticks), escenario inexistente | 400 con lista de errores | 400 en todos los casos | ✅ |
| W07 | Exportar CSV y JSON de una receta | Archivo con cabecera y métricas con autores | CSV `tick;origen;nivel;evento`; JSON con `elaborado_por` | ✅ |
| W08 | Experimento con R1 caído en tick 6 | 4 filas; tubería termina por SIGPIPE | 4 filas; «SIGPIPE» | ✅ |
| W09 | Navegador a 1440 / 1100 / 390 px con el servidor en **3 procesos independientes** (gunicorn, como en Vercel) | Sin errores JS; simulación coherente entre peticiones | 0 errores; ancho de página = 390 px | ✅ |
| W10 | Cambiar a **EN** y recorrer 12 escenarios, fallos, experimento (con y sin fallo), IPC real y conceptos; buscar textos en español | Ningún texto en español (salvo nombres propios) | 0 textos sin traducir; 0 errores JS | ✅ |
| W11 | Volver a **ES** y recargar | El idioma elegido se conserva | `localStorage` = `es`; página en español | ✅ |
