# Despliegue en el VPS

Orquestación con Docker Compose + **Caddy** (HTTPS automático con Let's Encrypt).
Servicios: `db` (PostgreSQL), `api` (FastAPI + WeasyPrint), `caddy` (proxy + estáticos).

## Requisitos

- VPS con **Docker** y **Docker Compose**.
- Un **dominio** (o subdominio) con un registro **A** apuntando a la IP del VPS.
- Puertos **80** y **443** abiertos en el firewall (Caddy los necesita para el certificado).

## Pasos

### 1. Variables de entorno

```bash
cd deploy
cp .env.example .env
nano .env
```

Define en `.env`:

| Variable | Qué es |
|----------|--------|
| `DOMAIN` | Dominio del servicio (ej. `reportes.midominio.com`). Caddy pide el TLS para este. |
| `BASE_URL` | Normalmente `https://` + el mismo `DOMAIN`. Se usa en el QR del PDF. |
| `JWT_SECRET` | Secreto para firmar los tokens. Genera uno: `openssl rand -hex 32` |
| `SEED_PASSWORD` | Contraseña inicial de los 6 usuarios del seed. |
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | Credenciales de la base. |

### 2. Compilar la PWA

Caddy sirve el build estático desde `../app/dist`, así que hay que generarlo antes:

```bash
cd ../app
npm ci
npm run build          # genera app/dist
cd ../deploy
```

### 3. Levantar todo

```bash
docker compose up -d --build
```

Al arrancar, el contenedor `api`: espera a PostgreSQL → aplica migraciones
(`alembic upgrade head`) → corre el **seed idempotente** (catálogo de 95 elementos + 6
usuarios) → inicia el servidor. Caddy obtiene el certificado TLS automáticamente.

Verifica:

```bash
docker compose ps
docker compose logs -f api
curl -s https://TU_DOMINIO/api/health      # {"status":"ok"}
```

- App: `https://TU_DOMINIO`
- API / Swagger: `https://TU_DOMINIO/api/docs`
- Verificación (QR): `https://TU_DOMINIO/verificar/{inspeccion_id}/{version}`

## Operación

**Usuarios** (contraseña inicial = `SEED_PASSWORD`): `ldavila`, `smartinez`, `darao`,
`mlanz`, `frojas`, `admin`. Cambiar/crear:

```bash
docker compose exec api python -m scripts.manage_users list
docker compose exec api python -m scripts.manage_users passwd darao --password NuevaClave
docker compose exec api python -m scripts.manage_users add jperez "Juan Perez" --password Clave123
```

**Actualizar la app** tras cambios de código:

```bash
cd ../app && npm run build && cd ../deploy   # si tocaste la PWA
docker compose up -d --build                 # reconstruye api y recarga
```

**Backups.** Lo que hay que respaldar:
- Volumen `pgdata` (base de datos).
- Volumen `reports` (PDF/HTML finalizados — **no se regeneran**, si se pierden se pierde el original firmado).

```bash
# Base de datos
docker compose exec -T db pg_dump -U roraima roraima > backup_$(date +%F).sql
# Reportes
docker run --rm -v deploy_reports:/data -v "$PWD":/out alpine \
  tar czf /out/reports_$(date +%F).tgz -C /data .
```

## Datos y persistencia

| Volumen | Contenido |
|---------|-----------|
| `pgdata` | Base de datos PostgreSQL |
| `reports` | PDF + HTML generados (una sola vez por versión) |
| `caddy_data` / `caddy_config` | Certificados TLS y estado de Caddy |

## Detrás de otro reverse proxy

Si el VPS ya tiene su propio proxy (Nginx/Traefik/otro Caddy) terminando TLS, hay dos
opciones:

**A) Quitar Caddy por completo.** Elimina el servicio `caddy` de `docker-compose.yml`,
expón el puerto de `api` (8000) y apunta tu proxy a `/api`, `/verificar` y `/reports`,
sirviendo `app/dist` como estáticos.

**B) Mantener Caddy detrás, en HTTP plano** (el enfoque usado en este VPS). El proxy del
host termina el TLS y hace `proxy_pass` a este Caddy, que ya sabe servir la PWA, `/api`,
`/verificar` y `/reports`. Se activa con **dos archivos locales** (no versionados, son
específicos de cada host — recuérdalos al respaldar o migrar el servidor):

| Archivo | Qué hace |
|---------|----------|
| `Caddyfile.proxied` | Caddyfile alterno que escucha en `:80` **sin pedir certificado** (`handle` para `/api`, `/verificar`, `/reports` y fallback SPA). |
| `docker-compose.override.yml` | Override que publica Caddy solo en `127.0.0.1:8090:80` y monta `Caddyfile.proxied` en vez del `Caddyfile` normal. |

Compose lee `docker-compose.override.yml` automáticamente, así que basta con:

```bash
docker compose up -d --build
```

Luego, en el proxy del host (ej. Nginx), apunta tu `server` con TLS a `http://127.0.0.1:8090`:

```nginx
location / {
    proxy_pass http://127.0.0.1:8090;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

Con este enfoque, `DOMAIN` en `.env` deja de usarse para pedir TLS (lo hace el host), pero
`BASE_URL` debe seguir siendo la URL pública `https://...` porque va en el QR del PDF.

## Desarrollo local

Solo `db` + `api`, sin Caddy ni dominio (API en `http://localhost:8010`):

```bash
docker compose -f docker-compose.dev.yml up --build
```

> **Nota sobre el build:** la capa de `apt` puede ir lenta según la red al compilar la
> imagen del `api`; con red normal compila sin problema. La base está fijada a
> `python:3.12-slim-bookworm`.
