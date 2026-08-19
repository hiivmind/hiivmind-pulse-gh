# Prior art: fleet-governance UI + embedded approving agent

**Date:** 2026-08-17
**Status:** Research complete, no decision
**Companion to:** [`2026-08-17-agent-native-fleet-ui.md`](2026-08-17-agent-native-fleet-ui.md) — read that
first for the problem/proposal this evaluates prior art against.
**Method:** web research (Exa), evaluated by customer/developer need, not by technical
implementation. A near-identical technical stack (Claude Code plugin + agent-native + FastAPI
boundary) is not expected to exist and its absence is not evidence of an open need — a
Cortex/Port/OpsLevel-shaped SaaS product satisfying the same job *would* be.

## The job-to-be-done, stated as a customer would

"I run a fleet of repos/services. I can't see their state in one place. The system already
finds problems. Fixing them today means a PR review or a terminal prompt. I want to see the
problem, click approve, and have an agent do the fix — in the same screen."

Four sub-needs, each mapped to the mechanism in `2026-08-17-agent-native-fleet-ui.md` that
would satisfy it:

| Sub-need | This program's existing mechanism |
|---|---|
| Single visual view of fleet state | `poll.py` Projects v2 bronze→silver→gold pipeline; today text-only, `gh-heartbeat`-only |
| Discrepancies surfaced, not buried in YAML | `findings` (typed, severity-graded) in every `*-result.yaml` kind |
| Approve/reject as a UI action, not a PR review or terminal prompt | `proposed_actions` + the F11 apply-mode lease/fence/journal gate |
| An agent that acts on what's shown, from the same screen | agent-native `defineAction()` — one action definition, UI button + chat tool + MCP tool |

## Verdict

**This job-to-be-done is not new. It is the core pitch of the "agentic Internal Developer
Platform" category, and multiple funded vendors sell it today.** The backlog item is not
proposing an undiscovered need — it is re-solving a need three named competitors already
serve, for a differently-shaped buyer. That reframes the open question from *"should we build
this?"* to *"build vs. point at an existing IDP vs. build only the wedge those IDPs don't
cover?"* — see § Strategic fork.

## Market map

| Category | Product | Need-fit | What's missing vs. this program's need |
|---|---|---|---|
| **Agentic IDP** | **Cortex.io** — closest match | Scorecards = continuous `findings`-equivalent. Workflows with a **Manual Approval** block = the approve-gate. Embedded MCP chat answers "what are quick wins for my scorecard?" pulling the same data the dashboard shows = the agent panel. AI Impact Dashboard measures agent-driven change over time. | Assumes an existing service catalog (ownership, ontology) as onboarding cost. Vendor-hosted SQL state, not git-committed. Enterprise buyer/pricing, not a solo/small-team self-hosted tool. |
| **Agentic IDP** | **Port.io** | Self-service Actions triggerable by UI *or* AI agent through the identical governed path; per-action execution mode (`automatic` vs `approval-required`); dynamic permission policies keyed off catalog data; full audit trail; MCP server. Functionally the tightest match to `defineAction()`'s "one action, many surfaces, approval-gateable" shape. | Same catalog-onboarding and enterprise-buyer gap as Cortex. Positioned toward fully autonomous end-to-end agent workflows (e.g. incident resolution) more than a human-reviews-then-approves loop. |
| **Agentic IDP** | **OpsLevel** | Catalog-first; treats AI agents as first-class catalog components alongside services, so existing maturity scorecards/ownership/dependency rules apply to the "AI fleet" too. Fast rollout, MCP support. | Weakest of the three on the specific approve→agent-executes loop; strongest on catalog auto-discovery, not remediation. |
| **DIY IDP** | **Backstage** + `@backstage/plugin-mcp-actions-backend` | Backend plugins register typed Actions, auto-exposed as MCP tools an embedded chat can call; Scaffolder templates gated by the existing permission framework; 2026 roadmap explicitly targets "agentic scaffolder actions" with human-in-the-loop gates. | Self-hosted and free like this program, but the approval model is Backstage's general permission framework, not a purpose-built findings→approve queue UI. No scorecard/compliance layer out of the box (bring your own plugin). |
| **GitHub-native policy enforcement** | **OSSF Allstar** (+ **Scorecard** for assessment) | Continuous compliance monitoring across a repo fleet with auto-revert or issue-driven remediation — the narrow "healthcheck" half of this program's job, GitHub-native, free, no catalog to build. | No UI, no agent, no chat — remediation is "open a GitHub issue, wait for a human to fix it manually," not an approve-and-agent-executes loop. No Projects/workflow visualization at all. |
| **Autonomous coding agents** | Devin (Cognition), GitHub Copilot Agent Mode, Charlie (Charlie Labs) | Agent takes real, non-trivial GitHub actions (PRs, fixes, migrations) from a task description. | Approval happens through the *standard GitHub PR review UI*, not an app-native dashboard the agent shares state with. Zero fleet-health/scorecard/governance dimension — single-repo, task-scoped, not "here are N proposals across the fleet, review them here." |
| **The proposed framework itself** | agent-native (BuilderIO) | Confirmed real, open-source, actively templated (Clips, Plans, Design, Content, Slides, Analytics). | No known GitHub-fleet-governance app built on it — none of its official templates touch repo governance. Choosing it is still a genuinely novel application, not a reimplementation of an existing agent-native app. |

