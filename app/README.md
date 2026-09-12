# App de campo — PWA (React + Vite)

PWA instalable, offline-first, para llenar el formulario de inspección y compartir el
reporte por WhatsApp.

## Desarrollo

```bash
npm ci
npm run dev        # http://localhost:5173 (o el que quede libre)
```

En desarrollo, Vite hace **proxy** de `/api` al backend. El destino está en
`vite.config.ts` (`server.proxy`); por defecto `http://localhost:8010` (el compose de
desarrollo). Ajústalo si tu API corre en otro puerto.

## Build de producción

```bash
npm run build      # genera dist/  (lo sirve Caddy en deploy/)
npm run preview    # previsualizar el build
```

## Estructura

```
src/
  main.tsx            registro del Service Worker + router (HashRouter)
  App.tsx             rutas y guardas de sesión
  api.ts              llamadas al backend (login, catalogo, sync, finalizar…)
  db.ts               IndexedDB (Dexie): inspecciones, catalogo, meta
  sync.ts             cola de sincronización + auto-sync + refresh de catálogo
  catalogo.ts         catálogo empaquetado (fallback 100% offline)
  report.ts           compartir PDF (Web Share API) con fallback a descarga
  types.ts            tipos compartidos
  pages/
    Login.tsx         inicio de sesión
    Lista.tsx         listado + estado de sync + botón "Sincronizar ahora"
    Formulario.tsx    formulario por Instalación→Sistema; SIMPLE / CCC / UPS
```

## Cómo funciona el offline

- Todo se guarda en **IndexedDB** al escribir (autosave). Cada inspección tiene
  `syncState: pending | synced`.
- `startAutoSync` intenta sincronizar al recuperar conexión (`online`) y cada 60 s; hay
  además un botón **"Sincronizar ahora"**.
- El **catálogo** se descarga al iniciar sesión y se cachea; si no hay red, se usa el
  catálogo empaquetado en `catalogo.ts` (regenerado desde `backend/app/catalogo_data.py`).
- **Finalizar** requiere conexión (genera el reporte en el backend).

## Configuración

Normalmente no hace falta configurar nada si la PWA se sirve desde el mismo dominio que
la API. Si están en dominios distintos, define en `.env`:

```
VITE_API_BASE_URL=https://reportes.midominio.com
```

## Compartir a WhatsApp

`report.ts` usa `navigator.share({ files: [pdf] })` (Web Share API, soportada en Android
Chrome). Si el navegador no soporta compartir archivos, cae automáticamente a descargar
el PDF.

## Reporte diario

La pantalla principal tiene botones **Reporte semanal** y **Reporte diario**, y
filtros del historial. El diario guarda automáticamente borradores en IndexedDB;
la actualización del esquema local conserva las inspecciones existentes.

Capture fecha/hora de Venezuela, responsable, LCN A/B, las GUS y temperaturas
ISH-1/ISH-2 en °C (coma o punto decimal). Las observaciones son opcionales.
El último responsable ingresado se recuerda en el teléfono. Los estados GUS
se capturan cada día; no se copian de una inspección semanal.

Los borradores se sincronizan al recuperar conexión, cada minuto mientras la
pantalla está abierta y con **Sincronizar ahora** en el historial. Finalizar
requiere conexión y todos los campos obligatorios. Si otro teléfono cambió el
reporte, revise la versión recuperada antes de finalizar.

Después del cierre puede ver, descargar y compartir el PNG. El menú de compartir
requiere un navegador compatible en HTTPS (o localhost); de lo contrario se
descarga la imagen para adjuntarla manualmente. Una imagen ya abierta puede
compartirse sin conexión mientras permanezca en pantalla; abrir otra versión
requiere conexión. Reabrir permite corregir y generar una nueva versión,
conservando las imágenes anteriores.
