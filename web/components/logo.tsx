import Image from 'next/image';
import Link from 'next/link';

export function Logo() {
  return (
    <Link className="flex items-center gap-2.5" href="/" aria-label="Drovixa Home">
      <Image
        src="/icons/icon-192.png"
        alt=""
        width={36}
        height={36}
        priority
        className="h-9 w-9 rounded-xl object-cover"
      />
      <span className="text-lg font-black tracking-[.16em]">DROVIXA</span>
    </Link>
  );
}
