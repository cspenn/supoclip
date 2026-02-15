# RULES.MD - React/TypeScript + Next.js + PocketBase Development Standards

Target: React 18+, TypeScript 5+, Next.js 14+ App Router on macOS with zsh. This document governs all code generation and modification.

---

## PART 1: FIRST PRINCIPLES

These principles take precedence over all other rules.

### P1: Fix Over Create
- Always update/fix existing React components rather than creating new ones
- **EXCEPTION**: React DevTools Profiler >5ms render time, component >200 lines, or >5 pieces of state

### P2: Reusable Testing Infrastructure
- NO one-off diagnostic components or test files; build reusable test utilities in `tests/utils/`
- Use Vitest + React Testing Library; add patterns to shared utilities

### P3: Documentation Location
- ALL documentation in `docs/` folder; component docs via JSDoc; ONLY exception: README.md at root

### P4: Never Defer Necessary Work
- Clean, performant code ALWAYS first priority; no "we'll optimize this later"
- Fix performance issues immediately; memory leaks MUST be resolved before commit

### P5: Use Agents Whenever Possible
- Agents allow separate context windows and parallel work; use for independent features

---

## PART 2: CORE STANDARDS

### 2.1 Project Structure

| Directory | Purpose |
|-----------|---------|
| `app/` | Next.js 14+ App Router |
| `components/` | React components (features/, ui/) |
| `lib/` | Utilities (engine/, stores/, utils/) |
| `types/` | TypeScript definitions |
| `config/` | Config files (config.ts, credentials.ts) |
| `tests/`, `docs/` | Test files, documentation |

### 2.2 Configuration

| Rule | Implementation |
|------|---------------|
| **No env vars** | Use config.ts for general settings |
| **Secrets** | Use credentials.ts (must be in .gitignore) |
| **Placeholders** | Provide credentials.example.ts as template |
| **Type safety** | All config validated with Zod at runtime |
| **No hardcoding** | Never hardcode URLs, keys, or magic numbers |

### 2.3 Code Quality

| Principle | Application |
|-----------|-------------|
| **DRY** | Extract common hooks, shared components |
| **SOLID** | One component = one purpose |
| **YAGNI** | No premature abstraction |

**Rules:** Max component: 200 lines; clear names; Props interface defined separately; Event handlers: `handle`/`on` prefix

### 2.4 Tooling

| Tool | Purpose |
|------|---------|
| **Next.js 14+** | Framework (App Router) |
| **TypeScript 5+** | Type safety |
| **Vitest** | Testing |
| **ESLint/Prettier** | Linting/Formatting |
| **Zustand** | State management |
| **Zod** | Runtime validation |

---

## PART 3: QUALITY GATE CHECKLIST

### Tier 1 - Gate Checks (Must Pass Before Commit)

| Tool | Command | Threshold |
|------|---------|-----------|
| **ESLint** | `eslint src/` | Zero errors (react-hooks, jsx-key rules) |
| **TypeScript** | `tsc --noEmit` | Zero errors |
| **Prettier** | `prettier --check src/` | All files formatted |
| **Vitest** | `vitest run` | 100% pass rate |

### Tier 2 - Quality Analysis

| Tool | Target |
|------|--------|
| **React DevTools Profiler** | <5ms per component |
| **Lighthouse** | >90 score |
| **Bundle analyzer** | <1MB total |

**Metrics:** Frame: 13-16.67ms avg (60 FPS); Component: <5ms; Memory: <1MB/min; Re-renders: <100/sec (Zustand selectors)

### Tier 3 - Advanced

| Tool | Purpose |
|------|---------|
| **Chrome Memory Profiler** | Memory leaks |
| **React DevTools** | Hierarchy analysis |
| **Vitest Coverage** | Test coverage |
| **Playwright** | E2E testing |
| **eslint-jsx-a11y** | Accessibility |

---

## PART 4: 8-DIMENSION QA FRAMEWORK

| Dimension | Question | React Example |
|-----------|----------|---------------|
| **Good** | What's working correctly? | Component <5ms; correct dependencies; cleanup present |
| **Bad** | What's broken? | Memory leak; 60 re-renders/sec; missing keys |
| **Missing** | What's absent? | No error boundaries; no loading states |
| **Unnecessary** | What's superfluous? | Memoization on <2ms components |
| **Fixed** | What was repaired? | Removed leak; fixed infinite re-render |
| **Newly Broken** | What now fails? | Refactor broke hook rules; stale data |
| **Silent Errors** | What's hidden? | setState on unmounted; race conditions |
| **Overengineered** | What's too complex? | Custom state when useState sufficient |

