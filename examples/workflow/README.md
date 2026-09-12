# Cross-repository reference loop

`reference_loop.py` exercises workflow 0.2 against the real sibling `standards-ui`
renderer. It uses the Schedule pair as a compact end-to-end example while the same public
contracts cover all six declared moves. The Python harness makes no model calls; the UI
checkout supplies its pinned Node and Chromium dependencies.

Prepare the renderer once with Node 22 or 24 LTS:

```bash
cd ../standards-ui
npm ci
npx playwright install chromium
cd ../standards-public
```

Run the proof:

```bash
python3 examples/workflow/reference_loop.py --ui ../standards-ui
```

The harness builds the UI, reads its support-manifest-bound identity, plans from the
brief, assembles the selected agent context, then retains four browser runs:

1. the unmodified Schedule and its passing report;
2. a seeded wrong total, its failing report and the initial repair decision;
3. the deterministic correction, freshly rendered, and a complete decision;
4. the same defective bytes submitted again, which stop as an oscillation while retaining
   the accepted best artifact for rollback.

Every stage keeps its HTML, embedded screenshot evidence, report or decision. Histories
include accepted and rejected attempts. `summary.json` records the plan/context hashes,
renderer identity, failed rules, successful correction and stop-on-repeat result. Pass
`--out PATH` to use a new or empty directory, or `--skip-build` when the UI is already
built.

This proves deterministic planning, binding, checking, history and repair-stop mechanics.
It does not establish comparative model performance, visual quality or the benefit of
automated repair.

## Retained reference artifact

The repository includes the current synthetic Schedule at the two viewports declared by
the example brief. These images let designers inspect the actual open component before
running the harness. They are review candidates, not designer-approved visual regression
baselines. The [reference manifest](reference/manifest.json) binds the exact brief, plan,
context, artifact, renderer/browser payload, evidence, report and screenshot hashes.
Public tests recreate the plan and context, rerun the checker and verify every file
offline, without the UI repository or a browser.

[Desktop reference, 1280 × 960](reference/schedule-1280x960.png) ·
[mobile reference, 390 × 844](reference/schedule-390x844.png)

![Instrument Schedule desktop reference](reference/schedule-1280x960.png)

[Retained plan](reference/schedule-plan.json) ·
[selected context](reference/schedule-context.json) ·
[static HTML](reference/schedule.html) ·
[render evidence](reference/schedule-render-evidence.json) ·
[checker report](reference/schedule-report.json)

The [long-content brief](schedule-long-brief.json) is a separate 320 × 844 stress case.
Its full-page reference must preserve every word, duration and fee without horizontal
overflow or mid-word breaks; column headings may occupy no more than two intact lines.

[Long-content reference, 320 × 844 viewport](reference/schedule-long-320x844.png)

![Instrument Schedule long-content narrow reference](reference/schedule-long-320x844.png)

[Long-content plan](reference/schedule-long-plan.json) ·
[selected context](reference/schedule-long-context.json) ·
[static HTML](reference/schedule-long.html) ·
[render evidence](reference/schedule-long-render-evidence.json) ·
[checker report](reference/schedule-long-report.json)

The rendered HTML embeds Public Sans and DM Mono. Their complete SIL Open Font License
1.1 notices are retained under [`reference/font-licenses/`](reference/font-licenses/).
