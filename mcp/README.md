# Standards MCP server

The local server exposes installed design systems, structured contracts and an agent-native
artifact workflow over stdio. It uses Python's standard library and makes no model calls.
The client discovers the exact supported surface, supplies a brief and generated HTML,
then receives a plan, selected context, checks and bounded repair instructions. The server
does not generate, execute or automatically edit HTML.

```bash
python3 mcp/server.py --selftest
python3 mcp/server.py
```

## Connect a client

```json
{
  "mcpServers": {
    "standards": {
      "command": "python3",
      "args": ["/absolute/path/to/standards/mcp/server.py"]
    }
  }
}
```

Replace the absolute path with your checkout. Add `"--packs", "/path/to/packs"` to the
arguments to serve a different local catalogue. The workflow imports code from the
server's repository, independently of the client's working directory. Client setup
support must be verified in the actual client; a protocol self-test is not that check.

## Retrieval tools

| Tool | Purpose |
|---|---|
| `list_systems` | Discover installed systems, constraint counts and licences |
| `get_system` | Read the compact or full instruction build, or detailed reference |
| `get_tokens` | Read the token contract as JSON |
| `get_archetypes` | Read compositional moves and selection guidance as JSON |
| `select_move` | Retrieve candidates for E Evidence, S Structure, N Narrative, C Change, T Transaction or W Wayfinding |

`select_move` can return several candidates for a job. It does not resolve a complete
artifact plan. Structured contracts avoid extracting values from prose; that is an
interface property, not evidence of lower cost, fewer errors or better design. Choose
instruction context deliberately and evaluate its effect for the task and model in use.

Advertised resource files can be read under `standards://<system>/<file>`. Reads are
contained to the selected installed pack, including resolved symlinks. Nested local text
files can also be read through that URI form when present inside the pack. The server
does not serve arbitrary host paths.

## Workflow tools

| Tool | Arguments | Result |
|---|---|---|
| `get_workflow_capabilities` | none | Canonical workflow/MCP versions, six exact pairs, bindings, runtimes, tested-client receipts and unsupported surfaces |
| `plan_artifact` | `brief`, `renderer` identity objects | A validated artifact plan with selected move and source/runtime provenance |
| `assemble_context` | `plan` object | Selected source context and a manifest of what was supplied |
| `check_artifact` | `plan`, `html`; optional `render_evidence` object | Rule-linked findings, failures and explicit unknowns |
| `prepare_repair` | `plan`, `html`; optional `history` array and `render_evidence` object | A repair packet, history record and stop condition |

Every advertised tool carries MCP read-only, non-destructive, idempotent and closed-world
annotations. Clients can use those hints when applying their own approval policy; the server
does not mutate files, call a model or contact the network.

Workflow 0.2 admits six exact Instrument job/move pairs and static HTML only. See the
[canonical support manifest](../workflow/support-manifest.json),
[workflow guide](../workflow/README.md) and runnable example.
The [brief schema](../workflow/schemas/brief.schema.json),
[renderer identity schema](../workflow/schemas/renderer-identity.schema.json) and
[plan schema](../workflow/schemas/plan.schema.json) are the same contracts advertised in
`tools/list`; malformed nested fields are rejected before execution. Every workflow tool
also advertises an output schema and returns `structuredContent`. Errors are returned as
tool results, and the server can process the next valid request.

Use the tools in this order:

1. Call `get_workflow_capabilities`. Select only an exact declared job, move, content kind,
   format and binding. Treat an empty `testedClients` list as untested client compatibility.
2. Discover the installed system. Ask the UI renderer for its local identity, then submit
   that identity with a supported fixed-content brief to `plan_artifact`. Preserve the
   returned host-pinned plan.
3. Pass that plan to `assemble_context` and give the returned context to the generating
   agent. Preserve the context manifest alongside the output.
4. Pass the generated HTML and the same plan to `check_artifact`. Add externally produced
   render evidence only when it follows the documented contract.
5. Pass the HTML, plan and complete prior history to `prepare_repair`. Append the returned
   record even when the attempt is rejected. Follow its stop condition; if it allows another
   attempt, start from the returned best artifact, apply only cited safe corrections and
   submit fresh evidence. Retain every artifact and record.

Repair preparation is deterministic and makes no inference call. It cannot guarantee that
an agent will follow a repair instruction. Stale evidence, repeated artifacts or finding
sets, ties, regressions and findings requiring configuration or human judgement stop the
loop. Carry the complete returned history forward rather than resetting it to evade the
workflow's repair budget or making a rejected attempt the next repair base.

## What the results establish

Source conformance, external render observations and human design judgement are separate.
A source check does not prove the browser rendered an artifact accessibly or attractively.
Missing or schema-invalid render evidence remains unknown. Valid evidence binds the exact
plan, artifact, renderer/runtime identity and embedded PNG bytes. Caller-supplied
observations are not independent attestation; the hashes establish consistency rather
than the truth of a claimed execution.

The workflow is an inspectable implementation, not a demonstrated advantage over another
tool, model or design approach. Comparative claims require an appropriate evaluation.
See the [public roadmap](../ROADMAP.md) for the broader proposed scope.

## Licensing and private reporting

The server serves the packs installed on disk and reports their licences. It does not
enforce entitlement. Serve only the catalogue intended for the client; placing a private
pack there makes it available through the server. Instrument is CC BY 4.0; tooling is MIT.
See [LICENSE](../LICENSE) and the licence within each pack.

Do not include credentials or private client material in public reproductions. Report
vulnerabilities through the [private reporting policy](../SECURITY.md).
