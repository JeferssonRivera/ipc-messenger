# IPC Messenger — Comunicación entre procesos

**Universidad Simón Bolívar · sede Cúcuta**
**Sistemas Operativos · Proyecto 9 · Programa de Ingeniería de Sistemas · 2026-2**

**Asignatura:** Sistemas Operativos · **Docente:** Ing. Álvaro Salamanca

**Software desarrollado por:**
- Jefersson Hernando Rivera Peñaranda
- Victor Manuel Ortega Blanco
- Cristian Miranda Zuluaga

*Estudiantes de 6.º semestre de Ingeniería de Sistemas.*

---

Aplicación **web** (frontend HTML/CSS/JavaScript + backend Python/Flask) que modela el
intercambio de mensajes entre procesos mediante **colas de mensajes**, **tuberías (pipes)**
y **memoria compartida** (con y sin sincronización). Permite inyectar fallos, detecta
estancamientos e interbloqueos, compara mecanismos con la misma carga e incluye un
módulo de **IPC real** con procesos del sistema operativo.

> ⚠ **Tipo de implementación:** el simulador es una **SIMULACIÓN de tiempo discreto**:
> los tiempos son *ticks* lógicos, no mediciones reales. La sección **«IPC real»** sí
> crea procesos reales con `multiprocessing` y mide tiempos reales del equipo.

## 1. Requisitos

| Requisito | Detalle |
|---|---|
| Python | 3.10 o superior (probado con 3.12 y 3.13) |
| Dependencias | **Flask** (`pip install -r requirements.txt`) |
| Navegador | Chrome, Edge, Firefox o Safari actualizados |
| Sistema operativo | Windows, Linux o macOS |

## 2. Instalación y ejecución

```bash
# 1. Descomprimir el proyecto y entrar a la carpeta
cd ipc_messenger

# 2. (Recomendado) crear un entorno virtual
python -m venv .venv
.venv\Scripts\activate          # Windows
source .venv/bin/activate       # Linux / macOS

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Ejecutar la aplicación web (abre el navegador automáticamente)
python main.py
#    → http://127.0.0.1:5000
```

Otros modos:

```bash
python main.py --puerto 8080        # otro puerto
python main.py --no-navegador       # no abrir el navegador
python main.py --listar             # lista los 15 escenarios (consola)
python main.py --escenario receptor_cae
python main.py --experimento        # reto de experimentación en consola
python main.py --real 20000         # IPC real en consola
python main.py --escritorio         # versión de escritorio (Tkinter), alternativa
python -m unittest -v               # 34 pruebas automatizadas
```

> En Windows, si `python` no funciona, usa `py`.

## 3. Secciones de la aplicación web

| Sección | Qué hace |
|---|---|
| **Inicio** | Presentación del proyecto, mecanismos, créditos del equipo y logo institucional. |
| **Simulador** | Elige uno de los 15 escenarios o configura uno propio (mecanismo, capacidad, emisores, receptores, timeout, modo bloqueante, sincronización…). Ejecuta continuo, paso a paso o hasta el final. El diagrama muestra el estado de cada proceso, el contenido del canal, los mensajes pendientes y **sobres animados** para cada envío o recepción. Incluye gráfica de ocupación, métricas y registro de eventos. **Inyecta fallos** (💥 Caer, 🧊 Congelar, 🐢 Lento, ✅ Recuperar) en el proceso seleccionado (o haz clic sobre él). Exporta la evidencia en **CSV** (eventos) y **JSON** (métricas). |
| **Experimento** | Ejecuta la **misma carga** sobre cola, tubería, memoria con semáforos y memoria sin sincronizar. Muestra tarjetas resumen, tabla, gráficas y conclusiones automáticas. Exportable a CSV. |
| **IPC real** | El servidor crea procesos reales y envía N mensajes por `Queue`, `Pipe` y memoria compartida con semáforos. Demuestra un `BrokenPipeError` real y la caída silenciosa de un receptor de cola. |
| **Conceptos** | Conceptos de SO representados y simplificaciones del modelo. |

La interfaz es *responsive* (en celulares el diagrama pasa a disposición vertical) y **bilingüe**: el selector **ES / EN** del encabezado traduce toda la página, incluidos los escenarios, el registro de eventos, los diagnósticos y las conclusiones. El idioma elegido se recuerda en el navegador.

## 4. Arquitectura

```
Navegador (HTML + CSS + JS)  ──fetch JSON──►  Flask (web/servidor.py)  ──►  ipc_sim (lógica)
```

```
ipc_messenger/
├── main.py                  Punto de entrada (web por defecto; consola; escritorio)
├── requirements.txt         Flask
├── ipc_sim/                 LÓGICA (independiente de cualquier interfaz)
│   ├── modelo.py            Estados, Mensaje, Accion, Proceso, Resultado
│   ├── mecanismos.py        ColaMensajes, Tuberia, MemoriaCompartida
│   ├── simulador.py         Motor por ticks, fallos, timeouts, estancamiento/interbloqueo, métricas
│   ├── escenarios.py        15 escenarios reproducibles (normal / límite / error)
│   ├── experimento.py       Reto de experimentación y conclusiones
│   └── ipc_real.py          IPC con procesos reales (multiprocessing)
├── web/                     APLICACIÓN WEB
│   ├── servidor.py          API REST (Flask) sin estado
│   └── templates/index.html Página única (SPA)
├── public/static/           Servidos por la CDN en Vercel:
│   ├── css/estilos.css      Paleta institucional USB
│   ├── js/app.js            Lógica de la interfaz
│   ├── js/i18n.js           Traducciones español / inglés
│   └── img/                 Logos de la Universidad y de Ingeniería de Sistemas
├── vercel.json              Configuración de despliegue en Vercel
├── .vercelignore            Archivos que no se suben a Vercel
├── gui/app.py               Versión de escritorio Tkinter (alternativa)
├── tests/                   test_ipc.py (26) + test_web.py (8) = 34 pruebas
└── docs/                    informe_tecnico.md · matriz_pruebas.md · capturas/
```

