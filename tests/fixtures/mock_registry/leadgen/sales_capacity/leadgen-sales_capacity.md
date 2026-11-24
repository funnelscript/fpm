# FunnelScript Sub-Task Prompt: Build Flagship Package `leadgen/sales_capacity`

You are the Senior Marketing Systems Engineer working on the **FunnelScript** repository.
Your sub-task is to design, implement, and verify the second production-grade `fpm` package: **`leadgen/sales_capacity`**.

This package models high-ticket lead-generation businesses (Real Estate, Clinics, B2B Services, Agencies) where paid acquisition feeds directly into a human sales team with finite daily capacity. Its core purpose is to model the intersection of **Promotion, People, Process, and Price**—exposing the operational bottleneck spreadsheets miss: doubling ad spend when a sales team is already near capacity causes lead queues to overflow, stretches `speed_to_lead` from minutes to hours, collapses contact and close rates, and spikes Effective CAC even while ad-platform CPL looks healthy.

---

## 1. Non-Negotiable Constraints

1. **Preserve Existing Documentation:** Do NOT modify, overwrite, or delete `AGENTS.md`, `EXECUTION_RULES.md`, or any roadmap `.md` files.
2. **Grammar, Module & Baseline Fidelity First:** Before writing any `.fnls` code, inspect:
   - `src/funnelscript/stdlib/marketing/lead_response.fnls` and `examples/marketing_lead_response.fnls` (existing baseline logic to extend, not duplicate)
   - `docs/fpm.md` and `packages/ecommerce/d2c_scale/` (match exact manifest format, naming conventions, and `fpm` import resolution already established)
   - `src/funnelscript/parser.py`, `src/funnelscript/compiler/world_ast.py`, and `src/funnelscript/compiler/linter.py`
   - `src/funnelscript/stdlib/marketing/` (`metrics.py`, `ledger.py`, `provenance.py`, `audit.py`, `commit.py`)
   - Do NOT invent unsupported `.fnls` syntax. Every `.fnls` file MUST parse, lint, and execute cleanly through the Python runtime (`src/funnelscript/`).
3. **Single Source of Truth:** All simulation logic runs strictly in the Python DEVS runtime (`src/funnelscript/runtime/`). Do NOT touch `apps/web/src/lib/simulator.ts`.
4. **Zero Hardcoded Business Constants:** Every rate, capacity cap, salary, commission, decay half-life, onboarding ramp period, and invoice collection lag MUST be exposed as typed, bounded parameters with sensible defaults.
5. **Strict Financial & Dimensional Discipline:**
   - All cash flows (daily ad spend, fixed rep payroll, hiring/onboarding costs, variable sales commissions, collected deal revenue) MUST reconcile through `ledger.py` with zero float drift.
   - Respect dimensional unit consistency (Currency, Count, Rate, Duration, Ratio).
   - Use deterministic keyed RNG only for stochastic lead arrivals, contact outcomes, and sales cycle durations.

---

## 2. Target Package Architecture

Create the package under `packages/leadgen/sales_capacity/` (matching the exact `fpm` directory convention used by `ecommerce/d2c_scale`) with the following modular structure:

1. **Package Manifest (`fpm.toml` or `manifest.json` per `docs/fpm.md`)**
   - Package ID: `leadgen/sales_capacity`, version `0.1.0`.
   - Declares exported modules, required FunnelScript version, input parameter schema (types, units, min/max bounds, defaults), and standard output metrics.

2. **Acquisition Module (`acquisition.fnls`)**
   - Models multi-channel daily paid spend (e.g., Meta Lead Forms, Google Search, LinkedIn) with immediate daily ad spend cash outflow.
   - Applies **Adstock** carryover and **Hill** saturation so scaling daily spend increases marginal CPL non-linearly.
   - Emits typed lead-arrival events into the sales queue with channel-specific baseline qualification intent.

3. **Queue & Speed-to-Lead SLA Module (`queue_and_sla.fnls`)**
   - Models finite sales team bandwidth: `active_reps`, `max_leads_per_rep_per_day`, and `baseline_response_minutes`.
   - Tracks daily incoming lead load vs. available rep handling capacity; excess leads spill into an explicit backlog queue carried into subsequent ticks.
   - Computes effective `speed_to_lead_minutes` from queue depth and team throughput.
   - Extends `lead_response.fnls` decay logic: applies a response-time decay curve parameterized by `lead_decay_half_life_minutes` so delayed leads experience sharp, realistic drops in `contact_rate` and `show_rate`.

4. **Pipeline & Hiring Lever Module (`pipeline_and_hiring.fnls`)**
   - Models multi-stage conversion: `Lead -> Contacted -> Qualified Appointment -> Closed Won / Lost` with bounded sales-cycle delay (`sales_cycle_days`).
   - Supports an explicit operational decision lever for capacity expansion: `planned_new_hires`, `hire_start_day`, `onboarding_ramp_days`, and `ramp_productivity_rate` (new reps incur payroll immediately upon hire while ramping from partial to full lead-handling capacity).

