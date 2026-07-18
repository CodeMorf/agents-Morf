# Hybrid Model Router — política de producción (VPS sin GPU)

## Problema observado

Una sola generación con `llama3.2:1b` en Ollama elevó la CPU del host de ~2% a ~94% mientras la RAM se mantenía ~4%. El cuello de botella es **CPU**, no memoria.

Ollama **no** debe ser el proveedor principal de conversación en producción en un VPS compartido con FastAPI, PostgreSQL, Redis, Qdrant y Nginx.

## Arquitectura

```text
Solicitud
    │
    ▼
Hybrid Model Router
    │
    ├── Caché / respuesta conocida (futuro Redis)
    ├── Herramientas / backend externo
    ├── Ollama: tareas pequeñas y controladas (máx. 1 inferencia)
    └── API externa: conversación y razonamiento (Groq, OpenAI, …)
```

## Uso de Ollama local

- embeddings
- clasificación de intención
- extracción de campos
- resúmenes cortos
- memoria (jobs en background)
- tareas privadas controladas
- **máximo una inferencia local simultánea**

## Uso de proveedores externos

- conversación en Studio
- clientes en producción
- razonamiento complejo
- contextos grandes
- tool calling
- alta concurrencia / picos / fallback

## Límites Ollama (Docker Compose)

Ver `docker-compose.yml` servicio `ollama`:

- `cpus: 4.0` — reserva el resto de núcleos a la plataforma
- `mem_limit: 10g`
- `OLLAMA_NUM_PARALLEL=1`
- `OLLAMA_MAX_LOADED_MODELS=1`
- `OLLAMA_MAX_QUEUE=4`
- `OLLAMA_KEEP_ALIVE=1m` (o `0` en bare metal systemd)
- `OLLAMA_NUM_THREAD=4`

`KEEP_ALIVE` descarga el modelo en reposo; **no** reduce CPU mientras genera. El techo real es `cpus` / `CPUQuota`.

## Regla de decisión

```text
Si existe respuesta en caché → Redis
Si resuelve con herramienta → tool call / server tool
Si embedding|clasificación|resumen corto
   y CPU < 60%
   y no hay otra inferencia local → Ollama
Si CPU >= 60% o cola local o tarea compleja
   o conversación de producción → proveedor externo
Si externo falla → siguiente proveedor permitido
```

## Código

- `apps/backend/app/services/hybrid_router.py` — decisión y reordenamiento
- `apps/backend/app/services/orchestrator.py` — aplica orden external-first en chat

## Operación bare metal (aaPanel sin Docker Ollama)

```bash
ollama stop llama3.2:1b
# o detener todos los cargados
systemctl restart ollama
# límites en /etc/systemd/system/ollama.service.d/limits.conf
```

En este VPS Ollama corre como **systemd**, no como contenedor Docker.
