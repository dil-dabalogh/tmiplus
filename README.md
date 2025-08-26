# Too Much Infromation (TMI) Resource Planner

A Typer-based CLI to manage initiatives, members, PTO, weekly assignments, planning, and reporting,
with Airtable as the initial data layer and a memory adapter for tests/demos.

## Quickstart

### Install dev version

```bash
# 1) Install (dev):
# zsh requires quoting extras to avoid bracket globbing
pipx install ".[dev]"

# or standard pip + venv:
pip install -e ".[dev]"

# 2) Check CLI:
tmi --help
tmi --version

# 3) Configure Airtable environment (optional for memory adapter):
export TMI_AIRTABLE_API_KEY=your_api_key
export TMI_AIRTABLE_BASE_ID=appXXXXXXXXXXXXXX

# 4) Show config (auto-created at ~/.tmi.yml):
tmi config show

# Health checks
tmi health check
```

### Install latest release (pipx)

The command below is auto-updated on each release:

<!-- INSTALL_LATEST_START -->
```bash
# No release yet – this block will be replaced on first tagged release
```
<!-- INSTALL_LATEST_END -->

### Required DB structure

**Members**
- Name (Primary, text, unique)
- Pool (Single select): Solutioning, Feature, Operability, QA
- ContractedHours (Number, 0 decimals, default 40)
- SquadLabel (Text)
- Active (Checkbox, default checked)
- Notes (Long text)

**Initiatives**
- Name (Primary, text, unique)
- Phase (Single select): Idea & Discovery, Solutioning, Implementation
- State (Single select): Open, In progress, Blocked, Done
- Priority (Number 1..5)
- Budget (Single select): Roadmap, Run the business, Tech Refresh
- OwnerPools (Multi-select): Solutioning, Feature, Operability, QA
- RequiredBy (Date; no time)
- StartAfter (Date; no time; can be empty)
- ROM (Number; 1 decimal)
- Granular (Number; 1 decimal)
- SSOT (URL)

**PTO**
- Record (Auto number)
- MemberName (Text; must match Members.Name)
- Type (Single select): Holiday, Sick leave, Other
- WeekStart (Date; Monday of ISO week)
- WeekEnd (Date; Sunday of ISO week)

**Assignments**
- Record (Auto number)
- MemberName (Text; must match Members.Name)
- InitiativeName (Text; must match Initiatives.Name)
- WeekStart (Date; Monday of ISO week)
- WeekEnd (Date; Sunday of ISO week)

Export:
- `TMI_AIRTABLE_API_KEY` and `TMI_AIRTABLE_BASE_ID` as env vars.

### CSV Templates

See `templates/csv/*.csv`. Import/export with:
```bash
tmi members import --path ./members.csv --dryrun
tmi initiatives export --out ./initiatives.csv
```

### Planner

- Greedy:
  - Respects OwnerPools, PTO, StartAfter, one-initiative-per-member-per-week, squad all-or-none.
  - No partial completion (MVP behavior).
  - `--recreate` ignores existing (not Done) assignments in window during planning.
  - Output plan to YAML/JSON; apply via `tmi assignments apply --plan plan.yml`.

- ILP (default-installed):
  - Supports partial weekly assignments per member-week via `CapacityPW`.
  - Reduces ping-pong (member switches) and compresses initiative spans using soft penalties.
  - All ILP solver and weighting parameters are read from config at `~/.tmi.yml` under `planner.ilp`.
  - No CLI flags for ILP tuning; edit config instead and re-run.

- ILP (preference-aware):
  - New algorithm key: `--algorithm ilp-pref`
  - Maximizes utilization, respects hard dependencies and OwnerPools, and treats Preferred Squad as a soft preference.
  - Enforces finish-to-start sequencing and can optionally run an idle-fill pass to use spare capacity.
  - Tunable via `planner.ilp_pref` in the config (weights for utilization, completion, breadth, pref_squad bonus, deadlines, roadmap target, etc.).

#### ILP configuration (in `~/.tmi.yml`)

```yaml
planner:
  ilp:
    time_limit_s: 120           # Solver time limit (seconds)
    mip_gap: 0.01               # Relative MIP gap target (e.g., 1% = 0.01)
    threads: 0                  # 0 = solver default
    weights:
      complete_priority_weight: 1000.0   # Large weight to prioritize fully completing higher-priority initiatives
      early_week_bonus: 0.25             # Small bonus to prefer earlier weeks
      member_chunk_transition_penalty: 2.0   # Penalize member switching between weeks (contiguity)
      init_span_transition_penalty: 1.0      # Penalize initiative week-to-week start/stop transitions
      init_active_week_penalty: 0.25         # Penalize each active week to compress initiative span
```

### Tooling

- `ruff` + `black` + `mypy` + `pytest`
- `nox -s all` runs lint/type/tests
- GitHub Actions CI provided

## License
MIT
