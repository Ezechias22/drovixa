import { WatchExperience } from '@/features/player/WatchExperience';
import type { PlaybackTarget } from '@/features/player/types';

type PageProps = {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ type?: string; target?: string }>;
};

export default async function WatchPage({ params, searchParams }: PageProps) {
  const [{ id }, query] = await Promise.all([params, searchParams]);
  const target: PlaybackTarget = query.target === 'movie' || query.type === 'movie' ? 'movie' : 'episode';
  return <WatchExperience id={id} target={target} />;
}
