# Cross-repository reference loop

`reference_loop.py` exercises the shipped workflow against the real sibling
`standards-ui` renderer. It uses only the Python standard library. The renderer
still needs the Node dependencies and Chromium version pinned by the UI
checkout.

Prepare the renderer once:

```bash
cd ../standards-ui
npm ci
npx playwright install chromium
cd ../standards-public
```

Run the complete reference loop:

```bash
python3 examples/workflow/reference_loop.py --ui ../standards-ui
```

The harness builds the UI packages, reads the renderer identity, and gives the
brief and identity to the public planner as separate inputs. It writes the
validated plan and selected context, then retains five browser runs:

1. the unmodified React Schedule and its passing report;
2. a seeded wrong total and its failing report plus repair packet;
3. the deterministic correction, freshly rendered, with a final pass;
4. the same unresolved defect after one ignored repair instruction;
5. the unresolved defect after the second allowed attempt, with an asserted
   `stop` action and zero repairs remaining.

Every stage keeps its HTML, embedded screenshot evidence, report or decision.
The final `summary.json` records the plan/context hashes, renderer identity,
failed rules, successful repair and honest stop path. Pass `--out PATH` to use a
new or empty directory, or `--skip-build` when the UI checkout is already built.

This is a deterministic integration proof of the workflow mechanics. It makes
no model call and does not establish comparative model performance or visual
quality.

## Reference artifact

The repository includes the current synthetic Schedule render at the two
viewports declared by the example brief. These images let designers inspect the
actual open component before running the harness. They are a review candidate,
not a designer-approved visual regression baseline. The
[reference manifest](reference/manifest.json) records their exact brief, plan,
context, artifact, renderer, browser payload, evidence, report and screenshot hashes.
The retained JSON and HTML records let the public test suite recreate the plan and
selected context, rerun the checker and verify every file offline without the sibling UI
repository or a browser. The HTML embeds Public Sans and DM Mono for reproducible rendering;
their complete SIL Open Font License 1.1 notices are in
[`reference/font-licenses/`](reference/font-licenses/).
The retained browser record includes the invariant band's geometry, colours and border
absence, plus visible-title, table, footer and numeric-column-order observations. The
public checker fails these records when a required fact is hidden, clipped, obscured or
out of place.

[Desktop reference, 1280 × 960](reference/schedule-1280x960.png) ·
[mobile reference, 390 × 844](reference/schedule-390x844.png)

![Instrument Schedule desktop reference](reference/schedule-1280x960.png)

[Retained plan](reference/schedule-plan.json) ·
[selected context](reference/schedule-context.json) ·
[static HTML](reference/schedule.html) ·
[render evidence](reference/schedule-render-evidence.json) ·
[checker report](reference/schedule-report.json)

The [long-content brief](schedule-long-brief.json) is a separate narrow-screen stress
case. It uses realistic headings, descriptions, standards, totals and notes at a 320 × 844
viewport. Its full-page reference must preserve every word, duration and fee without
horizontal overflow or mid-word breaks; column headings may occupy no more than two intact
lines.

[Long-content reference, 320 × 844 viewport](reference/schedule-long-320x844.png)

![Instrument Schedule long-content narrow reference](reference/schedule-long-320x844.png)

[Long-content plan](reference/schedule-long-plan.json) ·
[selected context](reference/schedule-long-context.json) ·
[static HTML](reference/schedule-long.html) ·
[render evidence](reference/schedule-long-render-evidence.json) ·
[checker report](reference/schedule-long-report.json)
