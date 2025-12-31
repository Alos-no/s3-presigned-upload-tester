"""Console reporter using Rich library for formatted CLI output.

Provides colorful, formatted output during test execution including:
- Provider headers and progress
- Per-case results with pass/fail indicators
- Final summary table comparing all providers
"""

from rich.console import Console
from rich.table import Table
from rich import box
from rich.panel import Panel
from rich.rule import Rule

from src.reporters.base import Reporter
from src.models import CaseResult, ProviderResult, ResultStatus
from src.test_cases import CASE_DEFINITIONS


# Short labels for the summary table columns
# Multipart tests (case_1, 2, 5-8) and Single-part tests (case_9-12)
CASE_SHORT_NAMES = {
    # Multipart upload tests
    "case_1": "MP:CL>",
    "case_2": "MP:CL<",
    "case_5": "MP:Sig>",
    "case_6": "MP:Sig<",
    "case_7": "MP:Ctrl",
    "case_8": "MP:List",
    # Single-part upload tests
    "case_9": "SP:CL>",
    "case_10": "SP:CL<",
    "case_11": "SP:Sig<",
    "case_12": "SP:Ctrl",
}


class ConsoleReporter(Reporter):
    """Rich-based console reporter for CLI output.

    Displays formatted, colorful output during test execution:
    - Headers when each provider starts
    - Pass/fail indicators for each test case
    - Summary table at the end

    Args:
        quiet: If True, suppress per-case output (only show summary)
    """

    def __init__(self, quiet: bool = False):
        """Initialize the console reporter.

        Args:
            quiet: Suppress per-case output if True
        """
        # Use legacy_windows=True for ASCII-safe output on Windows consoles
        self.console = Console(legacy_windows=True)
        self.quiet = quiet

    def on_case_start(self, provider_name: str, case_id: str) -> None:
        """Called when a test case starts.

        Currently a no-op for console reporter.
        """
        pass

    def on_case_complete(self, provider_name: str, result: CaseResult) -> None:
        """Called when a test case completes.

        Displays pass/fail indicator with case details.
        """
        if self.quiet:
            return

        case_def = CASE_DEFINITIONS.get(result.case_id, {})
        case_name = case_def.get("name", result.case_id)

        if result.status == ResultStatus.PASS:
            status_text = "[green][PASS][/green]"
        elif result.status == ResultStatus.FAIL:
            status_text = "[red][FAIL][/red]"
        else:
            status_text = "[yellow][ERROR][/yellow]"

        self.console.print(f"  {status_text}: {case_name}")

        if result.error_message and result.status != ResultStatus.PASS:
            self.console.print(f"     [dim]{result.error_message}[/dim]")

    def on_provider_start(self, provider_name: str) -> None:
        """Called when testing begins for a provider.

        Displays a header with the provider name.
        """
        self.console.print()
        self.console.print(
            Rule(f"[bold cyan]Testing: {provider_name}[/bold cyan]", style="cyan", characters="-")
        )

    def on_provider_complete(self, result: ProviderResult) -> None:
        """Called when testing completes for a provider.

        Displays summary of provider results.
        """
        if result.status == ResultStatus.PASS:
            status = "[bold green]PASSED[/bold green]"
        elif result.status == ResultStatus.FAIL:
            status = "[bold red]FAILED[/bold red]"
        else:
            status = "[bold yellow]ERROR[/bold yellow]"

        duration_str = ""
        if result.duration_seconds > 0:
            duration_str = f" in {result.duration_seconds:.1f}s"

        self.console.print()
        self.console.print(f"{result.provider_name}: {status}{duration_str}")

        if result.error_message:
            self.console.print(f"   [dim red]{result.error_message}[/dim red]")

    def on_run_complete(self, results: dict[str, ProviderResult]) -> None:
        """Called when all testing is complete.

        Displays a summary table comparing all providers.
        """
        if not results:
            self.console.print("[yellow]No results to display.[/yellow]")
            return

        self.console.print()
        self.console.print(
            Rule("[bold]Provider Compliance Summary[/bold]", style="magenta", characters="-")
        )

        # Create summary table with ASCII-safe box drawing
        table = Table(
            title="",
            show_header=True,
            header_style="bold magenta",
            border_style="dim",
            box=box.ASCII,
        )

        # Add columns - use no_wrap to prevent Unicode ellipsis on Windows
        table.add_column("Provider", style="cyan", no_wrap=True)
        for case_id in sorted(CASE_SHORT_NAMES.keys()):
            table.add_column(CASE_SHORT_NAMES[case_id], justify="center", no_wrap=True)
        table.add_column("Status", justify="center", no_wrap=True)

        # Add rows for each provider
        for provider_key, provider_result in results.items():
            row_data = [provider_result.provider_name]

            # Add case results
            for case_id in sorted(CASE_SHORT_NAMES.keys()):
                case_result = provider_result.cases.get(case_id)
                if case_result is None:
                    symbol = "[dim]-[/dim]"
                elif case_result.status == ResultStatus.PASS:
                    symbol = "[green]OK[/green]"
                elif case_result.status == ResultStatus.FAIL:
                    symbol = "[red]X[/red]"
                else:
                    symbol = "[yellow]?[/yellow]"
                row_data.append(symbol)

            # Add overall status
            if provider_result.status == ResultStatus.PASS:
                status_symbol = "[green]PASS[/green]"
            elif provider_result.status == ResultStatus.FAIL:
                status_symbol = "[red]FAIL[/red]"
            else:
                status_symbol = "[yellow]ERROR[/yellow]"
            row_data.append(status_symbol)

            table.add_row(*row_data)

        self.console.print(table)
        self.console.print()
