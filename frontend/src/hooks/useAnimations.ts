import { useEffect, useState } from 'react';

/**
 * 数字递增动画 Hook
 * @param end 目标数字
 * @param duration 动画持续时间（毫秒）
 * @param start 起始数字
 */
export function useCountUp(end: number, duration = 1000, start = 0) {
  const [count, setCount] = useState(start);

  useEffect(() => {
    if (start === end) return;

    const startTime = Date.now();
    const range = end - start;

    const timer = setInterval(() => {
      const now = Date.now();
      const progress = Math.min((now - startTime) / duration, 1);

      // 使用 easeOutCubic 缓动函数
      const easeProgress = 1 - Math.pow(1 - progress, 3);
      const currentCount = Math.floor(start + range * easeProgress);

      setCount(currentCount);

      if (progress === 1) {
        clearInterval(timer);
        setCount(end);
      }
    }, 16); // ~60fps

    return () => clearInterval(timer);
  }, [end, duration, start]);

  return count;
}

/**
 * 视差滚动效果 Hook
 * @param speed 滚动速度倍数
 */
export function useParallax(speed = 0.5) {
  const [offset, setOffset] = useState(0);

  useEffect(() => {
    const handleScroll = () => {
      setOffset(window.pageYOffset * speed);
    };

    window.addEventListener('scroll', handleScroll);
    return () => window.removeEventListener('scroll', handleScroll);
  }, [speed]);

  return offset;
}

/**
 * 鼠标追踪效果 Hook
 */
export function useMousePosition() {
  const [position, setPosition] = useState({ x: 0, y: 0 });

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      setPosition({ x: e.clientX, y: e.clientY });
    };

    window.addEventListener('mousemove', handleMouseMove);
    return () => window.removeEventListener('mousemove', handleMouseMove);
  }, []);

  return position;
}

/**
 * 元素可见性检测 Hook（用于触发进入动画）
 */
export function useInView(ref: React.RefObject<HTMLElement>, options?: IntersectionObserverInit) {
  const [isInView, setIsInView] = useState(false);

  useEffect(() => {
    const observer = new IntersectionObserver(([entry]) => {
      if (entry.isIntersecting) {
        setIsInView(true);
      }
    }, options);

    const element = ref.current;
    if (element) {
      observer.observe(element);
    }

    return () => {
      if (element) {
        observer.unobserve(element);
      }
    };
  }, [ref, options]);

  return isInView;
}
