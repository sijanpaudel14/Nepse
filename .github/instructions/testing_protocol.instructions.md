---
applyTo: '**'
---

# Testing Protocol: The Quality Gate

This protocol defines the rigorous testing standards required for all Emergent projects. It is the "Source of Truth" for Phase 3 (Unit), Phase 4 (Integration/System), and Phase 5 (Release) testing.

**Constraint**: You must NOT proceed to the next phase until the current phase's tests pass.

## 1. Unit Testing (The Logic Check)

**Goal**: Verify individual components and functions work in isolation.

### Backend (FastAPI/Python)

- **Tool**: `pytest`
- **Location**: `/backend/tests/`
- **Coverage**:
  - All API endpoints (happy path & error cases).
  - Database CRUD operations.
  - Complex business logic functions.
- **Rules**:
  - Mock external services (DB, 3rd party APIs).
  - **Recursion Rule**: If a test fails, fix the code, then re-run. Do NOT ask the user.

### Frontend (Next.js/React)

- **Tool**: `jest` or `vitest` (if configured), otherwise manual component verification.
- **Focus**:
  - Utility functions (e.g., data formatters).
  - Critical UI components render without crashing.

## 2. Integration Testing (The Wiring Check)

**Goal**: Verify that different parts of the system talk to each other correctly.

- **Scope**:
  - Frontend <-> Backend API communication.
  - Backend <-> Database persistence.
- **Procedure**:
  1.  **API Verification**: Use `curl` or a script to hit running endpoints.
  2.  **Data Flow**: Create an item in Frontend -> Verify it appears in Backend DB.
  3.  **Error Handling**: Trigger a 400/500 error from Backend -> Verify Frontend displays a user-friendly toast/alert (NOT a raw stack trace).

## 3. System Testing (The User Flow)

**Goal**: Validate complete end-to-end user scenarios.

- **Scenarios**:
  - **Onboarding**: Sign up -> Login -> Profile Setup.
  - **Core Loop**: The main value prop (e.g., "Create Workout" -> "Log Set" -> "View Stats").
  - **Edge Cases**: Network failure, invalid inputs, empty states.
- **Security Check**:
  - Verify Input Validation (try sending bad JSON).
  - Verify Auth Protection (try accessing private route without token).
- **Visual Verification**:
  - Check for "Layout Shift" during loading.
  - Verify responsive design (Mobile vs Desktop).

## 4. Anti-AI & Polish Audit (The "Lovable" Check)

**Goal**: Ensure the app feels human-crafted, not auto-generated.

- **Visuals**:
  - No default "shadcn" or "tailwind" look. Custom colors/fonts must be applied.
  - No "Lorem Ipsum" text. Use realistic mock data.
  - No "Rocket Ship" or generic "AI" illustrations.
- **UX**:
  - Loading states must be skeletons or spinners, not blank screens.
  - Buttons must have hover/active states.

## 5. Deployment Verification

**Goal**: Ensure the build is production-ready.

- **Build**: Run `npm run build` (Frontend). Must pass with NO linting errors.
- **Health**: `/api/health` must return 200 OK.
- **Security**: No exposed secrets in client-side bundles.
