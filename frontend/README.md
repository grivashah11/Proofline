# Proofline frontend

This directory contains the React, Vite and TypeScript application. For the full product overview, architecture, Supabase setup, environment variables, judge quick start and test commands, see the repository-root [`README.md`](../README.md).

## Run locally

From this directory:

```bash
cp .env.example .env.local
npm ci
npm run dev
```

Edit `.env.local` with the URL of your local backend and the Supabase project URL and publishable key. Do not put Supabase secret/service-role keys in any `VITE_` variable.

## Validate before deployment

```bash
npm run lint
npm run build
```
