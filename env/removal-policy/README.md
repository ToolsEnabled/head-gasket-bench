# Removal policy input

The three files here are the "L1" labelled removal policy for the 1,240
selected engine bodies (`cad96-removal-policy-v4`). They are the input that
`python3 -m headgasket prepare` embeds into every variant configuration:

| File | Role | SHA-256 |
|---|---|---|
| `policy.json` | parts, bindings, release actions and conditions for 1,255 bodies | `1f8c6a752db366b82ab72cf824070449a315c8ff2ecd62e8fbbec5ad13e753b6` (as sealed) |
| `removal-fixture.json` | the 162-step grouped reference removal script | `e5f920a2ce16440666a790b64876c09f504f227d4cbc61fffc7cfc8a6472dc25` (as sealed) |
| `job-checklists.json` | 626 reinstallation requirements and 100 attachment restorations | `f98311db00086a26346ce3c6b8cf4691306ae8f060e71b02720159a42c9b4b69` |

`job-checklists.json` differs from the sealed file
(`fbc5bdfee625cc84fd2ca29f0bb7970585aad10d3be1994bfb720d202ddee3dd`) in exactly
625 string values: the `basis[].sources[].path` citations were respelled from a
machine-local shared-folder path to the neutral labels
`benchmark-policy/STUDY-DESIGN-v2.md` (624) and
`benchmark-policy/CHECKPOINTS-SIGNOFF.md` (1), the same labels the published
run records carry. No requirement, identifier, rule or count changed.
`tools/l1_controls.py` pins the respelled file, writes that pin into each
configuration as `reassembly.source_raw_sha256`, and records the sealed pin in
a comment.

The policy describes discrete benchmark transitions (prepare a condition,
release an attachment, remove a group to the tray, restore). It does not
simulate motion, clearance or physical withdrawal; `physical_qualification`
is `false` throughout.

ToolsEnabled is not affiliated with or endorsed by Anthropic, OpenAI or any other AI provider.
