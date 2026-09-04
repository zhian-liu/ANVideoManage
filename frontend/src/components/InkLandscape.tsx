import type { Theme } from '../theme/colors';

interface InkLandscapeProps {
  theme: Theme;
  className?: string;
}

/** Single full-screen ink landscape backdrop shared by the application pages. */
export default function InkLandscape({ theme, className = '' }: InkLandscapeProps) {
  const classNames = ['ink-landscape', className].filter(Boolean).join(' ');

  return (
    <div className={classNames}>
      <img
        className="ink-landscape__image"
        src="/ink-landscape-lake.png"
        alt=""
        aria-hidden="true"
      />
      <div
        className="ink-landscape__wash"
        style={{
          background: `linear-gradient(180deg, ${theme.bg.base}14 0%, ${theme.bg.base}42 100%)`,
        }}
      />
    </div>
  );
}
