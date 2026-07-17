# Instrucciones para subir Agents Morf a GitHub

Repositorio de destino:

```text
https://github.com/CodeMorf/agents-Morf.git
```

## Opción recomendada: terminal

1. Descarga y descomprime `agents-Morf-full.zip`.
2. Abre una terminal dentro de la carpeta `agents-Morf`.
3. Ejecuta:

```bash
git init
git branch -M main
git add .
git commit -m "Initial Agents Morf platform"
git remote add origin https://github.com/CodeMorf/agents-Morf.git
git push -u origin main
```

Si aparece el error `remote origin already exists`, usa:

```bash
git remote set-url origin https://github.com/CodeMorf/agents-Morf.git
git push -u origin main
```

GitHub puede solicitar autenticación mediante navegador o token personal. No escribas claves de proveedores de IA ni SMTP2GO en GitHub.

## Descripción del repositorio

```text
Agents Morf — The Autonomous AI Agent Operating System for sales, reservations, restaurant operations, support and real-world business automation.
```

## Página web

```text
https://agent.codemorf.tech
```

## Topics sugeridos

```text
ai-agents
autonomous-agents
fastapi
react
vite
multi-tenant
llm
ollama
sales-automation
restaurant-automation
reservations
openai-compatible
```

## Después de subirlo

En GitHub entra a **Settings → General** y configura la descripción y el sitio web. Después protege la rama `main` en **Settings → Branches** cuando empieces a colaborar con más desarrolladores.

## Instalación en el servidor

```bash
git clone https://github.com/CodeMorf/agents-Morf.git
cd agents-Morf
cp .env.example .env
nano .env
docker compose up -d --build
```

Después crea el administrador:

```bash
docker compose exec backend python -m app.cli create-admin \
  --email admin@codemorf.tech \
  --password 'CREA_UNA_CONTRASEÑA_LARGA_Y_UNICA' \
  --organization CodeMorf
```
