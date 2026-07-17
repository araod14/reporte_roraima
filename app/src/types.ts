export type Tipo = "SIMPLE" | "CCC" | "UPS";
export type Estado = "OK" | "MALO" | "OBSERVACION";

export interface CatalogoElemento {
  codigo: string;
  instalacion: string;
  sistema: string;
  nombre: string;
  tipo: Tipo;
  ups_dobles: boolean;
  orden: number;
}

export interface Registro {
  id: string;
  catalogo_codigo: string;
  estado?: Estado | null;
  comentario?: string | null;
  valor_a?: string | null;
  valor_b?: string | null;
  fuente_1?: boolean | null;
  bateria_1?: boolean | null;
  fan_1?: boolean | null;
  fuente_2?: boolean | null;
  bateria_2?: boolean | null;
  fan_2?: boolean | null;
  fuente_3?: boolean | null;
  bateria_3?: boolean | null;
  fan_3?: boolean | null;
  fuente_4?: boolean | null;
  bateria_4?: boolean | null;
  fan_4?: boolean | null;
}

export type SyncState = "pending" | "synced";
export type EstadoInspeccion = "BORRADOR" | "FINALIZADA";

export interface Inspeccion {
  id: string;
  fecha: string; // YYYY-MM-DD
  inspeccionado_por_nombre: string;
  verificado_por_nombre: string;
  aprobado_por_nombre: string;
  observaciones_generales: string;
  estado: EstadoInspeccion;
  syncState: SyncState;
  client_updated_at: string; // ISO
  registros: Record<string, Registro>; // por catalogo_codigo
  // Datos del último reporte generado (si finalizada)
  reporte?: ReporteMeta;
}

export interface ReporteMeta {
  version: number;
  pdf_url: string;
  html_url: string;
  verificar_url: string;
  pdf_hash_short: string;
  content_hash: string;
}
