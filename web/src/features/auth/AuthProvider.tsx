import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { setUnauthorizedHandler } from "@/lib/apiClient";
import { fetchMe, logout as logoutRequest, startGoogleLogin, takeReturnPath, type Me } from "./api";

// 로그인 상태를 App 수준에 한 번만 둔다. 훅이 각자 상태를 들고 있으면
// 화면마다 /auth/me를 따로 부르고, 아바타 메뉴에서 로그아웃해도 다른
// 화면(자유질문 입력창 등)은 로그인 상태로 남는다.
const ANONYMOUS: Me = { authenticated: false, user_id: null, name: null, email: null };

interface AuthValue {
  me: Me;
  loading: boolean;
  login: () => void;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<Me>(ANONYMOUS);
  const [loading, setLoading] = useState(true);
  const location = useLocation();
  const navigate = useNavigate();

  useEffect(() => {
    let cancelled = false;

    fetchMe()
      .then((data) => {
        if (cancelled) return;
        setMe(data);

        // 로그인하고 막 돌아온 참이면 원래 보던 화면으로 되돌린다.
        // 백엔드는 항상 프론트 첫 화면으로 보내기 때문에(SecurityConfig의
        // defaultSuccessUrl) 여기서 복원해줘야 한다.
        if (data.authenticated) {
          const returnPath = takeReturnPath();
          if (returnPath && returnPath !== location.pathname + location.search) {
            navigate(returnPath, { replace: true });
          }
        }
      })
      // 서버가 꺼져있거나 응답이 이상해도 화면은 떠야 하므로 비로그인으로 둔다.
      .catch(() => {
        if (!cancelled) setMe(ANONYMOUS);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
    // 최초 1회만 확인한다. 로그인 상태는 페이지 이동으로 바뀌지 않는다.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // 어떤 요청이든 401을 받으면(= 세션 만료) 화면 전체를 비로그인으로
  // 되돌린다. 아바타는 로그인 상태인데 입력창만 막히는 어긋남을 막는다.
  useEffect(() => {
    setUnauthorizedHandler(() => setMe(ANONYMOUS));
    return () => setUnauthorizedHandler(null);
  }, []);

  const login = useCallback(() => {
    startGoogleLogin(location.pathname + location.search);
  }, [location]);

  // 서버 세션을 끊는 것만으로는 화면이 비지 않는다. 자유질문 말풍선,
  // 진행 중이던 Case Study의 답변과 피드백은 이미 리액트 상태로 그려져
  // 있어서 로그아웃 뒤에도 그대로 남는다 — 실습실 같은 공용 PC에서는
  // 다음 사람이 그걸 그대로 읽는다.
  //
  // 훅마다 로그아웃을 구독해 각자 비우는 방법도 있지만 하나 빠뜨리기 쉽고,
  // 상태를 가진 화면이 늘 때마다 같은 실수가 되풀이된다(이 버그가 정확히
  // 그렇게 생겼다). 통째로 다시 불러오면 어디에 무엇이 남아 있든 사라진다.
  const logout = useCallback(async () => {
    await logoutRequest();
    sessionStorage.clear();
    window.location.assign("/");
  }, []);

  return <AuthContext.Provider value={{ me, loading, login, logout }}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within an AuthProvider");
  return ctx;
}
