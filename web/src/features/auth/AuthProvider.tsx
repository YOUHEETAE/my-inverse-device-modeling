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

  const logout = useCallback(async () => {
    await logoutRequest();
    setMe(ANONYMOUS);
  }, []);

  return <AuthContext.Provider value={{ me, loading, login, logout }}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within an AuthProvider");
  return ctx;
}
