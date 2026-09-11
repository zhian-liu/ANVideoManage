import { useEffect, useRef } from 'react';
import type { Dispatch, SetStateAction } from 'react';
import { message } from 'antd';
import { isAxiosError } from 'axios';
import * as api from '../api';
import type { Device, StreamInfo } from '../api/types';

// One renewable lease per visible GB channel in this page, regardless of window count.
export function useGbPlayback(
  devices: Device[], ids: Array<number | null>,
  setStreams: Dispatch<SetStateAction<Record<number, StreamInfo>>>
) {
  const desired = useRef(new Set<number>());
  const reconcile = useRef<() => void>(() => undefined);
  const gbIds = new Set(devices.filter((d) => d.enabled && d.access_type === 'gb28181').map((d) => d.id));
  desired.current = new Set(ids.filter((id): id is number => id != null && gbIds.has(id)));
  const key = [...desired.current].sort((a, b) => a - b).join(',');

  useEffect(() => {
    let disposed = false;
    const leases = new Map<number, string>();
    const pending = new Set<number>();
    const due = new Map<number, number>();
    const errors = new Map<number, string>();
    const release = (id: number, leaseId: string) => {
      void api.releaseGbLease(id, leaseId).catch(() => {
        // Server-side expiration releases the lease if a tab exits without connectivity.
      });
    };
    const acquire = async (id: number) => {
      if (pending.has(id)) return;
      pending.add(id);
      try {
        let info;
        try {
          info = await api.acquireGbLease(id, leases.get(id));
        } catch (err) {
          if (!isAxiosError(err) || err.response?.status !== 404 || !leases.has(id)) throw err;
          leases.delete(id);
          info = await api.acquireGbLease(id);
        }
        if (disposed || !desired.current.has(id)) {
          release(id, info.lease_id);
          return;
        }
        leases.set(id, info.lease_id);
        due.set(id, Date.now() + 15000);
        errors.delete(id);
        setStreams((previous) => ({ ...previous, [id]: info }));
      } catch (err) {
        const old = leases.get(id);
        if (old) release(id, old);
        leases.delete(id);
        due.set(id, Date.now() + 5000);
        if (!disposed && desired.current.has(id)) {
          const detail = isAxiosError(err) ? err.response?.data?.detail : undefined;
          const text = typeof detail === 'string' ? detail : '国标点播失败，请检查设备和服务状态';
          if (errors.get(id) !== text) message.error({ key: `gb-play-${id}`, content: text });
          errors.set(id, text);
          setStreams((previous) => previous[id]
            ? { ...previous, [id]: { ...previous[id], online: false } } : previous);
        }
      } finally {
        pending.delete(id);
      }
    };
    const tick = () => {
      if (disposed) return;
      for (const [id, leaseId] of leases) {
        if (!desired.current.has(id)) {
          leases.delete(id);
          due.delete(id);
          errors.delete(id);
          release(id, leaseId);
        }
      }
      for (const id of desired.current) {
        if (Date.now() >= (due.get(id) ?? 0)) void acquire(id);
      }
    };
    reconcile.current = tick;
    const timer = window.setInterval(tick, 1000);
    tick();
    return () => {
      disposed = true;
      window.clearInterval(timer);
      for (const [id, leaseId] of leases) release(id, leaseId);
      leases.clear();
    };
  }, [setStreams]);

  useEffect(() => reconcile.current(), [key]);
}
