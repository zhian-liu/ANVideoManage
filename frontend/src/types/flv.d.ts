declare module 'flv.js' {
  export interface FlvPlayer {
    attachMediaElement(el: HTMLMediaElement): void;
    load(): void;
    play(): Promise<void>;
    pause(): void;
    unload(): void;
    destroy(): void;
    on(event: string, cb: (...args: unknown[]) => void): void;
    off(event: string, cb: (...args: unknown[]) => void): void;
  }

  export interface FlvConfig {
    type: 'flv';
    url: string;
    isLive?: boolean;
    hasAudio?: boolean;
    hasVideo?: boolean;
  }

  export function createPlayer(
    config: FlvConfig,
    opts?: Record<string, unknown>
  ): FlvPlayer;

  export function isSupported(): boolean;

  const flvjs: {
    createPlayer: typeof createPlayer;
    isSupported: typeof isSupported;
  };
  export default flvjs;
}