## Detail: Cortex.io, since it is the closest match

- **Scorecards** define "what good looks like" per service/repo and continuously evaluate
  against it — the direct product-market analog of `healthcheck-result.yaml` findings, just
  sold as a standing SaaS dashboard instead of a committed YAML file read by `cat`.
- **Workflows** are multi-step automations that can include a **Manual Approval** block gating
  a remediation before it runs — the direct analog of "approve this proposed_action" replacing
  a PR review or terminal confirmation. This is evidence the approval-gated-remediation UX
  pattern is proven in production, not speculative.
- **Cortex MCP + embedded chat** lets an engineer (or an agent) ask "what are quick wins for my
  AI Governance scorecard?" from inside a chat surface wired to the same context graph the
  dashboard renders — the direct analog of the proposed LLM agent panel with fleet context.
- **AI Impact Dashboard** goes further than this program's v1 scope cut (§ "Scope cut for v1"
  in the companion doc) — it measures the *effect* of agent-driven changes on DORA metrics,
  something not yet designed here.
- Customer testimonials (Skyscanner, Xero, Rapid7, VistaPrint) cite the pain points this
  program also names: fragmented visibility across tools, standards drift without a central
  scorecard, "spreadsheet culture" for tracking production readiness. Same underlying need,
  enterprise-platform-team buyer.

## Strategic fork this research surfaces

Every named IDP competitor shares two structural traits this program's target user does not
have and may not want:

1. **Catalog onboarding cost.** Scorecards mean nothing until services/repos are modeled in the
   vendor's ontology first. This program's state is already GitHub-native (Projects v2,
   branch protection, rulesets, Actions) — there is no catalog to stand up.
2. **Vendor-hosted state, enterprise buyer.** IDP state lives in the vendor's SQL database,
   priced and sold to platform-engineering leadership at orgs with many teams owning many
   services. This program's state is git-committed YAML in a repo the team already owns,
   diffable via PR, usable by a solo maintainer or small team with zero seats to buy.

That gap is the candidate wedge, not a gap in imagination: **GitHub-native, catalog-free,
self-hosted, git-committed-state fleet governance with an embedded approving agent, for teams
too small or too GitHub-centric to adopt an enterprise IDP.** Whether that wedge is worth
building — versus telling GitHub-fleet-governance prospects to just buy Cortex or Port — is
the open decision this research hands back to the brainstorming pass on
`2026-08-17-agent-native-fleet-ui.md`. It is not decided here.

## Sources

Findings above are synthesized from web search (Exa-backed), not primary-source vendor docs
read in full; treat vendor-specific claims (e.g. exact Cortex workflow block names, OpsLevel's
AI-agent-as-catalog-entity framing) as directionally accurate but re-verify against
`docs.cortex.io` / `docs.port.io` / `docs.opslevel.com` before citing in a spec or customer-
facing comparison.
