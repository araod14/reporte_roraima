import type { ReporteMeta } from "./types";

function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.style.display = "none";
  document.body.appendChild(a);
  a.click();
  a.remove();

  // Algunos navegadores empiezan la descarga después de que termina el click.
  // Revocar inmediatamente el object URL puede cancelar el archivo.
  window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
}

function isShareCancellation(error: unknown): boolean {
  return error instanceof DOMException && error.name === "AbortError";
}

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
    if (navigator.canShare?.({ files: [file] }) && navigator.share) {
      try {
        await navigator.share({ files: [file], title, text });
        return "Compartido";
      } catch (error) {
        if (isShareCancellation(error)) return "Compartir cancelado";

        downloadBlob(blob, filename);
        return "No se pudo abrir el menú para compartir; PDF descargado";
      }
    }

    downloadBlob(blob, filename);
    return "Descargado (compartir no soportado en este navegador)";
  } catch {
    try {
      downloadBlob(blob, filename);
      return "No se pudo abrir el menú para compartir; PDF descargado";
    } catch {
      // Último recurso para reportes que también tienen una URL pública.
    }
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
