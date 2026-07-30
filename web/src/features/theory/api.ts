import { apiClient } from "@/lib/apiClient";
import { getErrorMessage } from "@/features/curves/api";
import type { PNOptions, PNResult } from "./types";

export { getErrorMessage };

export async function fetchPNOptions() {
  const response = await apiClient.get<PNOptions>("/theory/pn-junction/options");
  return response.data;
}

export async function fetchPNResult(acceptors: number, donors: number, bias: number) {
  const response = await apiClient.post<PNResult>("/theory/pn-junction/result", { acceptors, donors, bias });
  return response.data;
}
