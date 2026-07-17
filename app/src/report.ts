import type { ReporteMeta } from "./types";

// Descarga el PDF y lo comparte por WhatsApp (Web Share API con archivos).
// Si el navegador no soporta compartir archivos, cae a abrir/descargar el PDF.
export async function compartirPDF(reporte: ReporteMeta, fecha: string): Promise<string> {
  const filename = `Reporte_ISH_SDC_${fecha}_v${reporte.version}.pdf`;
  try {
    const res = await fetch(reporte.pdf_url);
    if (!res.ok) throw new Error("No se pudo descargar el PDF");
    const blob = await res.blob();
    const file = new File([blob], filename, { type: "application/pdf" });

    const nav = navigator as any;
    if (nav.canShare && nav.canShare({ files: [file] })) {
      await nav.share({
        files: [file],
        title: "Reporte ISH y SDC",
        text: `Verificación Periódica ISH y SDC — ${fecha} (v${reporte.version})`,
      });
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
  } catch (e) {
    // Último recurso: abrir el PDF del backend en una pestaña.
    window.open(reporte.pdf_url, "_blank");
    return "PDF abierto en el navegador";
  }
}