### Servidor sin estado

El servidor **no guarda simulaciones en memoria** (requisito de plataformas *serverless*
como Vercel, donde cada petición puede atenderla una instancia distinta). El navegador
conserva una **receta** `{escenario, config, ops}` y el servidor reconstruye la simulación
reproduciendo las operaciones. Como el motor es determinista (semilla fija), siempre se
llega exactamente al mismo estado.

```json
{ "escenario": "cola_llena", "config": null,
  "ops": [["p", 12], ["f", "R1", "caer", 3], ["e"]] }
```
`["p", n]` avanza n ticks · `["f", pid, tipo, factor]` inyecta un fallo · `["e"]` ejecuta hasta el final.

### API REST

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/api/escenarios` | Escenarios predefinidos |
| POST | `/api/simular` | Reconstruye la receta y devuelve el estado (procesos, canales, métricas, eventos) |
| POST | `/api/exportar` | Receta + `formato: csv \| json` → archivo de evidencia |
| POST | `/api/experimento` | `{config, fallo_tick}` |
| POST | `/api/ipc-real` | `{n}`: procesos reales del SO |

Las entradas inválidas responden **400** con `{"ok": false, "errores": [...]}`.

## 4.1 Publicar en Vercel

El proyecto ya está preparado: `main.py` expone la instancia Flask `app` (Vercel la detecta
sola), `public/` contiene los archivos estáticos y `vercel.json` amplía el tiempo máximo
de la función a 60 s.

**Opción A: desde GitHub (recomendada)**
1. Sube la carpeta `ipc_messenger` a un repositorio de GitHub (la raíz del repo debe ser la carpeta que contiene `main.py`).
2. En <https://vercel.com> → **Add New… → Project** → importa el repositorio.
3. Deja los valores por defecto (Vercel detecta Flask) y pulsa **Deploy**.
4. Cada `git push` vuelve a desplegar automáticamente.

**Opción B: con la CLI de Vercel** (requiere Node.js)
```bash
npm i -g vercel
cd ipc_messenger
vercel            # vista previa (la primera vez pide iniciar sesión y crear el proyecto)
vercel --prod     # producción
```

**Limitación en Vercel:** en la sección «IPC real», `multiprocessing.Queue` y la memoria
compartida con semáforos necesitan semáforos POSIX (`/dev/shm`), que las funciones
*serverless* no ofrecen; la página los marca como «No disponible en este servidor».
`Pipe` y todo el simulador funcionan normalmente. Para la medición completa, ejecútalo en local.

## 5. Escenarios incluidos

| # | Clave | Tipo | Qué demuestra |
|---|---|---|---|
| 1 | `normal_cola` | normal | 2 emisores, 2 receptores, cola de 4 |
| 2 | `cola_llena` | límite | Emisores bloqueados con la cola llena |
| 3 | `cola_no_bloq` | límite | `EAGAIN` en envío no bloqueante |
| 4 | `receptor_cae` | error | Receptor caído → estancamiento detectado |
| 5 | `receptor_cae_timeout` | error | El timeout detecta la caída |
| 6 | `receptor_congelado` | error | El receptor deja de responder y se recupera |
| 7 | `tuberia_normal` | normal | Tubería con reensamblado y EOF |
| 8 | `tuberia_parcial` | límite | Lecturas parciales de 7 bytes |
| 9 | `tuberia_rota` | error | `EPIPE` / `SIGPIPE` |
| 10 | `tuberia_multilector` | error | Mensajes corruptos con 2 lectores |
| 11 | `memoria_sin_sync` | error | Condición de carrera |
| 12 | `memoria_sync` | normal | Mutex + semáforos, sin pérdidas |
| 13 | `mutex_huerfano` | error | Proceso que muere dentro de la sección crítica |
| 14 | `interbloqueo` | error | Espera circular A → B → A |
| 15 | `sin_interbloqueo` | normal | Se rompe la espera circular |

## 6. Responsables por componente

> Propuesta de distribución: ajústenla a lo que hizo realmente cada integrante antes de entregar.

| Integrante | Componentes |
|---|---|
| Jefersson Hernando Rivera Peñaranda | `ipc_sim/simulador.py` (motor, fallos, detección de estancamiento), `experimento.py`, informe técnico |
| Cristian Miranda Zuluaga | `ipc_sim/mecanismos.py` (cola, tubería, memoria compartida), `ipc_real.py`, API `web/servidor.py` |
| Victor Manuel Ortega Blanco | Frontend web (`templates`, `static`), `escenarios.py`, pruebas y matriz de pruebas |

## 7. Limitaciones conocidas

- Simulación de tiempo discreto: un paso por proceso por tick, sin planificador de CPU ni cambios de contexto.
- Los procesos bloqueados reintentan cada tick (equivale a despertarlos cuando cambia el recurso).
- La tubería delimita mensajes con `\n`; no modela `PIPE_BUF` exacto.
- No se modelan claves IPC, permisos ni límites del núcleo.
- Cada petición reproduce la simulación desde el inicio (máx. 25 000 ticks por receta); es instantáneo para los tamaños del proyecto.
- En local se usa el servidor de desarrollo de Flask; en Vercel corre como función serverless.
- Las tipografías se cargan de Google Fonts; sin internet se usan las fuentes del sistema.
