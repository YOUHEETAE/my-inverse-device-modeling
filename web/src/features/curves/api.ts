import { apiClient } from "@/lib/apiClient";
import type { CurveConfig, CurveResponse, ExplainResponse, PromptResponse, DeviceParameters } from "./types";

export async function predictCurve(parameters: DeviceParameters) {
    const response = await apiClient.post<CurveResponse>("/curves/predict", parameters);
    return response.data;
}

export async function explainCurve(curves: CurveConfig[]) {
    const response = await apiClient.post<ExplainResponse>("/explain/curves", { curves });
    return response.data;
}

export async function previewCurvePrompt(curves: CurveConfig[]) {
    const response = await apiClient.post<PromptResponse>("/explain/curves/prompt", { curves })
    return response.data;
}