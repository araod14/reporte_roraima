import { fetchSlides } from "./api";
import { shareOrDownload } from "./report";

// Abre la vista visual interactiva (panel sinóptico) en una pestaña nueva.
// Se descarga con token y se abre como blob: para que funcione con auth.
export async function verSlides(inspeccionId: string): Promise<void> {
  const blob = await fetchSlides(inspeccionId, "html");
  const url = URL.createObjectURL(blob);
  window.open(url, "_blank");
  // El blob URL se libera al cerrar la pestaña; no lo revocamos de inmediato.
}

// Comparte el panel sinóptico en PDF (apaisado) por WhatsApp.
export async function compartirSlides(inspeccionId: string, fecha: string): Promise<string> {
  const blob = await fetchSlides(inspeccionId, "pdf");
  return shareOrDownload(
    blob,
    `Panel_ISH_SDC_${fecha}.pdf`,
    "Panel visual ISH y SDC",
    `Panel de estado ISH y SDC — ${fecha}`,
  );
}
