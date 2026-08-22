# Drovixa web — Phase 9

This independent Next.js application contains Drovixa's responsive public
experience: Home, Discover, Search, Shorts, details, My List, Notifications,
Profile, login/register and PWA metadata. The player authorizes every episode or
movie through the API and mounts only the returned short-lived signed Mux HLS URL.

Copy `.env.example` to `.env.local`, run `npm run web` from the repository root,
and open `http://localhost:3000`.

The production build is a standalone container and installable PWA. Its service
worker provides a static offline fallback but intentionally never caches API
responses, Mux manifests, or media segments.
