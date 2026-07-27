import { apiClient } from "@/lib/apiClient";
import { getErrorMessage } from "../curves/api";
import type {
  DeviceParameters,
  FieldCompareResponse,
  FieldConfig,
  FieldDisplayResponse,
  FieldResponse,
} from "./types";

export { getErrorMessage };

export async function predictField(parameters: DeviceParameters) {
  const response = await apiClient.post<FieldResponse>("/fields/predict", parameters);
  return response.data;
}

export async function fetchFieldDisplay(
  parameters: DeviceParameters,
  display: string,
  scaleMode: string,
  rangeMode: string,
) {
  const response = await apiClient.post<FieldDisplayResponse>("/fields/display", {
    ...parameters,
    display,
    scale_mode: scaleMode,
    range_mode: rangeMode,
  });
  return response.data;
}

export async function fetchFieldDisplayCompare(
  devices: FieldConfig[],
  display: string,
  scaleMode: string,
  rangeMode: string,
) {
  const response = await apiClient.post<FieldCompareResponse>("/fields/display/compare", {
    devices,
    display,
    scale_mode: scaleMode,
    range_mode: rangeMode,
  });
  return response.data;
}

interface ExplainFieldsPayload {
  descriptions: string[];
  comparisons: string[];
  tradeoffs: string[];
  cautions: string[];
  provider: string;
  model: string;
  cached: boolean;
}

export async function explainFields(
  fields: FieldConfig[],
  display: string,
  scaleMode: string,
  rangeMode: string,
) {
  const response = await apiClient.post<ExplainFieldsPayload>("/explain/fields", {
    fields,
    display,
    scale_mode: scaleMode,
    range_mode: rangeMode,
  });
  return response.data;
}

export async function previewFieldsPrompt(
  fields: FieldConfig[],
  display: string,
  scaleMode: string,
  rangeMode: string,
) {
  const response = await apiClient.post<{ prompt: string }>("/explain/fields/prompt", {
    fields,
    display,
    scale_mode: scaleMode,
    range_mode: rangeMode,
  });
  return response.data;
}
