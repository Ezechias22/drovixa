import type { Metadata } from 'next';

import { PremiumExperience } from '@/features/monetization/PremiumExperience';

export const metadata: Metadata = { title: 'Premium' };

export default function PremiumPage() {
  return <PremiumExperience />;
}
