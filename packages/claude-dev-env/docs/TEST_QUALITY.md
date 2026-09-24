# Test Quality Reference

> Load this file when writing tests, reviewing test code, or setting up test infrastructure.

## Test Infrastructure Anti-Patterns

Test helpers drift toward over-engineering faster than production code. Keep
each helper in one file, as plain functions with the fewest abstractions the
current tests use. Add a cache class, a multi-file package, or an abstraction
only when a current test needs it. A junior developer reads the helper on the
first pass.

## Delete Useless Tests

**Tests must add value.** Delete these types of tests:

### Tests to delete

**Function existence** - "Testing that the function exists doesn't add value. If the function doesn't exist, the code will not run."
- Bad: `test_public_api_exports_download_function()` only verified `callable(func)`
- Action: delete

**Constant values** - "It's silly to test that constant values have not changed."
- Bad: `assert CACHE_DIR == "cache"`
- Action: delete

**Duplicate coverage** - "Isn't this test case the same as test_X?"
- Action: delete the redundant test

## Missing dependencies fail the test

"The tests should fail if they can't run. Missing system dependencies should make the test fail."

- Leave `@skip_if_missing_dependency` and other skip decorators out of test files. The code-rules lint flags each one.
- A missing dependency fails the test with a clear error, which prompts the install.

## Core Testing Principles

- **Behavior-driven** - Verify expected behavior, not implementation
- **Test through public API** - Never examine internals
- **100% coverage via business behavior** - Not implementation coverage
- **No 1:1 mapping** - Test files test behavior, not individual implementation files
- **Tests document behavior** - Tests are the spec

## React Testing Patterns

### Patterns

**Test behavior, not implementation** - What user sees/does, not internal state
- Bad: `expect(component.state.isOpen).toBe(true)`
- Good: `expect(screen.getByRole('dialog')).toBeVisible()`

**Use Testing Library queries correctly** - Priority order:
1. `getByRole` (best)
2. `getByLabelText`
3. `getByText`
4. `getByTestId` (last resort)

- Bad: `getByTestId('submit-button')` as first choice
- Good: `getByRole('button', { name: /submit/i })`

**Test user interactions**
- Use `userEvent` over `fireEvent` (more realistic)
- `await userEvent.click(button)` then assert result

### Anti-patterns

**Snapshot test everything** - Only for stable, visual components
- Snapshots break on any change, creating noise
- Reserve for design system components, icons

**Mock too much** - Prefer integration tests
- Bad: Mock every hook and function
- Good: Render with unmocked hooks, mock only API calls

**Test implementation details** - Test what user experiences
- Bad: Assert on state values, hook return values
- Good: Assert on rendered output, user-visible behavior

**Forget async handling** - Use waitFor, findBy queries
- Bad: Expect immediately after async action
- Good: `await waitFor(() => expect(...))` or `await screen.findByText(...)`

## Test File Organization

- **Use React Testing Library** - Not Enzyme
- **Query by accessibility** - Role, label, text (not test-id as first choice)
- **Test user flows** - Render, interact, assert on visible changes
- **Mock API boundaries** - Not internal functions
- **Colocate tests** - `Component.test.tsx` next to `Component.tsx`
