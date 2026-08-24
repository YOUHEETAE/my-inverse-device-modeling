import axios from "axios";

export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL,
  // 로그인 세션 쿠키를 함께 보낸다. 기본값(false)이면 브라우저가 쿠키를
  // 붙이지 않아 로그인해도 계속 비로그인으로 취급된다.
  withCredentials: true,
});

// 세션은 화면을 열어둔 사이에도 만료된다. 진입할 때 한 번 확인한 로그인
// 상태를 계속 믿으면, 만료된 뒤에도 입력창이 열려 있다가 raw 401을 토해낸다.
// 그래서 어떤 요청이든 401을 받으면 앱 전체를 비로그인으로 되돌린다 —
// 아바타와 입력창이 함께 바뀌어야 사용자가 무슨 일이 났는지 알 수 있다.
let onUnauthorized: (() => void) | null = null;

export function setUnauthorizedHandler(handler: (() => void) | null) {
  onUnauthorized = handler;
}

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (axios.isAxiosError(error) && error.response?.status === 401) {
      onUnauthorized?.();
    }
    // 호출부가 각자 오류를 표시할 수 있도록 그대로 흘려보낸다.
    return Promise.reject(error);
  },
);
