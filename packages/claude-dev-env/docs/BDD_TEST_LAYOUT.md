# BDD Test Layout and Personas

Tests are **technical documentation**: they should read clearly when you return to the codebase after time away. Organize by **behavior and functional slice**, not necessarily by mirroring production file paths, when that aids navigation.

For future readers, tests read as documentation: names, grouping, and **should** sentences should make behavior discoverable without opening production code first.

> "Many organizations apply a looser association between test classes and production classes. … Test packages or directories organized in terms of functional slices are often easier to navigate." — Smart & Molak §16.5.5

> "Writing unit tests that make good technical documentation relies more on an attitude than on using a particular tool." — Smart & Molak §16.5.5

## Describe / when / should

- Outermost **describe** names the unit under test (component, module, or feature slice).
- Inner **describe** uses **When [context]** (or equivalent grouping) for the situation.
- **it** (or **test**) names start with **should** and state one observable outcome.

Dan North (2006): naming tests as sentences keeps focus on the **next behaviour** you care about.

## Soap-opera personas

When you lack full personas, introduce **short-lived characters** with a name and role and deepen them as scenarios grow—like a serial drama adding cast over episodes (Smart & Molak §7.6.5). Embed **\[Name], the \[role]** in scenario titles or setup where the actor changes behavior.

## Example (JavaScript-style)

```javascript
describe("PaymentProcessor", () => {
  describe("When Carrie the compliance officer requests a refund for a disputed charge", () => {
    it("should deduct the refund amount from the account balance", async () => {
      const disputedChargeAmount = 150.0;
      const refundResult = await processor.refund(carrieAccountId, disputedChargeAmount);
      expect(refundResult.status).toBe("completed");
      expect(refundResult.amount).toBe(disputedChargeAmount);
    });

    it("should create an audit record with a timestamp and initiator", async () => {
      const disputedChargeAmount = 150.0;
      const auditRecord = await processor.refund(carrieAccountId, disputedChargeAmount);
      expect(auditRecord.timestamp).toBeDefined();
      expect(auditRecord.initiator).toBe("carrie_compliance");
    });
  });

  describe("When Barry the small business owner requests a refund", () => {
    it("should send a confirmation notification within business hours", async () => {
      const refundAmount = 500.0;
      const confirmation = await processor.refund(barryAccountId, refundAmount);
      expect(confirmation.notificationSent).toBe(true);
    });
  });
});
```

Adapt naming to your test runner (pytest: functions; Jest/Vitest: `it`; JUnit: `@Test` methods with `should_` names).

## File organization

- Prefer **one file per feature slice** or user journey when it keeps related behaviours together.
- Split when files grow hard to scan; keep **should** names readable in lists and IDEs.

## Checklist

- [ ] Every test name reads as a **should** sentence for one outcome
- [ ] Groups use **When**-style context where it helps navigation
- [ ] Personas appear only when they change behaviour or clarity
- [ ] Tests do not mirror production folders if that obscures behaviour
- [ ] A new reader can understand intent without opening production code first

## References

- Smart & Molak, *BDD in Action* 2e, §16.5.5 (test layout), §7.6.5 (personas)
- Dan North, "Introducing BDD" (2006)
