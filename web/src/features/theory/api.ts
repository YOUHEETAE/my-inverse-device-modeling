import { apiClient } from "@/lib/apiClient";
import { getErrorMessage } from "@/features/curves/api";
import type { LongChannelOptions, LongChannelResult, PNOptions, PNResult } from "./types";

export { getErrorMessage };

export async function fetchPNOptions() {
  const response = await apiClient.get<PNOptions>("/theory/pn-junction/options");
  return response.data;
}

export async function fetchPNResult(acceptors: number, donors: number, bias: number) {
  const response = await apiClient.post<PNResult>("/theory/pn-junction/result", { acceptors, donors, bias });
  return response.data;
}

export async function fetchLongChannelOptions() {
  const response = await apiClient.get<LongChannelOptions>("/theory/long-channel-mosfet/options");
  return response.data;
}

export async function fetchLongChannelResult(gateVoltage: number, drainVoltage: number) {
  const response = await apiClient.post<LongChannelResult>("/theory/long-channel-mosfet/result", {
    gate_voltage: gateVoltage,
    drain_voltage: drainVoltage,
  });
  return response.data;
}
