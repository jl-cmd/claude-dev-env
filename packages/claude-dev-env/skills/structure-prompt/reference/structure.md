# Structural ordering

The optimized prompt presents blocks in this fixed sequence:

1. Mission block
2. Metadata block
3. Framework block
4. Questions block
5. Output spec block
6. Data body block

## Procedure

1. Extract each tagged block from the input. The gap-report region (prior-run `> Gap:` lines or `<!-- gap-report:` comment blocks) is excluded from block ordering — it is kept at the end during classification and reordering, then deterministically replaced during emission per [`output-contract.md`](output-contract.md).
2. Concatenate the blocks in the sequence above.
3. Preserve every byte of the inputs that [`output-contract.md`](output-contract.md) lists under "Preservation invariants" exactly as supplied.

## Multiple data bodies

When the input contains multiple data body blocks (e.g., several file diffs), group them as a contiguous final section in their original relative order.

## Atomicity

The framework block stays whole. The data body section sits as one contiguous region at the end.

## Disposition reporting

Every outcome emits an action note via the mechanism that [`output-contract.md`](output-contract.md) defines. When blocks were reordered: `> Gap: Blocks reordered to canonical sequence (mission → metadata → framework → questions → output spec → data body).` When the input already follows canonical ordering and no reorder is needed: `> Gap: Structural ordering verified — input already in canonical sequence.` Silent omission is forbidden — see the [no silent action](output-contract.md#disposition-invariants) invariant.
