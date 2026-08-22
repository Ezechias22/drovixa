import type { SVGProps } from 'react';
type Props = SVGProps<SVGSVGElement> & { size?: number };
function Icon({ size = 20, children, ...props }: Props & { children: React.ReactNode }) { return <svg aria-hidden="true" width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" {...props}>{children}</svg>; }
export function HomeIcon(p: Props) { return <Icon {...p}><path d="m3 11 9-8 9 8v9a1 1 0 0 1-1 1h-5v-7H9v7H4a1 1 0 0 1-1-1z" /></Icon>; }
export function CompassIcon(p: Props) { return <Icon {...p}><circle cx="12" cy="12" r="9" /><path d="m15.5 8.5-2 5-5 2 2-5z" /></Icon>; }
export function PlayIcon(p: Props) { return <Icon {...p}><path d="m8 5 11 7-11 7z" /></Icon>; }
export function BookmarkIcon(p: Props) { return <Icon {...p}><path d="M6 3h12v18l-6-4-6 4z" /></Icon>; }
export function UserIcon(p: Props) { return <Icon {...p}><circle cx="12" cy="8" r="4" /><path d="M4 21a8 8 0 0 1 16 0" /></Icon>; }
export function SearchIcon(p: Props) { return <Icon {...p}><circle cx="11" cy="11" r="7" /><path d="m20 20-4-4" /></Icon>; }
export function BellIcon(p: Props) { return <Icon {...p}><path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9" /><path d="M10 21h4" /></Icon>; }
export function PlusIcon(p: Props) { return <Icon {...p}><path d="M12 5v14M5 12h14" /></Icon>; }
export function CheckIcon(p: Props) { return <Icon {...p}><path d="m5 12 4 4L19 6" /></Icon>; }
