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


def _run_pipeline(
    config: "Config",
    agent_name: str,
    scan_result: "ScanResult",
    model: str = "claude-sonnet-4-5-20250929",
    dry_run: bool = False,
    verbose: bool = False,
) -> None:
    """Run the O→F→T→C→A→T pipeline after scanning/designing is complete."""
    from softcat.core.orchestrator import Orchestrator
    from softcat.core.fabricator import Fabricator
    from softcat.core.tester import Tester
    from softcat.core.configurator import Configurator
    from softcat.core.activator import Activator
    from softcat.core.tracker import Tracker

    if verbose:
        console.print(Panel(str(scan_result), title="Scan Result"))

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

    # Post-activation runtime test
    console.print("[bold yellow]🐱 Verifying agent runs correctly...[/bold yellow]")
    runtime_result = tester.test_runtime(agent_dir)

    if runtime_result.warnings:
        for w in runtime_result.warnings:
            console.print(f"   [yellow]⚠ {w}[/yellow]")

    if runtime_result.passed:
        console.print("   → [green]runtime check passed ✓[/green]")
    else:
        console.print("   → [yellow]runtime check had issues (agent deployed anyway)[/yellow]")

    # T — Track
    console.print("[bold yellow]🐱 Tracking enabled[/bold yellow]")
    tracker = Tracker(config)
    tracker.register(agent_name, deploy_config)

    console.print(f"\n[bold green]Agent spawned: {agent_name} 🐱[/bold green]")


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
    from softcat.core.scanner import Scanner

    console.print(BANNER)
    console.print(f"[dim]Spawning agent from description...[/dim]\n")

    config = get_config()

    # S — Scan
    console.print("[bold yellow]🐱 Scanning requirements...[/bold yellow]")
    scanner = Scanner(config, model=model)
    scan_result = scanner.scan(description)

    agent_name = name or scan_result.suggested_name

    _run_pipeline(config, agent_name, scan_result, model=model, dry_run=dry_run, verbose=verbose)


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
@click.option("--verbose", "-v", is_flag=True, help="Show detailed output")
def trigger(agent_name: str, verbose: bool) -> None:
    """Poke an agent to run right now. No waiting for cron.

    Runs the agent immediately, streaming output to the terminal.
    Does NOT signal the healthcheck endpoint (that's for scheduled runs).
    Works even if the agent is napping.

    Example:
        softcat trigger hackernews-ai-agent-digest
    """
    import subprocess

    from softcat.agents.runtime import build_env, resolve_python

    config = get_config()
    manager = AgentManager(config)
    agent = manager.get_agent(agent_name)

    if not agent:
        console.print(f"[red]🙀 No agent named '{agent_name}'[/red]")
        raise SystemExit(1)

    agent_dir = config.agents_dir / agent_name
    python = resolve_python(agent_dir)

    if verbose:
        console.print(f"[dim]Agent dir: {agent_dir}[/dim]")
        console.print(f"[dim]Python:    {python}[/dim]")
        console.print(f"[dim]Status:    {agent.status}[/dim]")

    console.print(f"[bold yellow]🐱 Poking {agent_name} awake...[/bold yellow]\n")

    env = build_env(agent_dir, extra={"SOFTCAT_MANUAL_TRIGGER": "1"})

    try:
        result = subprocess.run(
            [python, str(agent_dir / "agent.py")],
            cwd=str(agent_dir),
            env=env,
        )
    except KeyboardInterrupt:
        console.print(f"\n[yellow]Interrupted. {agent_name} stopped mid-run.[/yellow]")
        raise SystemExit(130)

    if result.returncode == 0:
        console.print(f"\n[bold green]🐱 {agent_name} ran successfully[/bold green]")
    else:
        console.print(f"\n[bold red]🙀 {agent_name} exited with code {result.returncode}[/bold red]")
        raise SystemExit(result.returncode)


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
@click.argument("agent_name", required=False, default=None)
@click.option("--prompt", is_flag=True, help="Also regenerate the prompt template")
def groom(agent_name: str | None, prompt: bool) -> None:
    """Regenerate agent code using the latest framework conventions.

    Refreshes agent.py while preserving config, prompt, env, and outputs.
    Use --prompt to also regenerate prompt.md.

    \b
    Examples:
        softcat groom hackernews-ai-agent-digest
        softcat groom hackernews-ai-agent-digest --prompt
        softcat groom              # groom all agents
    """
    config = get_config()
    manager = AgentManager(config)

    if agent_name:
        agents_to_groom = [manager.get_agent(agent_name)]
        if agents_to_groom[0] is None:
            console.print(f"[red]🙀 No agent named '{agent_name}'[/red]")
            raise SystemExit(1)
    else:
        agents_to_groom = manager.list_agents()

    if not agents_to_groom:
        console.print("[dim]No agents to groom.[/dim]")
        return

    mode = "code + prompt" if prompt else "code only"
    console.print(f"[bold]🐱 Grooming ({mode})...[/bold]\n")

    for agent in agents_to_groom:
        console.print(f"  Grooming {agent.name}...", end=" ")
        try:
            success = manager.update_agent(agent.name, regenerate_prompt=prompt)
        except Exception as exc:
            console.print(f"[red]✗ {exc}[/red]")
            continue

        if success:
            console.print("[green]✓ fur looking fresh[/green]")
        else:
            console.print("[red]✗ hairball — restored previous version[/red]")

    console.print("\n[bold green]Grooming complete 🐱[/bold green]")


