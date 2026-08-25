import axios from "axios";
import { apiClient } from "@/lib/apiClient";
import type { CurveConfig, CurveResponse, ExplainResponse, PromptResponse, DeviceParameters } from "./types";

// 화면에 그대로 보이는 문장이라 한국어로 돌려준다. 서버가 주는 detail도
// 전부 한국어다(자바의 ResponseStatusException, Python의
// public_presentation.py) — 여기서만 영어를 쓰면 한 화면에 두 언어가 섞인다.
export function getErrorMessage(err: unknown): string {
    if (axios.isAxiosError(err)) {
        // 스프링 시큐리티의 401은 본문 없이 상태 코드만 온다
        // (SecurityConfig의 HttpStatusEntryPoint). detail이 없으니 그대로
        // 두면 axios의 "Request failed with status code 401"이 사용자에게
        // 그대로 보인다.
        if (err.response?.status === 401) {
            return "로그인이 필요합니다. 로그인 후 다시 시도해 주세요.";
        }
        return err.response?.data?.detail ?? "요청을 처리하지 못했습니다. 잠시 후 다시 시도해 주세요.";
    }
    return "문제가 발생했습니다. 잠시 후 다시 시도해 주세요.";
}

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