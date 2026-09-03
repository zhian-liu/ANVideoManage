import type { ReactNode } from 'react';

interface GridViewProps<T> {
  items: T[];
  keyOf: (item: T) => number | string;
  renderCell: (item: T) => ReactNode;
  cols?: number;
}

export default function GridView<T>({
  items,
  keyOf,
  renderCell,
  cols,
}: GridViewProps<T>) {
  if (items.length === 0) return null;
  const c = cols ?? (items.length === 1 ? 1 : items.length <= 4 ? 2 : 3);

  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: `repeat(${c}, 1fr)`,
        gap: 8,
      }}
    >
      {items.map((item) => (
        <div
          key={keyOf(item)}
          style={{
            position: 'relative',
            aspectRatio: '16 / 9',
            background: '#000',
            borderRadius: 4,
            overflow: 'hidden',
          }}
        >
          {renderCell(item)}
        </div>
      ))}
    </div>
  );
}
