# TMI Resource Planner (prototype)

A Typer-based CLI to manage initiatives, members, PTO, weekly assignments, planning, and reporting,
with Airtable as the initial data layer and a memory adapter for tests/demos.

## Quickstart

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
```

### Airtable Structure (Manual, non-expert guide)

Create a base named **TMI Resource Planner** with **four tables**:

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

### Planner (Greedy MVP)

- Respects OwnerPools, PTO, StartAfter, one-initiative-per-member-per-week, squad all-or-none.
- No partial completion: initiative is either fully staffed within window or reported as unstaffed.
- `--recreate` ignores existing (not Done) assignments in window during planning.
- Output plan to YAML/JSON; apply via `tmi assignments apply --plan plan.yml`.

### Tooling

- `ruff` + `black` + `mypy` + `pytest`
- `nox -s all` runs lint/type/tests
- GitHub Actions CI provided

## License
MIT
