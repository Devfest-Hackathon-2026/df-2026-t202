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
      className="relative mx-4 mb-2.5 grid flex-none grid-cols-2 gap-0.5 rounded-xl bg-white/10 p-[3px] desk:mx-[18px]"
      role="tablist"
      aria-label={t('sheet.tabs')}
    >
      {/* One white pill that slides to the selected tab. */}
      <span
        className="absolute top-[3px] bottom-[3px] left-[3px] w-[calc(50%-4px)] rounded-lg bg-white shadow-sm transition-transform duration-300 ease-(--ease-out)"
        style={{
          transform: `translateX(${TABS.indexOf(tab) * 100}%) translateX(${TABS.indexOf(tab) * 2}px)`,
        }}
        aria-hidden="true"
      />
      {TABS.map((name) => (
        <button
          key={name}
          type="button"
          role="tab"
          id={`sheet-tab-${name}`}
          aria-selected={name === tab}
          aria-controls={`sheet-panel-${name}`}
          className={`relative h-9 rounded-lg border-0 bg-transparent text-[13px] transition-colors duration-200 ${
            name === tab ? 'text-ink font-semibold' : 'text-white/70'
          }`}
          onClick={() => onTabChange(name)}
        >
          {t(`sheet.${name}`)}
        </button>
      ))}
    </div>
  );
}
