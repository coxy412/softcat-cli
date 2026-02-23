"""SOFT CAT CLI — the cat-themed agent spawner interface."""

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from softcat import __version__
from softcat.config import get_config, init_config
from softcat.agents.manager import AgentManager

console = Console()

BANNER = """[bold cyan]
  ╔═══════════════════════════════════════╗
  ║  🐱 SOFT CAT                         ║
  ║  Smart Outputs From Trained           ║
  ║  Conversational AI Technology         ║
  ╚═══════════════════════════════════════╝
[/bold cyan]"""


@click.group()
@click.version_option(version=__version__, prog_name="softcat")
@click.pass_context
def cli(ctx: click.Context) -> None:
    """🐱 SOFT CAT — A conversational agent spawner.

    Describe what you want. The cat builds it.
    """
    ctx.ensure_object(dict)
    ctx.obj["config"] = get_config()
    ctx.obj["manager"] = AgentManager(ctx.obj["config"])


@cli.command()
@click.argument("description")
@click.option("--name", "-n", default=None, help="Agent name (auto-generated if not set)")
@click.option("--model", "-m", default="claude-sonnet-4-5-20250929", help="Claude model to use")
@click.option("--dry-run", is_flag=True, help="Generate but don't deploy")
@click.option("--verbose", "-v", is_flag=True, help="Show detailed pipeline output")
def spawn(description: str, name: str | None, model: str, dry_run: bool, verbose: bool) -> None:
    """Create a new agent from a natural language description.

    The full S.O.F.T.C.A.T pipeline runs:
    Scan → Orchestrate → Fabricate → Test → Configure → Activate → Track

    Example:
        softcat spawn "watch HackerNews for AI news, summarise top 5 daily"
    """
    console.print(BANNER)
    console.print(f"[dim]Spawning agent from description...[/dim]\n")

    from softcat.core.scanner import Scanner
    from softcat.core.orchestrator import Orchestrator
    from softcat.core.fabricator import Fabricator
    from softcat.core.tester import Tester
    from softcat.core.configurator import Configurator
    from softcat.core.activator import Activator
    from softcat.core.tracker import Tracker

    config = get_config()

    # S — Scan
    console.print("[bold yellow]🐱 Scanning requirements...[/bold yellow]")
    scanner = Scanner(config, model=model)
    scan_result = scanner.scan(description)

    if verbose:
        console.print(Panel(str(scan_result), title="Scan Result"))

    agent_name = name or scan_result.suggested_name

    # O — Orchestrate
    console.print("[bold yellow]🐱 Orchestrating...[/bold yellow]")
    orchestrator = Orchestrator(config)
    plan = orchestrator.plan(scan_result)

    if verbose:
        console.print(Panel(str(plan), title="Orchestration Plan"))

    # F — Fabricate
    console.print("[bold yellow]🐱 Fabricating agent...[/bold yellow]")
    fabricator = Fabricator(config)
    agent_dir = fabricator.fabricate(agent_name, scan_result, plan)
    console.print(f"   → generated: {agent_dir}")

    # T — Test
    console.print("[bold yellow]🐱 Testing against sample data...[/bold yellow]")
    tester = Tester(config)
    test_result = tester.test(agent_dir)

    if not test_result.passed:
        console.print(f"[bold red]🙀 Tests failed: {test_result.message}[/bold red]")
        if not dry_run:
            console.print("[dim]Use --dry-run to generate without deploying[/dim]")
            return

    console.print("   → [green]✓ passed[/green]")

    if dry_run:
        console.print(f"\n[bold cyan]🐱 Dry run complete. Agent at: {agent_dir}[/bold cyan]")
        return

    # C — Configure
    console.print("[bold yellow]🐱 Configuring deployment...[/bold yellow]")
    configurator = Configurator(config)
    deploy_config = configurator.configure(agent_name, scan_result, plan)
    console.print(f"   → schedule: {deploy_config.schedule}")

    # A — Activate
    console.print("[bold yellow]🐱 Activating...[/bold yellow]")
    activator = Activator(config)
    activator.activate(agent_name, agent_dir, deploy_config)
    console.print("   → [green]live ✓[/green]")

    # T — Track
    console.print("[bold yellow]🐱 Tracking enabled[/bold yellow]")
    tracker = Tracker(config)
    tracker.register(agent_name, deploy_config)

    console.print(f"\n[bold green]Agent spawned: {agent_name} 🐱[/bold green]")


