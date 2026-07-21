import type { ReporteMeta } from "./types";

// Comparte un blob por Web Share API (WhatsApp con archivos). Si el navegador
// no soporta compartir archivos, cae a descargar; último recurso: abrir en pestaña.
export async function shareOrDownload(
  blob: Blob,
  filename: string,
  title: string,
  text: string,
  fallbackUrl?: string,
): Promise<string> {
  try {
    const file = new File([blob], filename, { type: blob.type || "application/pdf" });
    const nav = navigator as any;
    if (nav.canShare && nav.canShare({ files: [file] })) {
      await nav.share({ files: [file], title, text });
      return "Compartido";
    }
    // Fallback: descargar el archivo.
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
    return "Descargado (compartir no soportado en este navegador)";
  } catch {
    if (fallbackUrl) {
      window.open(fallbackUrl, "_blank");
      return "Abierto en el navegador";
    }
    return "No se pudo compartir";
  }
}

// Descarga el PDF del reporte oficial y lo comparte por WhatsApp.
export async function compartirPDF(reporte: ReporteMeta, fecha: string): Promise<string> {
  const filename = `Reporte_ISH_SDC_${fecha}_v${reporte.version}.pdf`;
  try {
    const res = await fetch(reporte.pdf_url);
    if (!res.ok) throw new Error("No se pudo descargar el PDF");
    const blob = await res.blob();
    return shareOrDownload(
      blob,
      filename,
      "Reporte ISH y SDC",
      `Verificación Periódica ISH y SDC — ${fecha} (v${reporte.version})`,
      reporte.pdf_url,
    );
  } catch {
    window.open(reporte.pdf_url, "_blank");
    return "PDF abierto en el navegador";
  }
}
