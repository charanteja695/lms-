import type { SVGProps } from "react";

/** Small inline icon set (24px stroke icons), so the app ships no icon dependency. */
const paths = {
  dashboard: "M3 12l9-8 9 8M5 10v10h5v-6h4v6h5V10",
  users: "M16 19v-1a4 4 0 00-4-4H6a4 4 0 00-4 4v1M9 10a3 3 0 100-6 3 3 0 000 6zm13 9v-1a4 4 0 00-3-3.87M16 4.13a3 3 0 010 5.74",
  shield: "M12 3l8 3v6c0 5-3.5 8.5-8 9-4.5-.5-8-4-8-9V6l8-3z",
  building: "M4 21V5a2 2 0 012-2h8a2 2 0 012 2v16M16 9h2a2 2 0 012 2v10M8 7h4M8 11h4M8 15h4M3 21h18",
  download: "M12 3v12m0 0l-4-4m4 4l4-4M4 17v2a2 2 0 002 2h12a2 2 0 002-2v-2",
  upload: "M12 21V9m0 0l-4 4m4-4l4 4M4 7V5a2 2 0 012-2h12a2 2 0 012 2v2",
  plus: "M12 5v14M5 12h14",
  sparkles: "M12 3l1.8 4.7L18.5 9.5l-4.7 1.8L12 16l-1.8-4.7L5.5 9.5l4.7-1.8L12 3zM19 15l.9 2.1L22 18l-2.1.9L19 21l-.9-2.1L16 18l2.1-.9L19 15zM5 15l.6 1.4L7 17l-1.4.6L5 19l-.6-1.4L3 17l1.4-.6L5 15z",
  paperclip: "M21.44 11.05l-9.19 9.19a6 6 0 01-8.49-8.49l9.19-9.19a4 4 0 015.66 5.66l-9.2 9.19a2 2 0 01-2.83-2.83l8.49-8.48",
  search: "M11 19a8 8 0 100-16 8 8 0 000 16zm10 2l-5.2-5.2",
  filter: "M3 5h18l-7 8v6l-4-2v-4L3 5z",
  x: "M6 6l12 12M18 6L6 18",
  check: "M5 12l5 5L20 7",
  chevronLeft: "M15 18l-6-6 6-6",
  chevronRight: "M9 6l6 6-6 6",
  chevronDown: "M6 9l6 6 6-6",
  menu: "M4 6h16M4 12h16M4 18h16",
  logout: "M15 17l5-5-5-5M20 12H9M12 21H5a2 2 0 01-2-2V5a2 2 0 012-2h7",
  user: "M20 21v-1a5 5 0 00-5-5H9a5 5 0 00-5 5v1M12 11a4 4 0 100-8 4 4 0 000 8z",
  key: "M15 7a4 4 0 11-3.9 4.9L3 20v-3h3v-3h3l2.1-2.1A4 4 0 0115 7z",
  edit: "M4 20h4L19 9l-4-4L4 16v4zM13.5 6.5l4 4",
  trash: "M4 7h16M10 11v6M14 11v6M5 7l1 13a2 2 0 002 2h8a2 2 0 002-2l1-13M9 7V4h6v3",
  ban: "M12 21a9 9 0 100-18 9 9 0 000 18zM5.6 5.6l12.8 12.8",
  play: "M8 5v14l11-7L8 5z",
  refresh: "M4 4v6h6M20 20v-6h-6M5 15a8 8 0 0013.5 3M19 9A8 8 0 005.5 6",
  clock: "M12 21a9 9 0 100-18 9 9 0 000 18zm0-13v5l3 2",
  alert: "M12 9v4m0 4h.01M10.3 3.9L2 18a2 2 0 001.7 3h16.6a2 2 0 001.7-3L13.7 3.9a2 2 0 00-3.4 0z",
  info: "M12 21a9 9 0 100-18 9 9 0 000 18zm0-11v6m0-9h.01",
  more: "M12 13a1 1 0 100-2 1 1 0 000 2zm7 0a1 1 0 100-2 1 1 0 000 2zM5 13a1 1 0 100-2 1 1 0 000 2z",
  smartphone: "M7 2h10a2 2 0 012 2v16a2 2 0 01-2 2H7a2 2 0 01-2-2V4a2 2 0 012-2zm5 16h.01",
  monitor: "M3 4h18v12H3zM8 20h8M12 16v4",
  briefcase: "M3 8h18v12H3zM8 8V5a2 2 0 012-2h4a2 2 0 012 2v3M3 13h18",
  graduation: "M2 9l10-5 10 5-10 5L2 9zm4 2v5c3 2 9 2 12 0v-5",
  mail: "M3 5h18v14H3zM3 6l9 7 9-7",
  eye: "M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12zm10 3a3 3 0 100-6 3 3 0 000 6z",
  eyeOff: "M3 3l18 18M10.6 5.1A10 10 0 0122 12s-1.3 2.3-3.6 4.3M6.6 6.6C3.8 8.4 2 12 2 12s4 7 10 7a9.8 9.8 0 004.4-1M9.9 9.9a3 3 0 004.2 4.2",
  video: "M4 6h9a2 2 0 012 2v8a2 2 0 01-2 2H4a2 2 0 01-2-2V8a2 2 0 012-2zM15 10l5-3v10l-5-3",
  fileText: "M14 3H6a2 2 0 00-2 2v14a2 2 0 002 2h12a2 2 0 002-2V9zM14 3v6h6M9 13h6M9 17h6",
  fileSpreadsheet: "M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8zM14 2v6h6M8 13h8M8 17h8M12 11v8",
  clipboardCheck: "M9 4h6a1 1 0 011 1v1H8V5a1 1 0 011-1zM8 5H6a2 2 0 00-2 2v12a2 2 0 002 2h12a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 14l2 2 4-4",
  terminal: "M4 5h16a1 1 0 011 1v12a1 1 0 01-1 1H4a1 1 0 01-1-1V6a1 1 0 011-1zM7 9l3 3-3 3M12 15h5",
  helpCircle: "M12 21a9 9 0 100-18 9 9 0 000 18zM9.5 9a2.5 2.5 0 115 1c0 1.5-2.5 1.5-2.5 3.5M12 17h.01",
  layers: "M12 3l9 5-9 5-9-5 9-5zM3 13l9 5 9-5M3 17l9 5 9-5",
  map: "M9 4L3 6v14l6-2 6 2 6-2V4l-6 2-6-2zM9 4v14M15 6v14",
  archive: "M3 5h18v4H3zM5 9v10a2 2 0 002 2h10a2 2 0 002-2V9M10 13h4",
  chart: "M4 20V11M10 20V4M16 20v-7M2 20h20",
  bell: "M18 16v-5a6 6 0 10-12 0v5l-2 2h16l-2-2zM10 20a2 2 0 004 0",
  arrowUp: "M12 19V5M5 12l7-7 7 7",
  arrowDown: "M12 5v14M19 12l-7 7-7-7",
  arrowLeft: "M19 12H5m7 7l-7-7 7-7",
  "arrow-left": "M19 12H5m7 7l-7-7 7-7",
  chevronUp: "M18 15l-6-6-6 6",
  "chevron-up": "M18 15l-6-6-6 6",
  "chevron-down": "M6 9l6 6 6-6",
  "grip-vertical": "M9 5h.01M9 12h.01M9 19h.01M15 5h.01M15 12h.01M15 19h.01",
  gripVertical: "M9 5h.01M9 12h.01M9 19h.01M15 5h.01M15 12h.01M15 19h.01",
  "alert-triangle": "M12 9v4m0 4h.01M10.3 3.9L2 18a2 2 0 001.7 3h16.6a2 2 0 001.7-3L13.7 3.9a2 2 0 00-3.4 0z",
  alertTriangle: "M12 9v4m0 4h.01M10.3 3.9L2 18a2 2 0 001.7 3h16.6a2 2 0 001.7-3L13.7 3.9a2 2 0 00-3.4 0z",
  alertCircle: "M12 22a10 10 0 100-20 10 10 0 000 20zm0-14v4m0 4h.01",
  save: "M19 21H5a2 2 0 01-2-2V5a2 2 0 012-2h11l5 5v11a2 2 0 01-2 2zM17 21v-8H7v8M7 3v5h8",
  "check-circle": "M22 11.08V12a10 10 0 11-5.93-9.14M22 4L12 14.01l-3-3",
  checkCircle: "M22 11.08V12a10 10 0 11-5.93-9.14M22 4L12 14.01l-3-3",
  bold: "M6 4h8a4 4 0 014 4 4 4 0 01-4 4H6zM6 12h9a4 4 0 014 4 4 4 0 01-4 4H6z",
  italic: "M19 4h-9M14 20H5M15 4L9 20",
  list: "M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01",
  link: "M10 13a5 5 0 007.54.54l3-3a5 5 0 00-7.07-7.07l-1.72 1.71M14 11a5 5 0 00-7.54-.54l-3 3a5 5 0 007.07 7.07l1.71-1.71",
  copy: "M8 5H6a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2v-1M8 5a2 2 0 002 2h2a2 2 0 002-2M8 5a2 2 0 012-2h2a2 2 0 012 2m0 0h2a2 2 0 012 2v3",
  "refresh-cw": "M4 4v6h6M20 20v-6h-6M5 15a8 8 0 0013.5 3M19 9A8 8 0 005.5 6",
  refreshCw: "M4 4v6h6M20 20v-6h-6M5 15a8 8 0 0013.5 3M19 9A8 8 0 005.5 6",
  "arrow-right": "M5 12h14m-7-7l7 7-7 7",
  book: "M4 19.5A2.5 2.5 0 016.5 17H20M4 19.5A2.5 2.5 0 006.5 22H20V2H6.5A2.5 2.5 0 004 4.5v15z",
  award: "M12 15l-3.5 5 1.5-6L5 9.5l6-.5 2.5-5.5L16 9l6 .5-5 4.5 1.5 6z",
  grid: "M3 3h7v7H3zM14 3h7v7h-7zM14 14h7v7h-7zM3 14h7v7H3z",
  flag: "M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1zM4 22v-7",
  lock: "M19 11H5a2 2 0 00-2 2v7a2 2 0 002 2h14a2 2 0 002-2v-7a2 2 0 00-2-2zM7 11V7a5 5 0 0110 0v4",
} as const;

export type IconName = keyof typeof paths;

interface IconProps extends SVGProps<SVGSVGElement> {
  name: IconName;
  size?: number;
}

export function Icon({ name, size = 18, className, ...props }: IconProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.8}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className={className}
      {...props}
    >
      <path d={paths[name]} />
    </svg>
  );
}
