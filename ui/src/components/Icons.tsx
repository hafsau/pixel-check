// Small inline icons (no icon library). All decorative: aria-hidden.
import type { SVGProps } from 'react';

function Svg(props: SVGProps<SVGSVGElement>) {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
      {...props}
    />
  );
}

export const IconPlay = () => (
  <Svg>
    <path d="M5 3.5v9l7-4.5-7-4.5z" fill="currentColor" stroke="none" />
  </Svg>
);
export const IconPause = () => (
  <Svg>
    <rect x="4" y="3.5" width="2.6" height="9" rx="0.6" fill="currentColor" stroke="none" />
    <rect x="9.4" y="3.5" width="2.6" height="9" rx="0.6" fill="currentColor" stroke="none" />
  </Svg>
);
export const IconStepBack = () => (
  <Svg>
    <path d="M11 4L6 8l5 4" />
  </Svg>
);
export const IconStepFwd = () => (
  <Svg>
    <path d="M5 4l5 4-5 4" />
  </Svg>
);
export const IconStart = () => (
  <Svg>
    <path d="M4 3.5v9M12 4L7 8l5 4" />
  </Svg>
);
export const IconEnd = () => (
  <Svg>
    <path d="M12 3.5v9M4 4l5 4-5 4" />
  </Svg>
);
export const IconArrowRight = () => (
  <Svg>
    <path d="M3 8h10M9 4l4 4-4 4" />
  </Svg>
);
export const IconArrowLeft = () => (
  <Svg>
    <path d="M13 8H3M7 4L3 8l4 4" />
  </Svg>
);
export const IconCopy = () => (
  <Svg>
    <rect x="5" y="5" width="8" height="8" rx="1.5" />
    <path d="M3 10.5V4a1 1 0 0 1 1-1h6.5" />
  </Svg>
);
export const IconDownload = () => (
  <Svg>
    <path d="M8 2.5v8M4.5 7L8 10.5 11.5 7M3 13.5h10" />
  </Svg>
);
export const IconSun = () => (
  <Svg>
    <circle cx="8" cy="8" r="3" />
    <path d="M8 1.5v1.5M8 13v1.5M1.5 8H3M13 8h1.5M3.4 3.4l1 1M11.6 11.6l1 1M3.4 12.6l1-1M11.6 4.4l1-1" />
  </Svg>
);
export const IconMoon = () => (
  <Svg>
    <path d="M13 9.5A5.5 5.5 0 0 1 6.5 3a5.5 5.5 0 1 0 6.5 6.5z" />
  </Svg>
);
export const IconCheck = () => (
  <Svg>
    <path d="M3 8.5l3 3 7-7" />
  </Svg>
);
export const IconAlert = () => (
  <Svg>
    <path d="M8 2l6.5 11.5h-13L8 2z" />
    <path d="M8 6.5v3M8 11.6v.1" />
  </Svg>
);
export const IconChevron = () => (
  <Svg>
    <path d="M6 4l4 4-4 4" />
  </Svg>
);
