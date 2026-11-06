# LMS Frontend

React 19 · TypeScript · Tailwind CSS 4 · Redux Toolkit + RTK Query · React Router 7 · Vite.
Product blueprint: [../docs/PRODUCT.md](../docs/PRODUCT.md).

## Run

```bash
npm install
cp .env.example .env    # every setting lives here; the code reads nothing else
npm run dev             # http://localhost:3000, /api is proxied to the API gateway on :8000
npm run build           # type check + production build
npx vitest run          # unit tests
```

In production the app is the `web` image: `docker build -t lms-web .` builds it with Node and serves it with nginx, which
forwards `/api` to the gateway on the same origin ([Dockerfile](Dockerfile), [nginx/](nginx)). `VITE_*` values are build
args (baked into the bundle, so never secrets); `API_UPSTREAM`, `API_MAX_BODY` and `STORAGE_ORIGIN` are read when the
container starts. The backend's compose file runs it as `web` on port 3000; see [docs/DEPLOYMENT.md](../docs/DEPLOYMENT.md).

## Structure

```
src/
├── main.tsx                 Provider → SessionRestorer → Router, Toaster
├── app/                     store.ts, hooks.ts, router.tsx (composes module routes), navigation.ts
├── core/                    no UI, no business rules
│   ├── api/                 baseApi (auth header, single shared token refresh), download, common API types
│   ├── config/  constants/  lib/ (format, query string, API error mapping)  hooks/  toast/
├── shared/                  reusable UI used by every module
│   ├── ui/                  Button, Card, DataTable, Pagination, FilterBar, Modal, ConfirmDialog, ... (import from "@/shared/ui")
│   ├── form/                TextField, SelectField, PasswordField, FormSection, ... (import from "@/shared/form")
│   ├── layout/              AppLayout, AuthLayout, AuthCard, Brand
│   ├── routing/             page() + lazyNamed() for lazy-loaded screens
│   └── pages/               NotFoundPage
└── modules/                 one folder per management (see src/modules/README.md)
    ├── user-management/     auth · account · users · admins · institutions · employers · audit-logs · downloads · common
    ├── dashboard/
    └── catalog/ learning/ assessments/ ...   planned
```

## Principles

- **The backend owns the rules.** The frontend makes API calls and renders UI. What a screen shows comes from the server:
  - `allowed_actions` on each record decides the buttons and menu items;
  - `GET /users/me/permissions` decides the menu sections, list filters and create rights;
  - `GET /users/form-options` describes the create/edit user form: roles, sections, required fields, defaults.
  Field errors from the API are shown on the matching inputs.
- **Only what the action needs is requested.** Lists keep filters in the URL and fetch once per change. Searches are
  debounced. Edits send only changed fields. Polling runs only while a background job is still running.
- **Session security.** The access token lives in memory; the refresh token is an httpOnly, SameSite=Strict cookie the
  page cannot read (the API sets it when the client sends `X-Session-Transport: cookie`). One shared refresh call runs
  per 401, because the backend treats a reused refresh token as theft. The API cache is cleared on sign-out.
- **Small files, one job each.** Pages, columns, filters, detail cards and form sections are separate files; anything
  generic belongs in `shared/`.

## Verified

`npx vitest run` covers the request-body mapping. A browser run (Edge via playwright-core) walks the whole flow:
sign-in, permission-driven navigation, admin responsibilities, institutions, institution heads, students without email
with one-time temporary passwords, filters, audit log, employers and recruiters, background import, cookie sessions
surviving a reload, and navigation on a phone-sized screen.
