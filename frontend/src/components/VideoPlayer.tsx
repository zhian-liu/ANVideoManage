import { useEffect, useRef } from 'react';

import flvjs from 'flv.js';

interface VideoPlayerProps {
  url: string;
  live?: boolean;
  muted?: boolean;
  onError?: () => void;
}

export default function VideoPlayer({
  url,
  live = true,
  muted = true,
  onError,
}: VideoPlayerProps) {
  const videoRef = useRef<HTMLVideoElement>(null);

  useEffect(() => {
    const el = videoRef.current;
    if (!el || !url) return;

    if (!live) {
      el.src = url;
      el.load();
      return;
    }

    if (!flvjs.isSupported()) {
      onError?.();
      return;
    }

    const player = flvjs.createPlayer({
      type: 'flv',
      url,
      isLive: true,
    });
    player.attachMediaElement(el);
    player.load();
    player.play().catch(() => onError?.());

    return () => {
      try {
        player.pause();
        player.unload();
        player.destroy();
      } catch {
        /* ignore */
      }
    };
  }, [url, live, onError]);

  return (
    <video
      ref={videoRef}
      className="video-surface"
      muted={muted}
      autoPlay
      playsInline
      controls={!live}
    />
  );
}
