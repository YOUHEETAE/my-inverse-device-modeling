import { ImageOff } from "lucide-react";
import { useState } from "react";

export interface ScreenshotCallout {
  /** Marker position as a percentage of the image's width/height (0-100). */
  xPct: number;
  yPct: number;
  label: string;
}

interface AnnotatedScreenshotProps {
  src: string;
  alt: string;
  callouts: ScreenshotCallout[];
}

// Same broken-image fallback as ScreenshotSlot, plus numbered markers over the
// image tied to a legend list below it — avoids placing text directly on top
// of an already-busy screenshot.
export function AnnotatedScreenshot({ src, alt, callouts }: AnnotatedScreenshotProps) {
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
    <div className="space-y-3">
      <div className="relative overflow-hidden rounded-md border border-outline-variant">
        <img src={src} alt={alt} className="block w-full" onError={() => setFailed(true)} />
        {callouts.map((c, i) => (
          <div
            key={i}
            className="absolute flex h-6 w-6 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full border-2 border-white bg-primary text-xs font-bold text-white shadow-[0_1px_4px_rgba(0,0,0,0.4)]"
            style={{ left: `${c.xPct}%`, top: `${c.yPct}%` }}
          >
            {i + 1}
          </div>
        ))}
      </div>
      <ol className="grid gap-x-6 gap-y-1.5 text-xs text-on-surface-variant sm:grid-cols-2">
        {callouts.map((c, i) => (
          <li key={i} className="flex items-start gap-2">
            <span className="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-primary text-[10px] font-bold text-white">
              {i + 1}
            </span>
            <span>{c.label}</span>
          </li>
        ))}
      </ol>
    </div>
  );
}
