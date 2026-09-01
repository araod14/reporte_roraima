import { fetchSlides } from "./api";
import { shareOrDownloadFiles } from "./report";
import type { ReporteMeta } from "./types";

// Abre la vista visual interactiva (panel sinóptico) en una pestaña nueva.
// Se descarga con token y se abre como blob: para que funcione con auth.
export async function verSlides(inspeccionId: string): Promise<void> {
  const blob = await fetchSlides(inspeccionId, "html");
  const url = URL.createObjectURL(blob);
  window.open(url, "_blank");
  // El blob URL se libera al cerrar la pestaña; no lo revocamos de inmediato.
}

// Comparte juntos el reporte oficial almacenado y el esquema visual generado.
export async function compartirPDFs(
  reporte: ReporteMeta,
  inspeccionId: string,
  fecha: string,
): Promise<string> {
  const reportePromise = fetch(reporte.pdf_url).then(async (res) => {
    if (!res.ok) throw new Error("No se pudo descargar el reporte oficial");
    return res.blob();
  });
  const [reporteBlob, esquemaBlob] = await Promise.all([
    reportePromise,
    fetchSlides(inspeccionId, "pdf"),
  ]);

  return shareOrDownloadFiles(
    [
      {
        blob: reporteBlob,
        filename: `Reporte_ISH_SDC_${fecha}_v${reporte.version}.pdf`,
      },
      {
        blob: esquemaBlob,
        filename: `Esquema_ISH_SDC_${fecha}.pdf`,
      },
    ],
    "Reporte y esquema ISH y SDC",
    `Verificación Periódica ISH y SDC — ${fecha} (v${reporte.version})`,
  );
}
