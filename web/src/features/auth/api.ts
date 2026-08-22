import { apiClient } from "@/lib/apiClient";

export interface Me {
  authenticated: boolean;
  user_id: number | null;
  name: string | null;
  email: string | null;
}

// 로그인 직전 보고 있던 경로를 담아두는 키. 로그인은 페이지를 완전히 떠났다가
// 돌아오는 흐름이라, 이걸 저장해두지 않으면 항상 첫 화면으로 돌아온다.
const RETURN_PATH_KEY = "auth:returnPath";

export async function fetchMe() {
  const response = await apiClient.get<Me>("/auth/me");
  return response.data;
}

// 스프링 시큐리티가 제공하는 진입점으로 "실제 페이지 이동"을 한다.
// fetch/axios로 부르면 안 된다 — 구글로 리다이렉트되는 흐름이라 XHR로는
// 따라갈 수 없고 CORS에도 막힌다.
export function startGoogleLogin(currentPath: string) {
  sessionStorage.setItem(RETURN_PATH_KEY, currentPath);
  window.location.href = `${import.meta.env.VITE_API_BASE_URL}/oauth2/authorization/google`;
}

// 로그인 후 돌아왔을 때 원래 보던 경로를 꺼낸다. 한 번 쓰면 지워서, 이후
// 새로고침에서 엉뚱하게 이동하지 않게 한다.
export function takeReturnPath() {
  const path = sessionStorage.getItem(RETURN_PATH_KEY);
  sessionStorage.removeItem(RETURN_PATH_KEY);
  return path;
}

// 로그아웃은 반드시 POST여야 한다. GET 링크로 두면 다른 사이트가
// <img src="...logout"> 같은 것으로 사용자를 강제 로그아웃시킬 수 있다.
export async function logout() {
  await apiClient.post("/logout");
}