---

## PART 5: IMPLEMENTATION STANDARDS

### 5.1 React Patterns

```typescript
// Effects and Cleanup (CRITICAL) - Missing cleanup: 1 listener → 102 after 30 min; 50MB+ growth
useEffect(() => {
  const interval = setInterval(() => update(), 16);
  const unsubscribe = pb.collection('players').subscribe('*', onUpdate);
  return () => { clearInterval(interval); unsubscribe(); }; // MUST return cleanup
}, []);

// Refs vs State - useState: 70 re-renders/sec; useRef: 30 re-renders/sec (50% reduction)
const [score, setScore] = useState(0); // UI state (triggers re-render)
const gameTimeRef = useRef(0); // Non-visual (no re-render)

// Memoization - ONLY if: Render >5ms, props stable, parent re-renders frequently
const GameTile = React.memo(({ x, y }: Props) => <Tile x={x} y={y} />, (prev, next) => prev.x === next.x);
// Overhead: Component: 2KB; + React.memo: 2.3KB (+15%); 1,000 instances: 500KB wasted if no benefit
```

### 5.2 TypeScript for Games

#### Branded Types (71% Crash Reduction)
```typescript
type PlayerId = string & { readonly __brand: 'PlayerId' };
type ItemId = string & { readonly __brand: 'ItemId' };
function addItemToInventory(playerId: PlayerId, itemId: ItemId, quantity: number): void { }
// ❌ Compile error prevents ID swapping bugs
```

**Impact:** PlayZen Studios: 71% reduction in crash rates

#### Discriminated Unions
```typescript
type GameAction = { type: 'MOVE_PLAYER'; payload: { x: number; y: number } }
  | { type: 'TAKE_DAMAGE'; payload: { amount: number } };

function gameReducer(state: GameState, action: GameAction): GameState {
  switch (action.type) {
    case 'MOVE_PLAYER': return { ...state, player: { ...state.player, position: action.payload } };
    case 'TAKE_DAMAGE': return { ...state, player: { ...state.player, health: state.player.health - action.payload.amount } };
  }
}
```

#### Strict tsconfig.json
```json
{ "compilerOptions": { "strict": true, "noImplicitAny": true, "strictNullChecks": true, "noImplicitReturns": true,
  "noUncheckedIndexedAccess": true, "noUnusedLocals": true, "noUnusedParameters": true } }
```

### 5.3 State Management (Zustand - 37.8% Performance Gain)

```typescript
// ❌ BAD: Subscribes to entire store
const gameState = useGameStore();

// ✅ GOOD: Selective subscription
const health = useGameStore(s => s.player.health);
```

**Impact:** Context API: 10,000 re-renders, 3200ms TTI; Zustand (selectors): 100 re-renders, 450ms TTI (37.8% improvement)

#### High-Frequency Updates
```typescript
useEffect(() => {
  const loop = () => {
    const store = useGameStore.getState(); // Read without subscribing
    store.updatePosition(store.position.x + deltaTime, store.position.y + deltaTime);
    requestAnimationFrame(loop);
  };
  requestAnimationFrame(loop);
}, []);
```

**Pattern:** Game loop: `getState()` (no re-renders); UI: hook subscription; Result: 60 FPS, 10-30 UI re-renders/sec

### 5.4 Game Loop (requestAnimationFrame)

```typescript
useEffect(() => {
  let rafId: number, lastTime = performance.now();
  const loop = (now: number) => {
    const deltaTime = (now - lastTime) / 1000;
    lastTime = now;
    updateGame(deltaTime);
    rafId = requestAnimationFrame(loop);
  };
  rafId = requestAnimationFrame(loop);
  return () => cancelAnimationFrame(rafId);
}, []);
```

**Benefits:** Synced with repaint (60 FPS); Auto-pauses when hidden; More accurate than setInterval

### 5.5 Performance Budgets

