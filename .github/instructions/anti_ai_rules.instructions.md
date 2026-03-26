---
applyTo: '**'
---

# Anti-AI Design & Development Rules

These rules are ABSOLUTE. They exist to prevent the "Default AI" look and ensure high-quality, human-grade software.

## 1. The "Purple Problem" Fix (CRITICAL)

**The Problem**: AI Agents lazy-load default UI libraries (like Shadcn UI) which ship with `slate-900` and `violet-500` as default colors. This results in the "Purple AI" aesthetic.
**The Fix**:

- **NEVER** install Shadcn or any UI library without **IMMEDIATELY** overriding the `index.css` and `tailwind.config.js` with a custom color palette.
- **INTERRUPT** the installation process mentally to "Think in detail and ACT".
- **PROHIBITED COLORS**: Default `slate`, `gray`, `zinc` (unless heavily modified), and default `violet`/`purple` primary colors.
- **REQUIRED ACTION**: Before generating any component code, generate `design_guidelines.json` and apply its variables to `index.css`.

## 2. Design System Tokens > Hardcoded Values

- **NEVER** use class names like `bg-white`, `text-black`, `bg-blue-500`.
- **ALWAYS** use semantic tokens: `bg-background`, `text-foreground`, `bg-primary`.
- **REASON**: This allows global theming and dark mode support instantly.

## 3. The "Think in Detail and ACT" Protocol

When a complex task is requested (e.g., "Install Shadcn"):

1.  **STOP**. Do not just run `npx shadcn-ui@latest init`.
2.  **THINK**: "If I run this, it will bring purple defaults."
3.  **PLAN**: "I need to run the init, AND THEN immediately write to `index.css` with my custom `design_guidelines.json` palette."
4.  **ACT**: Execute the sequence.

## 4. "Anti-AI" Aesthetic Guidelines

- **Avoid**:
  - Generic 3-column feature grids with centered icons.
  - "Rocket ship" startup illustrations.
  - Boring generic text ("We help you scale...").
- **Embrace**:
  - Asymmetry and negative space.
  - Brutalist or Neo-Brutalist typography (if appropriate).
  - Micro-interactions (hover states, scale effects).
  - "Vibe-based" design (Make it feel like a specific archetype).

## 5. Development Rigor (Emergent Protocol)

- **Plan**: Always create/update a `implementation_plan.md` or `backend_contracts.md` before coding logic.
- **Mock First**: For frontend, mock ALL data first. Do not wait for backend. Create a "teaser" that works 100% visually.
- **Test**: You are responsible for testing.
  - Backend: `pytest` or `curl` checks (automated).
  - Frontend: Browser checks (screenshot tool).
- **No Hollow Shells**: Every button must do something (even if it's just a toast notification "Feature coming soon").