@cli.command()
def litter() -> None:
    """List all spawned agents."""
    config = get_config()
    manager = AgentManager(config)
    agents = manager.list_agents()

    if not agents:
        console.print("[dim]No agents spawned yet. Use 'softcat spawn' to create one.[/dim]")
        return

    table = Table(title="🐱 The Litter", show_header=True)
    table.add_column("Name", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Schedule", style="yellow")
    table.add_column("Last Run", style="dim")
    table.add_column("Outputs", justify="right")

    for agent in agents:
        status_icon = {
            "active": "[green]purring[/green]",
            "paused": "[yellow]napping[/yellow]",
            "error": "[red]hissing[/red]",
        }.get(agent.status, agent.status)

        table.add_row(
            agent.name,
            status_icon,
            agent.schedule or "manual",
            agent.last_run or "never",
            str(agent.output_count),
        )

    console.print(table)


@cli.command()
@click.argument("agent_name")
def purr(agent_name: str) -> None:
    """Check status of an agent. Is it purring along?"""
    config = get_config()
    manager = AgentManager(config)
    agent = manager.get_agent(agent_name)

    if not agent:
        console.print(f"[red]🙀 No agent named '{agent_name}'[/red]")
        return

    console.print(Panel(
        f"[bold]{agent.name}[/bold]\n\n"
        f"Status: {agent.status}\n"
        f"Schedule: {agent.schedule or 'manual'}\n"
        f"Last run: {agent.last_run or 'never'}\n"
        f"Outputs: {agent.output_count}\n"
        f"Health: {agent.health_url or 'not configured'}",
        title=f"🐱 {agent_name}",
    ))


@cli.command()
@click.argument("agent_name")
@click.option("--limit", "-l", default=5, help="Number of outputs to show")
def feed(agent_name: str, limit: int) -> None:
    """Show recent outputs from an agent."""
    config = get_config()
    manager = AgentManager(config)
    outputs = manager.get_outputs(agent_name, limit=limit)

    if not outputs:
        console.print(f"[dim]No outputs yet for '{agent_name}'[/dim]")
        return

    for output in outputs:
        console.print(Panel(
            output.content[:500] + ("..." if len(output.content) > 500 else ""),
            title=f"{output.timestamp}",
            subtitle=output.filename,
        ))


@cli.command()
@click.argument("agent_name")
def nap(agent_name: str) -> None:
    """Pause an agent. It'll sleep until you wake it."""
    config = get_config()
    manager = AgentManager(config)

    if manager.pause_agent(agent_name):
        console.print(f"[yellow]😴 {agent_name} is napping[/yellow]")
    else:
        console.print(f"[red]🙀 Couldn't pause '{agent_name}'[/red]")


@cli.command()
@click.argument("agent_name")
def wake(agent_name: str) -> None:
    """Resume a paused agent."""
    config = get_config()
    manager = AgentManager(config)

    if manager.resume_agent(agent_name):
        console.print(f"[green]🐱 {agent_name} is awake and purring[/green]")
    else:
        console.print(f"[red]🙀 Couldn't wake '{agent_name}'[/red]")


@cli.command()
@click.argument("agent_name")
@click.confirmation_option(prompt="Are you sure? This permanently removes the agent.")
def hiss(agent_name: str) -> None:
    """Kill an agent permanently. Gone. Nine lives used up."""
    config = get_config()
    manager = AgentManager(config)

    if manager.remove_agent(agent_name):
        console.print(f"[red]💀 {agent_name} has been removed[/red]")
    else:
        console.print(f"[red]🙀 Couldn't remove '{agent_name}'[/red]")


@cli.command()
def groom() -> None:
    """Update all agents to the latest framework version."""
    config = get_config()
    manager = AgentManager(config)
    agents = manager.list_agents()

    if not agents:
        console.print("[dim]No agents to groom.[/dim]")
        return

    console.print("[bold]🐱 Grooming all agents...[/bold]\n")

    for agent in agents:
        console.print(f"  Grooming {agent.name}...", end=" ")
        success = manager.update_agent(agent.name)
        if success:
            console.print("[green]✓[/green]")
        else:
            console.print("[red]✗[/red]")

    console.print("\n[bold green]Grooming complete 🐱[/bold green]")


@cli.command()
@click.argument("template_name")
def adopt(template_name: str) -> None:
    """Install a community agent template."""
    console.print(f"[bold]🐱 Adopting template: {template_name}[/bold]")
    # TODO: Implement template registry and installation
    console.print("[dim]Template registry coming soon.[/dim]")


@cli.command()
def meow() -> None:
    """Interactive chat mode for designing complex agents.

    Talk to the cat. It'll ask questions, refine your requirements,
    and spawn the perfect agent.
    """
    console.print(BANNER)
    console.print("[bold]Entering interactive mode. Type 'quit' to exit.[/bold]\n")
    console.print("[cyan]🐱 What would you like me to build?[/cyan]\n")

    # TODO: Implement interactive multi-turn agent design
    # This will use Claude in a conversational loop to refine
    # requirements before running the spawn pipeline
    console.print("[dim]Interactive mode coming soon. Use 'softcat spawn' for now.[/dim]")


@cli.command()
def init() -> None:
    """Initialise SOFT CAT configuration."""
    console.print(BANNER)
    init_config()
    console.print("[bold green]🐱 SOFT CAT initialised. Ready to spawn.[/bold green]")


if __name__ == "__main__":
    cli()
