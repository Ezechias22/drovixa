import type { Metadata } from 'next';

import { CoinsExperience } from '@/features/monetization/CoinsExperience';

export const metadata: Metadata = { title: 'Coins' };

export default function CoinsPage() {
  return <CoinsExperience />;
}
