from __future__ import annotations

import typer

from tmiplus.config.loader import ensure_config, save_config

app = typer.Typer(help="Config management")

@app.command()
def show():
    cfg = ensure_config()
    import yaml
    typer.echo(yaml.safe_dump(cfg.model_dump(), sort_keys=False, allow_unicode=True))

@app.command("pools")
def pools_list():
    cfg = ensure_config()
    typer.echo("Pools: " + ", ".join(cfg.pools))

@app.command("pools-add")
def pools_add(name: str):
    cfg = ensure_config()
    if name in cfg.pools:
        typer.echo(f"Pool already exists: {name}")
        return
    cfg.pools.append(name)
    save_config(cfg)
    typer.echo(f"Added pool '{name}'. Please also update Airtable select options manually.")

@app.command("pools-remove")
def pools_remove(name: str):
    cfg = ensure_config()
    if name not in cfg.pools:
        typer.echo(f"Pool not in config: {name}")
        return
    cfg.pools = [p for p in cfg.pools if p != name]
    save_config(cfg)
    typer.echo(f"Removed pool '{name}'. Please also update Airtable select options manually.")
