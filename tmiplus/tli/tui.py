from __future__ import annotations

from collections.abc import Iterable
from datetime import date

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal
from textual.reactive import reactive
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    TabPane,
    Tabs,
)

from tmiplus.core.services.csv_io import (
    read_assignments_csv,
    read_initiatives_csv,
    read_members_csv,
    read_pto_csv,
    write_assignments_csv,
    write_initiatives_csv,
    write_members_csv,
    write_pto_csv,
)
from tmiplus.core.services.planner_greedy import (
    PlanResult as GreedyPlanResult,
)
from tmiplus.core.services.planner_greedy import (
    plan_greedy,
)
from tmiplus.core.services.planner_ilp import (
    PlanResult as ILPPlanResult,
)
from tmiplus.core.services.planner_ilp import (
    plan_ilp,
)
from tmiplus.core.services.reports import (
    budget_distribution,
)
from tmiplus.core.util.dates import (
    parse_date,
    week_end_from_start_str,
)
from tmiplus.tli.context import get_adapter


def _fill_table(
    table: DataTable, columns: list[str], rows: Iterable[Iterable[object]]
) -> None:
    table.clear(columns=True)
    for c in columns:
        table.add_column(c)
    for r in rows:
        table.add_row(*[str(x) for x in r])


class TmiTui(App):
    CSS = """
    Screen { overflow: auto; }
    #toolbar { dock: top; }
    #content { dock: top; height: 1fr; }
    """

    show_tooltip = reactive("")

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="toolbar"):
            yield Button("Refresh", id="refresh")
            yield Button("Export CSV", id="export")
            yield Button("Import CSV", id="import")
            yield Input(placeholder="Date from (YYYY-MM-DD)", id="dfrom")
            yield Input(placeholder="Date to (YYYY-MM-DD)", id="dto")
            yield Button("Plan (Greedy)", id="plan_greedy")
            yield Button("Plan (ILP)", id="plan_ilp")
        with Container(id="content"):
            with Tabs():
                yield TabPane(Label("Members"), id="tab_members")
                yield TabPane(Label("Initiatives"), id="tab_inits")
                yield TabPane(Label("Assignments"), id="tab_assigns")
                yield TabPane(Label("PTO"), id="tab_pto")
                yield TabPane(Label("Reports"), id="tab_reports")
        yield Footer()

    def on_mount(self) -> None:
        self.adapter = get_adapter()
        # Tables
        self.members_table = DataTable()
        self.inits_table = DataTable()
        self.assigns_table = DataTable()
        self.pto_table = DataTable()
        self.reports_table = DataTable()
        # Insert tables into panes
        self.query_one("#tab_members").mount(self.members_table)
        self.query_one("#tab_inits").mount(self.inits_table)
        self.query_one("#tab_assigns").mount(self.assigns_table)
        self.query_one("#tab_pto").mount(self.pto_table)
        self.query_one("#tab_reports").mount(self.reports_table)
        self.refresh_all()

    def refresh_all(self) -> None:
        # Members
        ms = self.adapter.list_members()
        _fill_table(
            self.members_table,
            ["Name", "Pool", "Hours", "Squad", "Active"],
            (
                (
                    m.name,
                    m.pool.value,
                    m.contracted_hours,
                    m.squad_label or "",
                    "Y" if m.active else "N",
                )
                for m in ms
            ),
        )
        # Initiatives
        inits = self.adapter.list_initiatives()
        _fill_table(
            self.inits_table,
            ["Name", "Phase", "State", "Priority", "Budget", "OwnerPools"],
            (
                (
                    i.name,
                    i.phase.value,
                    i.state.value,
                    i.priority,
                    i.budget.value,
                    ",".join(p.value for p in i.owner_pools),
                )
                for i in inits
            ),
        )
        # Assignments
        assigns = self.adapter.list_assignments()
        _fill_table(
            self.assigns_table,
            ["Member", "Initiative", "WeekStart", "WeekEnd", "CapacityPW"],
            (
                (
                    a.member_name,
                    a.initiative_name,
                    a.week_start,
                    a.week_end or "",
                    "" if a.capacity_pw is None else f"{a.capacity_pw}",
                )
                for a in assigns
            ),
        )
        # PTO
        pto = self.adapter.list_pto()
        _fill_table(
            self.pto_table,
            ["Member", "Type", "WeekStart", "WeekEnd"],
            (
                (p.member_name, p.type.value, p.week_start, p.week_end or "")
                for p in pto
            ),
        )
        # Reports (default current quarter budget distribution)
        today = date.today()
        q = (today.month - 1) // 3 + 1
        start_month = 3 * (q - 1) + 1
        end_month = start_month + 2
        start = date(today.year, start_month, 1)
        end_day = (
            31
            if end_month in (1, 3, 5, 7, 8, 10, 12)
            else (
                29
                if today.year % 4 == 0 and end_month == 2
                else (28 if end_month == 2 else 30)
            )
        )
        end = date(today.year, end_month, end_day)
        dist = budget_distribution(self.adapter, start, end)
        total = sum(dist.values()) or 1.0
        _fill_table(
            self.reports_table,
            ["Category", "PW", "%"],
            ((k, f"{v:.2f}", f"{(v/total*100):.1f}%") for k, v in dist.items()),
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:  # noqa: N802
        bid = event.button.id or ""
        if bid == "refresh":
            self.refresh_all()
        elif bid == "export":
            # Simple defaults
            write_members_csv("members.csv", self.adapter.list_members())
            write_initiatives_csv("initiatives.csv", self.adapter.list_initiatives())
            write_pto_csv("pto.csv", self.adapter.list_pto())
            write_assignments_csv("assignments.csv", self.adapter.list_assignments())
        elif bid == "import":
            # Import if files exist next to cwd
            try:
                ms = read_members_csv("members.csv")
                if ms:
                    self.adapter.upsert_members(ms)
            except Exception:
                pass
            try:
                ins = read_initiatives_csv("initiatives.csv")
                if ins:
                    self.adapter.upsert_initiatives(ins)
            except Exception:
                pass
            try:
                pto = read_pto_csv("pto.csv")
                if pto:
                    self.adapter.upsert_pto(pto)
            except Exception:
                pass
            try:
                assigns = read_assignments_csv("assignments.csv")
                if assigns:
                    self.adapter.upsert_assignments(assigns)
            except Exception:
                pass
            self.refresh_all()
        elif bid in ("plan_greedy", "plan_ilp"):
            dfrom_input = self.query_one("#dfrom", Input).value or ""
            dto_input = self.query_one("#dto", Input).value or ""
            if not dfrom_input or not dto_input:
                return
            dfrom = parse_date(dfrom_input)
            dto = parse_date(dto_input)
            recreate = False
            pr: GreedyPlanResult | ILPPlanResult
            if bid == "plan_greedy":
                pr = plan_greedy(self.adapter, dfrom, dto, recreate=recreate)
            else:
                pr = plan_ilp(self.adapter, dfrom, dto, recreate=recreate, msg=False)
            # Apply results to assignments table (preview only; not writing back)
            _fill_table(
                self.assigns_table,
                ["Member", "Initiative", "WeekStart", "WeekEnd", "CapacityPW"],
                (
                    (
                        a.member_name,
                        a.initiative_name,
                        a.week_start,
                        a.week_end or week_end_from_start_str(a.week_start),
                        "" if a.capacity_pw is None else f"{a.capacity_pw}",
                    )
                    for a in pr.assignments
                ),
            )


def run_tui() -> None:
    TmiTui().run()
