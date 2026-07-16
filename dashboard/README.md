# Multi-Agent AI Platform - Dashboard

Real-time monitoring and management dashboard for AI workflows.

## Quick Start

```bash
npm install
npm run dev
```

Navigate to `http://localhost:3000`

## Structure

```
dashboard/
├─ app/
│  ├─ page.tsx          # Home: Workflows list
│  ├─ layout.tsx        # Navigation
│  ├─ workflows/[id]/   # Workflow detail
│  ├─ metrics/          # Analytics
│  └─ rate-limiting/    # Budget tracking
├─ components/          # Reusable components
├─ lib/                 # Utilities
└─ public/              # Static assets
```

## Pages

- **Home** (`/`) - Active workflows list
- **Workflow Detail** (`/workflows/{id}`) - Detailed view with timeline
- **Metrics** (`/metrics`) - Cost & performance analytics
- **Budget** (`/rate-limiting`) - Rate limiting & budget status

## Tech Stack

- Next.js 14 (React 18 + TypeScript)
- Tailwind CSS (dark theme)
- Recharts (data visualization)
- Lucide React (icons)

## Development

```bash
npm run dev      # Start dev server
npm run build    # Build for production
npm start        # Run production build
npm run lint     # Run linter
```

## Integration

Connected to FastAPI backend at `http://localhost:8000`

API endpoints used:
- `/api/workflows` - Get workflows
- `/api/observability/*` - Metrics
- `/api/rate-limiting/*` - Budget

## Production

```bash
npm run build
npm start
```

Dashboard will be served at configured port (default: 3000)
