import { LogOut, User } from "lucide-react";
import { Menu, MenuContent, MenuItem, MenuSeparator, MenuTrigger } from "@/components/ui/menu";
import { useAuth } from "./useAuth";

// 이름 첫 글자로 원형 배지를 만든다. 구글이 프로필 사진(picture)도 주지만
// 지금은 세션에 담지 않아서, 사진이 필요해지면 CustomOAuth2UserService와
// /auth/me에 함께 추가해야 한다.
function initialOf(name: string | null) {
  return name?.trim().charAt(0) ?? "?";
}

export function AccountMenu() {
  const { me, loading, login, logout } = useAuth();

  // 확인 중에는 아무것도 그리지 않는다. 잠깐 "로그인" 버튼이 보였다가
  // 아바타로 바뀌면 깜빡이는 것처럼 보인다.
  if (loading) {
    return <div className="h-7 w-7" aria-hidden />;
  }

  // 비로그인은 회색 기본 아바타. 로그인 후 자리와 크기가 같아서 상태가
  // 바뀌어도 헤더가 흔들리지 않는다. 아이콘만으로는 무슨 버튼인지 알기
  // 어려우므로 title/aria-label로 알려준다.
  if (!me.authenticated) {
    return (
      <button
        type="button"
        onClick={login}
        title="구글 계정으로 시작하기"
        aria-label="구글 계정으로 시작하기"
        className="flex h-7 w-7 items-center justify-center rounded-full bg-surface-container-high text-on-surface-variant transition-colors hover:bg-outline-variant hover:text-foreground"
      >
        <User className="h-4 w-4" />
      </button>
    );
  }

  return (
    <Menu>
      <MenuTrigger
        render={
          <button
            type="button"
            aria-label="계정 메뉴"
            className="flex h-7 w-7 items-center justify-center rounded-full bg-primary text-xs font-semibold text-on-primary transition-opacity hover:opacity-80"
          />
        }
      >
        {initialOf(me.name)}
      </MenuTrigger>
      <MenuContent>
        <div className="px-2 py-1.5">
          <p className="truncate text-xs font-medium">{me.name}</p>
          <p className="truncate text-[11px] text-on-surface-variant">{me.email}</p>
        </div>
        <MenuSeparator />
        <MenuItem onClick={logout}>
          <LogOut className="h-3.5 w-3.5" />
          로그아웃
        </MenuItem>
      </MenuContent>
    </Menu>
  );
}
