import type { MetadataRoute } from 'next';

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: 'Drovixa — Stories Today. Legends Tomorrow.',
    short_name: 'Drovixa',
    description: 'Premium cinematic short dramas, series and movies.',
    start_url: '/',
    scope: '/',
    display: 'standalone',
    orientation: 'any',
    background_color: '#08090B',
    theme_color: '#08090B',
    icons: [
      { src: '/icons/icon-192.png', sizes: '192x192', type: 'image/png' },
      { src: '/icons/icon-512.png', sizes: '512x512', type: 'image/png' },
      { src: '/icons/icon-512.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
    ],
    categories: ['entertainment', 'video'],
    shortcuts: [
      { name: 'Discover', short_name: 'Discover', url: '/discover' },
      { name: 'My List', short_name: 'My List', url: '/library' },
      { name: 'Shorts', short_name: 'Shorts', url: '/shorts' },
    ],
  };
}
