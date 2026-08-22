import { useCallback, useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { fetchMe, logout as logoutRequest, startGoogleLogin, takeReturnPath, type Me } from "./api";

const ANONYMOUS: Me = { authenticated: false, user_id: null, name: null, email: null };

export function useAuth() {
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

  const login = useCallback(() => {
    startGoogleLogin(location.pathname + location.search);
  }, [location]);

  const logout = useCallback(async () => {
    await logoutRequest();
    setMe(ANONYMOUS);
  }, []);

  return { me, loading, login, logout };
}
