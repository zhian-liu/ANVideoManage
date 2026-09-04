import { useCallback, useEffect, useRef } from 'react';

import flvjs from 'flv.js';

interface VideoPlayerProps {
  url: string;
  live?: boolean;
  muted?: boolean;
  paused?: boolean;
  onError?: () => void;
  videoKey?: string;
  onVideoElement?: (key: string, element: HTMLVideoElement | null) => void;
}

export default function VideoPlayer({
  url,
  live = true,
  muted = true,
  paused = false,
  onError,
  videoKey,
  onVideoElement,
}: VideoPlayerProps) {
  const videoRef = useRef<HTMLVideoElement | null>(null);

  const assignVideoRef = useCallback(
    (element: HTMLVideoElement | null) => {
      videoRef.current = element;
      if (videoKey) onVideoElement?.(videoKey, element);
    },
    [onVideoElement, videoKey]
  );

  useEffect(() => {
    return () => {
      if (videoKey) onVideoElement?.(videoKey, null);
    };
  }, [onVideoElement, videoKey]);

  useEffect(() => {
    const el = videoRef.current;
    if (!el || !url) return;

    if (!live) {
      el.src = url;
      el.load();
      if (paused) el.pause();
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
    if (!paused) player.play().catch(() => onError?.());

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

  useEffect(() => {
    const el = videoRef.current;
    if (!el) return;

    if (paused) {
      el.pause();
      return;
    }

    el.play().catch(() => onError?.());
  }, [paused, onError]);

  return (
    <video
      ref={assignVideoRef}
      className="video-surface"
      muted={muted}
      autoPlay
      playsInline
      crossOrigin="anonymous"
      controls={!live}
    />
  );
}
