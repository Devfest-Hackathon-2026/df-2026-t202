'use client';

import { useT } from '@/lib/i18n';

export type SheetTab = 'chat' | 'plan';

const TABS: SheetTab[] = ['chat', 'plan'];

export function SheetTabs({
  tab,
  onTabChange,
}: {
  tab: SheetTab;
  onTabChange: (tab: SheetTab) => void;
}) {
  const t = useT();

  return (
    <div
      className="mx-4 mb-2.5 grid flex-none grid-cols-2 gap-0.5 rounded-xl bg-white/10 p-[3px] desk:mx-[18px]"
      role="tablist"
      aria-label={t('sheet.tabs')}
    >
      {TABS.map((name) => (
        <button
          key={name}
          type="button"
          role="tab"
          id={`sheet-tab-${name}`}
          aria-selected={name === tab}
          aria-controls={`sheet-panel-${name}`}
          className={
            name === tab
              ? 'text-ink h-9 rounded-lg border-0 bg-white text-[13px] font-semibold'
              : 'h-9 rounded-lg border-0 bg-transparent text-[13px] text-white/70'
          }
          onClick={() => onTabChange(name)}
        >
          {t(`sheet.${name}`)}
        </button>
      ))}
    </div>
  );
}
