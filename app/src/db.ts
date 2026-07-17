import Dexie, { type Table } from "dexie";
import type { CatalogoElemento, Inspeccion } from "./types";

class RoraimaDB extends Dexie {
  inspecciones!: Table<Inspeccion, string>;
  catalogo!: Table<CatalogoElemento, string>;
  meta!: Table<{ key: string; value: string }, string>;

  constructor() {
    super("roraima");
    this.version(1).stores({
      inspecciones: "id, estado, syncState, updated:client_updated_at",
      catalogo: "codigo, orden",
      meta: "key",
    });
  }
}

export const db = new RoraimaDB();

export async function getMeta(key: string): Promise<string | undefined> {
  return (await db.meta.get(key))?.value;
}

export async function setMeta(key: string, value: string): Promise<void> {
  await db.meta.put({ key, value });
}

export async function delMeta(key: string): Promise<void> {
  await db.meta.delete(key);
}
