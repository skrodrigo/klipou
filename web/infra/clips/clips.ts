import { request } from "../http";
import type { Clip } from "./types/clips-types";


export async function listClips(): Promise<Clip[]> {
  const data = await request<{ results: Clip[] }>("/api/clips/");
  return data.results ?? [];
}

export async function createClip(title: string): Promise<Clip> {
  return request<Clip>("/api/clips/", {
    method: "POST",
    body: JSON.stringify({ title }),
  });
}
