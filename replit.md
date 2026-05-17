# EEI Explorer

## Overview

EEI Explorer is a web application for looking up Ecosystem Integrity Index (EEI) values for up to 10 locations on Earth. Users enter geographic coordinates to retrieve ecosystem health metrics including functional, structural, and compositional integrity scores. The application displays both individual results per coordinate and average EEI values across all entered locations. It integrates with Google Earth Engine to access the Landler EEI public dataset.

## Recent Changes

- **Multi-location support**: Users can now enter up to 10 coordinate pairs
- **Batch API endpoint**: Added `/api/eei-batch` for querying multiple locations at once
- **Averages calculation**: Displays average EEI across all valid locations
- **CORS enabled**: API can be called from other Replit apps

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

### Hybrid Python/TypeScript Stack

The application uses a dual-language architecture:

1. **Backend (Python/Flask)**: The main API server is built with Flask (`main.py`), handling EEI data queries through Google Earth Engine integration. The Node.js server (`server/index.ts`) acts as a process spawner that launches the Python Flask application.

2. **Frontend (React/TypeScript)**: A modern React SPA using Vite for bundling, with TypeScript throughout. Located in the `client/` directory.

### Frontend Architecture

- **React 18** with TypeScript
- **Vite** as the build tool and development server
- **Wouter** for client-side routing
- **TanStack Query** for server state management and API calls
- **Tailwind CSS** for styling with CSS variables for theming
- **shadcn/ui** component library (New York style) built on Radix UI primitives

### Backend Architecture

- **Flask** serves the API endpoints for EEI data lookups
- **Google Earth Engine Python API** connects to the Landler EEI public dataset
- The Express server infrastructure exists but primarily delegates to Flask
- **Drizzle ORM** configured for PostgreSQL (schema in `shared/schema.ts`)

### Data Layer

- **PostgreSQL** database configured via `DATABASE_URL` environment variable
- **Drizzle Kit** for database migrations (output to `./migrations`)
- Schema includes validation with Zod (`drizzle-zod`)
- Currently includes user management schema and EEI request/response types

### Key Design Patterns

- **Shared Types**: Common TypeScript types in `shared/schema.ts` using Zod for validation
- **Path Aliases**: `@/` maps to client source, `@shared/` to shared code
- **Component-based UI**: Comprehensive shadcn/ui component library pre-installed
- **API Client**: Centralized fetch wrapper with error handling in `client/src/lib/queryClient.ts`

## External Dependencies

### Google Earth Engine
- **Purpose**: Provides access to the Ecosystem Integrity Index dataset
- **Asset Path**: `projects/landler-open-data/assets/eii/global/eii_global_v1`
- **Authentication**: Uses default credentials or service account via `ee-landler-open-data` project
- **Requirement**: Earth Engine authentication must be configured (`earthengine authenticate`)

### PostgreSQL Database
- **Connection**: Via `DATABASE_URL` environment variable
- **ORM**: Drizzle ORM with PostgreSQL dialect
- **Migrations**: Managed through Drizzle Kit (`npm run db:push`)

### Key NPM Dependencies
- `@tanstack/react-query`: Server state management
- `express`: HTTP server framework (v5)
- `drizzle-orm` / `drizzle-zod`: Database ORM and validation
- `wouter`: Lightweight React router
- Radix UI primitives: Accessible UI component foundations

### Python Dependencies
- `flask`: Web framework for API
- `ee` (earthengine-api): Google Earth Engine Python client