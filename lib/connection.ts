export type Connection = {
  baseUrl: string;
  apiKey: string;
  datasetId: string;
  noticeDatasetId?: string;
};

const CONFIG_KEY = "jnu-ragflow-connection";
const API_KEY = "jnu-ragflow-api-key";

export function loadConnection(): Connection {
  if (typeof window === "undefined") return { baseUrl: "", apiKey: "", datasetId: "" };
  let saved: Partial<Connection> = {};
  try { saved = JSON.parse(localStorage.getItem(CONFIG_KEY) || "{}"); } catch {}
  return {
    baseUrl: saved.baseUrl || "",
    datasetId: saved.datasetId || "",
    noticeDatasetId: saved.noticeDatasetId || "",
    apiKey: sessionStorage.getItem(API_KEY) || localStorage.getItem(API_KEY) || ""
  };
}

export function saveConnection(value: Connection, remember: boolean): void {
  localStorage.setItem(CONFIG_KEY, JSON.stringify({
    baseUrl: value.baseUrl,
    datasetId: value.datasetId,
    noticeDatasetId: value.noticeDatasetId || ""
  }));
  sessionStorage.setItem(API_KEY, value.apiKey);
  if (remember) localStorage.setItem(API_KEY, value.apiKey);
  else localStorage.removeItem(API_KEY);
}

export function clearConnection(): void {
  localStorage.removeItem(CONFIG_KEY);
  localStorage.removeItem(API_KEY);
  sessionStorage.removeItem(API_KEY);
}

export function isRemembered(): boolean {
  return typeof window !== "undefined" && Boolean(localStorage.getItem(API_KEY));
}
