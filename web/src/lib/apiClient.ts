import axios from "axios";

export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL,
  // 로그인 세션 쿠키를 함께 보낸다. 기본값(false)이면 브라우저가 쿠키를
  // 붙이지 않아 로그인해도 계속 비로그인으로 취급된다.
  withCredentials: true,
});
