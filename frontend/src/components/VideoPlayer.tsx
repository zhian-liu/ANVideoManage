import mpegts from 'mpegts.js';
import { useCallback, useEffect, useRef, useState } from 'react';

interface VideoPlayerProps {
  url: string;
  fallbackUrl?: string;
  live?: boolean;
  muted?: boolean;
  paused?: boolean;
  onError?: () => void;
  videoKey?: string;
  onVideoElement?: (key: string, element: HTMLVideoElement | null) => void;
}

export default function VideoPlayer({
  url,
  fallbackUrl,
  live = true,
  muted = true,
  paused = false,
  onError,
  videoKey,
  onVideoElement,
}: VideoPlayerProps) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const [usingFallback, setUsingFallback] = useState(false);

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
    setUsingFallback(false);
  }, [url, fallbackUrl]);

  useEffect(() => {
    const el = videoRef.current;
    if (!el || !url) return;

    if (!live) {
      el.src = url;
      el.load();
      if (paused) el.pause();
      return;
    }

    if (!mpegts.isSupported()) {
      onError?.();
      return;
    }

    const playbackUrl = usingFallback && fallbackUrl ? fallbackUrl : url;
    const isFlv = playbackUrl.toLowerCase().includes('.flv');
    const player = mpegts.createPlayer({
      type: isFlv ? 'flv' : 'mpegts',
      url: playbackUrl,
      isLive: true,
      cors: true,
    }, {
      // Keep enough network buffer for camera jitter while bounding MSE memory.
      enableStashBuffer: true,
      autoCleanupSourceBuffer: true,
      autoCleanupMaxBackwardDuration: 30,
      autoCleanupMinBackwardDuration: 10,
      liveBufferLatencyChasing: true,
    });

    let failedOver = false;
    const handlePlaybackError = () => {
      if (!usingFallback && fallbackUrl && !failedOver) {
        failedOver = true;
        setUsingFallback(true);
        return;
      }
      onError?.();
    };

    player.on(mpegts.Events.ERROR, handlePlaybackError);
    player.attachMediaElement(el);
    player.load();
    if (!paused) Promise.resolve(player.play()).catch(handlePlaybackError);

    return () => {
      try {
        player.off(mpegts.Events.ERROR, handlePlaybackError);
        player.pause();
        player.unload();
        player.destroy();
      } catch {
        /* ignore */
      }
    };
  }, [url, fallbackUrl, live, onError, usingFallback]);

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
