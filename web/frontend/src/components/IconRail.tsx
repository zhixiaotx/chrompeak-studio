import type { ReactNode } from "react";
import { PANEL_TITLES, type PanelKey } from "../theme";

interface Props {
  active: PanelKey;
  onChange: (k: PanelKey) => void;
}

const I = (children: ReactNode) => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7"
       strokeLinecap="round" strokeLinejoin="round">
    {children}
  </svg>
);

const ICONS: Record<PanelKey, ReactNode> = {
  algo: I(
    <>
      <line x1="4" y1="7" x2="20" y2="7" /><circle cx="9" cy="7" r="2.1" />
      <line x1="4" y1="13" x2="20" y2="13" /><circle cx="15" cy="13" r="2.1" />
      <line x1="4" y1="19" x2="20" y2="19" /><circle cx="7" cy="19" r="2.1" />
    </>
  ),
  preprocess: I(<path d="M3 5h18l-7 8.2V20l-4-2.2v-4.6z" />),
  compare: I(
    <>
      <line x1="3.5" y1="20" x2="20.5" y2="20" />
      <rect x="5" y="11" width="3.6" height="7" rx="1" />
      <rect x="10.2" y="6.5" width="3.6" height="11.5" rx="1" />
      <rect x="15.4" y="13" width="3.6" height="5" rx="1" />
    </>
  ),
  log: I(
    <>
      <path d="M6 3h8l4 4v14H6z" /><path d="M14 3v4h4" />
      <line x1="9" y1="12.5" x2="15" y2="12.5" /><line x1="9" y1="16.5" x2="15" y2="16.5" />
    </>
  ),
  about: I(
    <>
      <circle cx="12" cy="12" r="9" />
      <line x1="12" y1="11" x2="12" y2="16.5" />
      <circle cx="12" cy="7.8" r="0.9" fill="currentColor" stroke="none" />
    </>
  ),
};

const ORDER: PanelKey[] = ["algo", "preprocess", "compare", "log", "about"];

export default function IconRail({ active, onChange }: Props) {
  return (
    <nav className="rail">
      {ORDER.map((k) => (
        <button
          key={k}
          className={`rail-btn${active === k ? " on" : ""}`}
          title={PANEL_TITLES[k]}
          onClick={() => onChange(k)}
        >
          {ICONS[k]}
          <span>{PANEL_TITLES[k]}</span>
        </button>
      ))}
      <div className="rail-spacer" />
    </nav>
  );
}
