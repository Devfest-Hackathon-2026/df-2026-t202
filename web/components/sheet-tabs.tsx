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
    <div className="flex-none bg-transparent px-4 pb-4 desk:px-5">
      <div
        className="relative grid grid-cols-2 gap-0.5 rounded-lg bg-fill p-[3px]"
        role="tablist"
        aria-label={t('sheet.tabs')}
      >
        {/* One raised surface that slides to the selected tab. */}
        <span
          className="absolute top-[3px] bottom-[3px] left-[3px] w-[calc(50%-4px)] rounded-md bg-fill-soft shadow-sm transition-transform duration-300 ease-(--ease-out)"
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
            className={`relative h-11 rounded-md border-0 bg-transparent text-[14px] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink transition-colors duration-200 ${
              name === tab ? 'text-ink font-semibold' : 'text-muted-strong hover:text-ink'
            }`}
            onClick={() => onTabChange(name)}
          >
            {t(`sheet.${name}`)}
          </button>
        ))}
      </div>
    </div>
  );
}
