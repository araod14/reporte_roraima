export function downloadBlob(blob: Blob, filename: string): void {
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

export interface ShareableBlob {
  blob: Blob;
  filename: string;
}

function downloadAll(files: ShareableBlob[]): void {
  files.forEach(({ blob, filename }) => downloadBlob(blob, filename));
}

// Comparte varios archivos en una sola hoja del sistema. Si el navegador no
// admite compartirlos juntos, descarga todos para adjuntarlos manualmente.
export async function shareOrDownloadFiles(
  files: ShareableBlob[],
  title: string,
  text: string,
): Promise<string> {
  try {
    const shareFiles = files.map(
      ({ blob, filename }) => new File([blob], filename, { type: blob.type || "application/pdf" }),
    );
    if (navigator.canShare?.({ files: shareFiles }) && navigator.share) {
      try {
        await navigator.share({ files: shareFiles, title, text });
        return "PDF compartidos";
      } catch (error) {
        if (isShareCancellation(error)) return "Compartir cancelado";

        downloadAll(files);
        return "No se pudo abrir el menú para compartir; ambos PDF fueron descargados";
      }
    }

    downloadAll(files);
    return "Ambos PDF descargados (compartir varios archivos no está soportado)";
  } catch {
    try {
      downloadAll(files);
      return "No se pudo abrir el menú para compartir; ambos PDF fueron descargados";
    } catch {
      return "No se pudieron compartir los PDF";
    }
  }
}
