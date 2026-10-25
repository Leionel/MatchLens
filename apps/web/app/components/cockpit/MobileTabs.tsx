"use client";

import React, { useRef } from "react";

export type MobileTabItem<T extends string> = {
  id: T;
  label: string;
  count?: number;
};

interface MobileTabsProps<T extends string> {
  tabs: MobileTabItem<T>[];
  active: T;
  onChange: (id: T) => void;
  label: string;
}

/**
 * Phone-only section tabs. Arrow keys move the selection and focus together,
 * matching the WAI-ARIA tabs keyboard pattern; the tablist is removed from
 * layout on wider screens, where every section is shown at once.
 */
export function MobileTabs<T extends string>({ tabs, active, onChange, label }: MobileTabsProps<T>) {
  const refs = useRef<Record<string, HTMLButtonElement | null>>({});

  const move = (event: React.KeyboardEvent<HTMLButtonElement>, index: number) => {
    let next = index;
    if (event.key === "ArrowRight") next = (index + 1) % tabs.length;
    else if (event.key === "ArrowLeft") next = (index - 1 + tabs.length) % tabs.length;
    else if (event.key === "Home") next = 0;
    else if (event.key === "End") next = tabs.length - 1;
    else return;
    event.preventDefault();
    const target = tabs[next];
    onChange(target.id);
    refs.current[target.id]?.focus();
  };

  return (
    <div className="r6-mobile-tabs" role="tablist" aria-label={label}>
      {tabs.map((tab, index) => {
        const selected = tab.id === active;
        return (
          <button
            key={tab.id}
            ref={(element) => {
              refs.current[tab.id] = element;
            }}
            type="button"
            role="tab"
            id={`r6-tab-${tab.id}`}
            aria-selected={selected}
            aria-controls={`r6-panel-${tab.id}`}
            tabIndex={selected ? 0 : -1}
            className={selected ? "active" : ""}
            onClick={() => onChange(tab.id)}
            onKeyDown={(event) => move(event, index)}
          >
            {tab.label}
            {typeof tab.count === "number" ? <span>{tab.count}</span> : null}
          </button>
        );
      })}
    </div>
  );
}