5. **Unit Economics & Treasury Module (`economics.fnls`)**
   - Integrates with `ledger.py` and `provenance.py` to separate booked deal value from collected cash (`invoice_collection_days`).
   - Records daily ad spend, pro-rated/periodic fixed rep payroll (`monthly_rep_salary`), one-time hiring cost (`hiring_cost_per_rep`), and variable commission (`sales_commission_rate`) triggered on closed/collected deals.
   - Tracks daily **Ad Platform CPL**, **Queue Backlog Depth**, **Average Speed-to-Lead (minutes)**, **Capacity Utilization (%)**, **Effective Close Rate**, **Effective CAC**, **Settled Cash Balance**, and **Net Contribution Margin**.

6. **Package Entry Point (`index.fnls`)**
   - Composes `acquisition.fnls`, `queue_and_sla.fnls`, `pipeline_and_hiring.fnls`, and `economics.fnls` cleanly and exposes the public exports.

7. **Package Documentation (`README.md`)**
   - Parameter reference table (name, unit, default, valid range, operational meaning).
   - Clear explanation of the capacity-decay feedback loop and hiring ramp tradeoff.
   - Minimal 15-line usage snippet.

---

## 3. Concrete Stress-Test Example

Create `examples/sales_capacity_stress.fnls` (target: 15–30 lines):
- Imports `leadgen/sales_capacity`.
- Configures a realistic high-ticket B2B/Real Estate/Clinic sales desk (e.g., 4 reps, max 12 leads/rep/day, 15-minute baseline SLA, 45-minute response decay half-life, 14-day sales cycle) attempting to **2.5x daily ad spend** over 30 days without adding headcount.
- Must clearly surface in simulation telemetry:
  - Ad-platform CPL increases only modestly.
  - Queue backlog overflows early in the month, pushing average `speed_to_lead_minutes` from minutes into hours.
  - Contact and close rates collapse under queue congestion, causing **Effective CAC** to spike sharply and **Net Margin** to turn negative despite high lead volume.

---

## 4. Verification & Test Suite

Create `tests/test_pkg_leadgen_sales_capacity.py` covering:
1. **Parse & Lint Cleanliness:** All `.fnls` files inside `leadgen/sales_capacity` and `examples/sales_capacity_stress.fnls` compile and pass `linter.py` with zero errors.
2. **Deterministic Replay:** Running `examples/sales_capacity_stress.fnls` twice with the same seed produces byte-for-byte identical telemetry and ledger hashes.
3. **Double-Entry Conservation:** Total debits equal total credits at every tick; `Starting Cash + Collected Deal Inflows - (Ad Spend + Payroll + Hiring Costs + Commissions) == Ending Settled Cash` with zero rounding drift.
4. **Monotonic Business Invariants (Sensitivity Checks):**
   - When the team is saturated, increasing `active_reps` strictly decreases `avg_speed_to_lead_minutes` and increases total closed deals.
   - Decreasing `lead_decay_half_life_minutes` (faster lead cooling) strictly lowers or equals total closed deals when backlog > 0.
   - Keeping daily lead arrivals below total team capacity maintains zero persistent backlog and keeps `speed_to_lead_minutes` at `baseline_response_minutes`.
   - Adding `planned_new_hires` with `onboarding_ramp_days > 0` increases payroll immediately while capacity relief lags until ramp completes.
5. **Parameter Bounds Validation:** Invalid inputs (e.g., `active_reps <= 0`, `max_leads_per_rep_per_day <= 0`, `lead_decay_half_life_minutes <= 0`, `sales_commission_rate = 1.2`) are rejected cleanly with clear diagnostic messages.

---

## 5. Execution Protocol & Exit Gate

1. **Inspect First:** Read the files listed in Section 1.2 and output a concise 5-bullet plan confirming how `leadgen/sales_capacity` extends `lead_response.fnls` and aligns with `ecommerce/d2c_scale`.
2. **Implement:** Build the package, stress-test example, and verification suite.
3. **Verify:** Run:
   - `pytest tests/test_pkg_leadgen_sales_capacity.py`
   - Full regression suite (`pytest`)
   - Linter (`ruff check .`)
   - Execute `examples/sales_capacity_stress.fnls` via `funnelscript` CLI and print the key summary metrics (Blended CPL, Peak Queue Backlog, Avg Speed-to-Lead, Capacity Utilization %, Effective Close Rate, Effective CAC, Net Contribution Margin, Ending Settled Cash, Ledger Audit Status).
4. **Report:** Output a concise completion summary listing created/modified files, test counts, and the CLI stress-test output. Stop and wait for review.