@cli.command()
@click.argument("template_name")
def adopt(template_name: str) -> None:
    """Install a community agent template."""
    console.print(f"[bold]🐱 Adopting template: {template_name}[/bold]")
    # TODO: Implement template registry and installation
    console.print("[dim]Template registry coming soon.[/dim]")


@cli.command()
@click.option("--name", "-n", default=None, help="Override agent name")
@click.option("--model", "-m", default=None, help="Claude model for conversation")
@click.option("--design-only", is_flag=True, help="Design without spawning")
def meow(name: str | None, model: str | None, design_only: bool) -> None:
    """Interactive chat mode for designing complex agents.

    Talk to the cat. It'll ask questions, refine your requirements,
    and spawn the perfect agent. Type 'quit' or 'exit' to leave.

    \b
    Examples:
        softcat meow
        softcat meow --design-only
        softcat meow --name my-agent
    """
    from softcat.core.designer import Designer

    console.print(BANNER)
    console.print("[bold]Interactive agent designer. Type 'quit' to exit.[/bold]\n")
    console.print("[cyan]🐱 What would you like me to build?[/cyan]\n")

    config = get_config()
    designer = Designer(config, model=model)

    try:
        scan_result = designer.design()
    except KeyboardInterrupt:
        console.print("\n[dim]Interrupted. No agent created.[/dim]")
        return

    if scan_result is None:
        return

    # Show summary
    agent_name = name or scan_result.suggested_name
    sources = ", ".join(s.description or s.url_or_path or s.type for s in scan_result.data_sources) or "none"

    console.print(Panel(
        f"[bold]{agent_name}[/bold]\n\n"
        f"{scan_result.summary}\n\n"
        f"Schedule:  {scan_result.schedule.cron_expression}\n"
        f"Output:    {scan_result.output.format} → {scan_result.output.destination}\n"
        f"Sources:   {sources}\n"
        f"Intent:    {scan_result.intent}\n"
        f"Complexity: {scan_result.complexity}",
        title="🐱 Agent Design",
    ))

    if design_only:
        console.print("[dim]Design complete (--design-only). Use 'softcat spawn' to build.[/dim]")
        return

    # Confirm before spawning
    if not click.confirm("Spawn this agent?"):
        console.print("[dim]No agent created.[/dim]")
        return

    console.print()
    _run_pipeline(
        config,
        agent_name,
        scan_result,
        model=model or config.default_model,
    )


@cli.command()
def init() -> None:
    """Initialise SOFT CAT configuration."""
    console.print(BANNER)
    init_config()
    console.print("[bold green]🐱 SOFT CAT initialised. Ready to spawn.[/bold green]")


if __name__ == "__main__":
    cli()
