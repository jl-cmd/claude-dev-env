# React Patterns Reference

> Load this file when working with React components, state management, hooks, or testing.

## Component Patterns

**NEVER:**

- **Create wrapper components for single use** - Use the component directly
  - Example: `<ButtonWrapper><Button /></ButtonWrapper>` when Button is only used once
  - Ask: "Is this wrapper adding any value?"

- **Put page-specific logic in shared components** - Keep shared components pure
  - Example: `if (pathname === '/home')` inside a shared Header component
  - Shared components should be context-agnostic

- **Use class components for new code** - Always use functional components with hooks
  - Exception: Error boundaries still require class components (React limitation)

- **Create HOCs when hooks work** - Prefer custom hooks over HOCs
  - Example: `withAuth(Component)` -> `useAuth()` hook
  - HOCs add wrapper layers; hooks are composable

- **Prop drill more than 2 levels** - Use Context or state management
  - Example: `<Parent data={x}><Child data={x}><GrandChild data={x} /></Child></Parent>`
  - Solution: Create context or lift state appropriately

## State Management Patterns

**NEVER:**

- **Store derived state** - Calculate on render
  - Bad: `const [fullName, setFullName] = useState(first + ' ' + last)`
  - Good: `const fullName = first + ' ' + last`

- **Mutate state directly** - Always create new references
  - Bad: `items.push(newItem); setItems(items)`
  - Good: `setItems([...items, newItem])`

- **Use useState for complex state logic** - Use useReducer
  - When: Multiple sub-values, next state depends on previous, complex update logic
  - Example: Form with many fields, shopping cart, multi-step wizard

- **Create global state for local concerns** - Colocate state
  - If only one component uses the state, keep it in that component
  - Lift state only when siblings need to share

- **Forget to memoize expensive calculations** - Use useMemo
  - Bad: `const sorted = items.sort((a, b) => ...)` on every render
  - Good: `const sorted = useMemo(() => items.sort(...), [items])`

## Hooks Patterns

**NEVER:**

- **Call hooks conditionally** - Hooks must be at top level
  - Bad: `if (condition) { const [x, setX] = useState() }`
  - Good: Always call hooks, use condition inside

- **Create effects without cleanup** - Return cleanup function when needed
  - Subscriptions, timers, event listeners MUST be cleaned up
  - Bad: `useEffect(() => { window.addEventListener(...) }, [])`
  - Good: `useEffect(() => { window.addEventListener(...); return () => window.removeEventListener(...) }, [])`

- **Use empty dependency arrays incorrectly** - Include all dependencies
  - Bad: `useEffect(() => { fetchData(userId) }, [])` (missing userId)
  - Good: `useEffect(() => { fetchData(userId) }, [userId])`
  - Use ESLint exhaustive-deps rule

- **Create new functions in render without useCallback** - Memoize callbacks passed to children
  - Bad: `<Child onClick={() => handleClick(id)} />`
  - Good: `const handleChildClick = useCallback(() => handleClick(id), [id])`

- **Overuse useMemo/useCallback** - Only optimize when needed
  - Memoization has cost; don't wrap everything
  - Profile first, then optimize specific bottlenecks

## Component Organization

**File structure:**
```
components/
  ComponentName/
    ComponentName.tsx      # Component logic
    ComponentName.test.tsx # Tests (colocated)
    index.ts               # Public export
```

**NEVER:**

- **Mix business logic with UI** - Separate concerns
  - Custom hooks for business logic: `useTaskManager()`
  - Components for UI: `<TaskList tasks={tasks} />`

- **Create god components** - Split into focused components
  - If component > 200 lines, likely doing too much
  - Extract sub-components or custom hooks

- **Export internal components** - Only export what's needed
  - Internal helpers stay private to the component folder
  - Only `index.ts` defines the public API

## Code Standards

- **Complete type annotations** - All props, state, and return types defined
- **No `any` types** - Use generics, union types, or `unknown` with type guards
- **No `@ts-ignore` or `@ts-expect-error`** without clear justification
- **Functional components only** - No class components (except error boundaries)
- **Custom hooks for logic** - Separate business logic from UI
- **Props interfaces** - Define explicit Props type for every component
- **Immutable updates** - Never mutate state or props
- **Small components** - Target 50-100 lines, max 200 lines
- **Max 2 nesting levels** - Extract sub-components
- **No inline styles** - Use CSS modules, styled-components, or Tailwind

## Testing Patterns

- **Use React Testing Library** - Not Enzyme
- **Query by accessibility** - Role, label, text (not test-id as first choice)
- **Test user flows** - Render, interact, assert on visible changes
- **Mock API boundaries** - Not internal functions
- **Colocate tests** - `Component.test.tsx` next to `Component.tsx`

**Testing anti-patterns:**

- **Snapshot test everything** - Only for stable, visual components
- **Mock too much** - Prefer integration tests
- **Test implementation details** - Test what user experiences
- **Forget async handling** - Use waitFor, findBy queries

## Example: God Component Refactoring

**Bad:**
```tsx
function TaskDashboard() {
  const [tasks, setTasks] = useState([]);
  const [filter, setFilter] = useState('all');
  const [sortBy, setSortBy] = useState('date');
  // ... 200 more lines of logic
  return (
    <div>{/* 150 lines of JSX */}</div>
  );
}
```

**Good:**
```tsx
function TaskDashboard() {
  const { tasks, filter, sortBy, actions } = useTaskManager();
  return (
    <div>
      <TaskFilters filter={filter} onFilterChange={actions.setFilter} />
      <TaskList tasks={tasks} sortBy={sortBy} />
    </div>
  );
}

function useTaskManager() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [filter, setFilter] = useState<Filter>('all');
  // ... focused logic
  return { tasks, filter, sortBy, actions };
}
```

## Example: Derived State

**Bad:**
```tsx
const [items, setItems] = useState<Item[]>([]);
const [filteredItems, setFilteredItems] = useState<Item[]>([]);

useEffect(() => {
  setFilteredItems(items.filter(i => i.active));
}, [items]);
```

**Good:**
```tsx
const [items, setItems] = useState<Item[]>([]);
const filteredItems = useMemo(
  () => items.filter(i => i.active),
  [items]
);
```
