import { ImageOff } from "lucide-react";
import { useState } from "react";

interface ScreenshotSlotProps {
  src: string;
  alt: string;
}

// Renders the screenshot once it exists at `src` (drop the file into
// web/public + this path — Vite serves everything under public/ from the
// site root, no code change needed). Until then, shows a placeholder instead
// of a broken image icon so the page still looks intentional.
export function ScreenshotSlot({ src, alt }: ScreenshotSlotProps) {
  const [failed, setFailed] = useState(false);

  if (failed) {
    return (
      <div className="flex flex-col items-center justify-center gap-2 rounded-md border border-dashed border-outline-variant bg-surface-container-low py-16 text-on-surface-variant">
        <ImageOff className="h-6 w-6" />
        <p className="font-mono text-[11px]">{src}</p>
        <p className="text-xs">스크린샷 준비 중</p>
      </div>
    );
  }

  return (
    <img
      src={src}
      alt={alt}
      className="w-full rounded-md border border-outline-variant"
      onError={() => setFailed(true)}
    />
  );
}
