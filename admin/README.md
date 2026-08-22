# Drovixa Admin

Independent Next.js administrative dashboard for Drovixa. It runs on port
`3001` locally and uses an authenticated same-origin proxy so access and refresh
tokens stay in secure HttpOnly cookies.

```bash
npm run admin
```

The default local API is `http://localhost:8000/api/v1`. Copy `.env.example`
to `.env.local` only when you need to override it.
