from __future__ import annotations

from collections.abc import Iterable
from datetime import date

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Input,
    Select,
    TabbedContent,
    TabPane,
)
from textual_datepicker import DatePicker

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
from tmiplus.core.services.reports import (
    budget_distribution,
)
from tmiplus.core.util.dates import parse_date
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
    #toolbar { dock: top; padding: 1 2; }
    #content { dock: top; height: 1fr; }
    .title { color: cyan; text-style: bold; }
    .accent { color: magenta; }
    .btn-primary { background: #005f87; color: white; }
    .btn-success { background: #2d7d46; color: white; }
    .btn-warning { background: #b58900; color: black; }
    .btn-danger { background: #d33682; color: white; }
    .panel { padding: 1 2; }
    .controls { padding: 0 2; }
    """

    show_tooltip = reactive("")

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="toolbar"):
            yield Button("Refresh", id="refresh", classes="btn-success")
            yield Button("Export CSV", id="export", classes="btn-primary")
            yield Button("Import CSV", id="import", classes="btn-warning")
        with Container(id="content"):
            with TabbedContent():
                # Home page
                with TabPane("Home", id="tab_home"):
                    with Vertical(classes="panel"):
                        yield Button(
                            "Members", id="home_members", classes="btn-primary"
                        )
                        yield Button(
                            "Initiatives", id="home_inits", classes="btn-primary"
                        )
                        yield Button(
                            "Assignments", id="home_assigns", classes="btn-primary"
                        )
                        yield Button("PTO", id="home_pto", classes="btn-primary")
                        yield Button(
                            "Reports", id="home_reports", classes="btn-primary"
                        )

                # Members
                with TabPane("Members", id="tab_members"):
                    with Horizontal(classes="controls"):
                        yield Input(placeholder="Filter...", id="members_filter")
                        yield Select([], prompt="Sort column", id="members_sort_col")
                        yield Select(
                            [("asc", "Ascending"), ("desc", "Descending")],
                            id="members_sort_dir",
                        )
                        yield Button("Apply", id="members_apply", classes="btn-success")
                        yield Button("Clear", id="members_clear", classes="btn-danger")
                    yield DataTable(id="members_table")

                # Initiatives
                with TabPane("Initiatives", id="tab_inits"):
                    with Horizontal(classes="controls"):
                        yield Input(placeholder="Filter...", id="inits_filter")
                        yield Select([], prompt="Sort column", id="inits_sort_col")
                        yield Select(
                            [("asc", "Ascending"), ("desc", "Descending")],
                            id="inits_sort_dir",
                        )
                        yield Button("Apply", id="inits_apply", classes="btn-success")
                        yield Button("Clear", id="inits_clear", classes="btn-danger")
                    yield DataTable(id="inits_table")

                # Assignments
                with TabPane("Assignments", id="tab_assigns"):
                    with Horizontal(classes="controls"):
                        yield Input(placeholder="Filter...", id="assigns_filter")
                        yield Select([], prompt="Sort column", id="assigns_sort_col")
                        yield Select(
                            [("asc", "Ascending"), ("desc", "Descending")],
                            id="assigns_sort_dir",
                        )
                        yield Button("Apply", id="assigns_apply", classes="btn-success")
                        yield Button("Clear", id="assigns_clear", classes="btn-danger")
                    with Horizontal(classes="controls"):
                        yield Input(
                            placeholder="Plan from YYYY-MM-DD", id="assign_from"
                        )
                        yield Input(placeholder="Plan to YYYY-MM-DD", id="assign_to")
                        yield Button(
                            "Plan (Greedy)",
                            id="assign_plan_greedy",
                            classes="btn-primary",
                        )
                        yield Button(
                            "Plan (ILP)", id="assign_plan_ilp", classes="btn-primary"
                        )
                    yield DataTable(id="assigns_table")

                # PTO
                with TabPane("PTO", id="tab_pto"):
                    with Horizontal(classes="controls"):
                        yield Input(placeholder="Filter...", id="pto_filter")
                        yield Select([], prompt="Sort column", id="pto_sort_col")
                        yield Select(
                            [("asc", "Ascending"), ("desc", "Descending")],
                            id="pto_sort_dir",
                        )
                        yield Button("Apply", id="pto_apply", classes="btn-success")
                        yield Button("Clear", id="pto_clear", classes="btn-danger")
                    yield DataTable(id="pto_table")

                # Reports
                with TabPane("Reports", id="tab_reports"):
                    with Horizontal(classes="controls"):
                        dp_from = DatePicker()
                        dp_from.id = "report_from_dp"
                        yield dp_from
                        dp_to = DatePicker()
                        dp_to.id = "report_to_dp"
                        yield dp_to
                        yield Button("Run", id="report_run", classes="btn-success")
                    yield DataTable(id="reports_table")
        yield Footer()

    def on_mount(self) -> None:
        self.adapter = get_adapter()
        # Tables
        self.members_table = self.query_one("#members_table", DataTable)
        self.inits_table = self.query_one("#inits_table", DataTable)
        self.assigns_table = self.query_one("#assigns_table", DataTable)
        self.pto_table = self.query_one("#pto_table", DataTable)
        self.reports_table = self.query_one("#reports_table", DataTable)
        self.refresh_all()
        # Initialize report date inputs and sort select options
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
        try:
            self.query_one("#report_from_dp", DatePicker).value = start
            self.query_one("#report_to_dp", DatePicker).value = end
        except Exception:
            pass
        self.query_one("#members_sort_col", Select).set_options(
            [(c, c) for c in ["Name", "Pool", "Hours", "Squad", "Active"]]
        )
        self.query_one("#inits_sort_col", Select).set_options(
            [
                (c, c)
                for c in ["Name", "Phase", "State", "Priority", "Budget", "OwnerPools"]
            ]
        )
        self.query_one("#assigns_sort_col", Select).set_options(
            [
                (c, c)
                for c in ["Member", "Initiative", "WeekStart", "WeekEnd", "CapacityPW"]
            ]
        )
        self.query_one("#pto_sort_col", Select).set_options(
            [(c, c) for c in ["Member", "Type", "WeekStart", "WeekEnd"]]
        )

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
        # Dashboard navigation buttons
        elif bid in (
            "home_members",
            "home_inits",
            "home_assigns",
            "home_pto",
            "home_reports",
        ):
            tab_id = bid.replace("home_", "tab_")
            self.query_one(TabbedContent).active = tab_id
        # Reports run using date pickers
        elif bid == "report_run":
            try:
                dfrom = self.query_one("#report_from_dp", DatePicker).value
                dto = self.query_one("#report_to_dp", DatePicker).value
            except Exception:
                return
            if not dfrom or not dto:
                return
            # DatePicker may return date or string; normalize
            if not isinstance(dfrom, date):
                try:
                    dfrom = parse_date(str(dfrom))
                except Exception:
                    return
            if not isinstance(dto, date):
                try:
                    dto = parse_date(str(dto))
                except Exception:
                    return
            dist = budget_distribution(self.adapter, dfrom, dto)
            total = sum(dist.values()) or 1.0
            _fill_table(
                self.reports_table,
                ["Category", "PW", "%"],
                ((k, f"{v:.2f}", f"{(v/total*100):.1f}%") for k, v in dist.items()),
            )


def run_tui() -> None:
    TmiTui().run()