| Budget | Target | Threshold |
|--------|--------|-----------|
| **Frame (60 FPS)** | 16.67ms total | Component >5ms → optimize; >16.67ms → dropped frame |
| **Memory** | <10KB/component, <1MB/min growth | >5MB/min = leak |
| **UI Updates** | Max 30/sec (not 60/sec) | Re-renders expensive (5-10ms); eye can't perceive >30/sec |
| **Network** | 20 Hz (every 50ms) | Decouple from game loop |

### 5.6 PocketBase Integration

```typescript
const pb = new PocketBase('https://your-pb.com');
await pb.realtime.subscribe('players/*', (e) => { console.log(e.action, e.record); });

// Optimistic updates: 1. Apply locally, 2. Send to server, 3. Rollback on error
async function updatePlayerPosition(playerId: string, newPosition: { x: number; y: number }): Promise<void> {
  useGameStore.setState(s => ({ ...s, player: { ...s.player, position: newPosition } }));
  try { await pb.collection('players').update(playerId, { position: newPosition }); }
  catch { useGameStore.setState(s => ({ ...s, player: { ...s.player, position: originalPosition } })); }
}

// Query optimization: Use expand to avoid N+1 queries (80% fewer queries; 30s → instant)
// ❌ N+1 (201 queries): for (const match of matches) match.player1 = await pb.collection('players').getOne(...)
// ✅ Expansion (1 query): const matches = await pb.collection('matches').getList(1, 100, { expand: 'player1,player2' });
```

### 5.7 Critical Anti-Patterns

| Anti-Pattern | Measured Impact | Fix |
|--------------|-----------------|-----|
| **Components in render** | **60 FPS → 5 FPS** (92% loss) | Define outside render |
| **Missing cleanup** | 1 listener → 102 after 30 min; 50MB+ growth | Return cleanup function |
| **useState for game state** | 60 re-renders/sec | Use useRef |

```typescript
// ❌ Component in render - CATASTROPHIC
const tiles = map(tile => { const C = () => <div>{tile.value}</div>; return <C key={tile.id} />; });

// ✅ Define outside
const Tile = ({ value }) => <div>{value}</div>;

// ❌ useState for loop: 60 re-renders/sec
const [position, setPosition] = useState({ x: 0, y: 0 });

// ✅ useRef for loop: 0 re-renders
const positionRef = useRef({ x: 0, y: 0 });
```

---

## PART 6: VUW METHODOLOGY

**Verifiable Units of Work** - micro-plans for disciplined debugging.

### Core Principles

1. **Extreme Granularity**: One file or one specific error per VUW
2. **Verification = Done**: Task incomplete until checklist passes
3. **Sequential Execution**: One VUW at a time; complete before next
4. **Clarity Over Conciseness**: Literal instructions, assume nothing

### VUW Template

```markdown
**VUW_ID:** [e.g., REACT-PERF-001]
**Objective:** [Why this matters]
**Files:** [List]
**Pre-Work:** git commit
**Steps:** [Literal instructions]
**Verification:**
- [ ] `npm run lint` zero errors
- [ ] `npm test` all pass
- [ ] Chrome Memory: no growth over 2 min
**Post-Work:** git commit
```

### Example VUWs

1. Fix useEffect dependency warning (ESLint exhaustive-deps; verify no infinite loop)
2. Add TypeScript types (replace `any`; define Props with branded types)
3. Implement cleanup (prevent leak; verify with Chrome Memory)
4. Replace Context with Zustand (reduce re-renders 10,000 → <100; measure with Profiler)
5. Add React.memo (reduce render 15ms → <5ms; profile before/after)

---

## React 18+ Features Reference

| Feature | Usage |
|---------|-------|
| **Automatic Batching** | Multiple state updates batched automatically |
| **Transitions** | `useTransition` for non-urgent updates |
| **Suspense** | Data fetching with `<Suspense>` boundary |
| **Server Components** | Next.js App Router default |
| **Streaming SSR** | Progressive hydration |
| **Concurrent Rendering** | Time-slicing for smoother UX |

---

## Anti-Patterns (NEVER DO)

- Components created inside render functions
- Missing useEffect cleanup functions
- useState for high-frequency game state
- Missing hook dependencies (stale closures)
- Subscribing to entire Zustand store
- Array index as key prop
- Memoization without profiling first
- setInterval instead of requestAnimationFrame
- Hardcoded API keys or secrets
- `any` type in TypeScript
