# Verificación Periódica de ISH y SDC (PDVSA)

App para digitalizar el formato de inspección **"Verificación Periódica de ISH y SDC"**.
Pensada para uso en campo con **mala señal**: la app funciona **offline** y sincroniza
con un backend central cuando hay conexión. Al finalizar, el backend genera un **PDF**
(y una versión **HTML**) con **hash de integridad** y **código QR** de verificación,
listo para compartir por WhatsApp.

## Componentes

| Carpeta     | Qué es | Tecnología |
|-------------|--------|-----------|
| `backend/`  | API REST + base de datos + generación de PDF/HTML + verificación | FastAPI, PostgreSQL, SQLAlchemy, Alembic, WeasyPrint |
| `app/`      | App de campo (PWA instalable, offline-first) | React + Vite + TypeScript, Dexie (IndexedDB) |
| `deploy/`   | Orquestación para el VPS | Docker Compose + Caddy (HTTPS automático) |

> **¿Por qué PWA y no Flutter?** Un solo ecosistema de front, se instala en el teléfono
> como una app (ícono, pantalla completa), funciona offline, comparte el PDF por WhatsApp
> con la Web Share API, y se **actualiza al instante** sin recompilar ni redistribuir
> APKs a cada teléfono. Si algún día necesitas un `.apk`, el mismo código se envuelve con
> Capacitor sin reescribir.

---

## Arquitectura

```
Teléfono (PWA instalada)
  └─ IndexedDB + Service Worker   ← llena el formulario OFFLINE
       │  sync por lotes (idempotente por UUID)
       ▼
Caddy (HTTPS del dominio)  ── sirve la PWA
  ├─ /api/*        → FastAPI
  ├─ /verificar/*  → FastAPI (página pública del QR)
  └─ /reports/*    → PDF/HTML (volumen, generados una sola vez)
       │
       ├─ PostgreSQL (volumen pgdata)
       └─ Volumen reports (archivos congelados)
```

---

## 1) Desplegar el backend en el VPS

Requisitos: Docker + Docker Compose y un **dominio apuntando al VPS** (registro A).

```bash
cd deploy
cp .env.example .env
nano .env        # define DOMAIN, BASE_URL, JWT_SECRET, contraseñas
```

Genera un `JWT_SECRET` aleatorio:

```bash
openssl rand -hex 32
```

Compila la PWA (produce `app/dist`, que Caddy sirve) y levanta todo:

```bash
# (una vez) construir la PWA
cd ../app && npm ci && npm run build && cd ../deploy

# levantar db + api + caddy
docker compose up -d --build
```

Al arrancar, el contenedor `api`:
1. espera a PostgreSQL,
2. aplica migraciones (`alembic upgrade head`),
3. corre el **seed idempotente** (catálogo fijo de 95 elementos + 6 usuarios),
4. inicia el servidor.

Caddy obtiene el certificado TLS automáticamente para tu `DOMAIN`. La app queda en
`https://TU_DOMINIO`, la API en `https://TU_DOMINIO/api`, y Swagger en
`https://TU_DOMINIO/api/docs`.

### Usuarios iniciales (seed)

Todos con la contraseña de `SEED_PASSWORD` (cámbiala tras el primer ingreso):

| Usuario | Nombre |
|---------|--------|
| `ldavila` | Leonardo Davila |
| `smartinez` | Siomar Martinez |
| `darao` | Daniel Arao |
| `mlanz` | Mariana Lanz |
| `frojas` | Felix Rojas |
| `admin` | Administrador |

Gestionar usuarios (dentro del contenedor):

```bash
docker compose exec api python -m scripts.manage_users list
docker compose exec api python -m scripts.manage_users passwd darao --password NuevaClave
docker compose exec api python -m scripts.manage_users add jperez "Juan Perez" --password Clave123
```

---

## 2) Configurar la URL del backend en la app

Si sirves la PWA **desde el mismo dominio** que la API (como en `deploy/`, vía Caddy),
**no necesitas configurar nada**: las llamadas van a `/api` en el mismo host.

Solo si sirves la PWA en un dominio distinto, crea `app/.env`:

```
VITE_API_BASE_URL=https://reportes.midominio.com
```

---

## 3) Instalar la PWA en el teléfono

1. Abre `https://TU_DOMINIO` en **Chrome** (Android).
2. Menú ⋮ → **"Agregar a la pantalla de inicio" / "Instalar app"**.
3. Se instala con ícono propio y se abre a pantalla completa, como una app nativa.
4. Inicia sesión una vez con conexión (descarga el catálogo). Después funciona offline.

---

## Flujo de uso

1. **Nueva inspección** → llenar el formulario (funciona sin señal; se guarda solo).
2. Cuando hay señal, se **sincroniza automáticamente** (o con el botón "Sincronizar ahora").
3. **Finalizar y generar reporte** (requiere conexión) → el backend congela los datos,
   genera el PDF+HTML, calcula los hashes y estampa el hash corto + QR en el PDF.
4. **Compartir PDF por WhatsApp** desde la app.
5. Quien lo recibe puede **escanear el QR** → página pública `/verificar/...` que muestra
   los metadatos y permite confirmar que el PDF no fue alterado (compara su SHA-256).
6. ¿Corrección? **Reabrir** genera una **nueva versión** (v2, v3…); la v1 y sus archivos
   y hashes quedan intactos.

---

## Desarrollo local

Ver `backend/README.md` (correr la API con Python) y `app/README.md` (correr la PWA con
`npm run dev`). Para levantar solo la base de datos + API en local:

```bash
cd deploy
docker compose -f docker-compose.dev.yml up --build   # API en http://localhost:8010
```

## Notas de diseño

- **Integridad sin paradoja:** un PDF no puede contener su propio hash. Por eso el hash
  **visible** estampado en el PDF es el `content_hash` (SHA-256 de los datos congelados),
  determinista y embebible. Los hashes de los **bytes** del PDF y del HTML se guardan en
  la base y se muestran/verifican en la página del QR (arrastrando el archivo recibido).
- **Los archivos no se regeneran:** el PDF/HTML se generan **una sola vez** al finalizar
  y se sirven siempre iguales, para que el hash de bytes siga siendo válido.
- **Sync idempotente:** cada inspección y registro usa un **UUID de cliente**; reenviar
  el mismo lote no crea duplicados.
