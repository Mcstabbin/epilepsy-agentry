from __future__ import annotations

from pathlib import Path

import typer

app = typer.Typer(help="epilepsy-agentry: reduction pyramid for EMU recordings", no_args_is_help=True)


@app.command()
def inspect(edf: Path):
    """Print channels, sampling rate, duration, and annotations of an EDF+ file."""
    import mne

    raw = mne.io.read_raw_edf(edf, preload=False, verbose="error")
    typer.echo(f"sfreq: {raw.info['sfreq']} Hz   duration: {raw.n_times / raw.info['sfreq'] / 3600:.2f} h")
    typer.echo(f"channels ({len(raw.ch_names)}): {', '.join(raw.ch_names)}")
    typer.echo(f"meas_date: {raw.info['meas_date']}")
    typer.echo(f"annotations: {len(raw.annotations)}")
    for o, d, l in list(zip(raw.annotations.onset, raw.annotations.duration, raw.annotations.description))[:50]:
        typer.echo(f"  {o:10.1f}s  {d:6.1f}s  {l}")


@app.command()
def transcode(edf: Path, zarr_out: Path, recording_id: str = "rec001"):
    """L0: EDF+ -> chunked Zarr canonical store."""
    from .store import transcode_edf_to_zarr

    ta = transcode_edf_to_zarr(edf, zarr_out, recording_id)
    typer.echo(f"wrote {zarr_out}  origin={ta.origin_utc}  sfreq={ta.sfreq}")


@app.command()
def features(zarr_in: Path, parquet_out: Path):
    """L1: continuous features -> Parquet."""
    from .features import compute_l1
    from .store import CanonicalStore

    p = compute_l1(CanonicalStore(zarr_in), parquet_out)
    typer.echo(f"wrote {p}")


@app.command()
def candidates(zarr_in: Path, l1_parquet: Path | None = None):
    """L2: list candidate episodes."""
    from .detectors import assemble_candidates
    from .store import CanonicalStore

    for c in assemble_candidates(CanonicalStore(zarr_in), str(l1_parquet) if l1_parquet else None):
        typer.echo(f"{c.candidate_id}  core {c.core.t0:.0f}-{c.core.t1:.0f}s  {c.sources}")


@app.command()
def aspects(aspects_dir: Path = Path("aspects")):
    """List aspect manifests."""
    from .agents import load_manifests

    for m in load_manifests(aspects_dir):
        typer.echo(f"{m.name:28s} on={m.trigger.when:16s} claims={m.claim_types}")


@app.command()
def conflicts(claims_path: Path = Path("data/claims.jsonl")):
    """L4 helper: show claims where aspects disagree."""
    from .claims import ClaimStore

    for (uri, ct), cs in ClaimStore(claims_path).conflicts().items():
        typer.echo(f"\n{ct} @ {uri}")
        for c in cs:
            typer.echo(f"  [{c.aspect} {c.confidence:.2f}] {c.assertion}")


@app.command()
def demo(output_dir: Path = Path("data/demo"), seed: int = 7):
    """Run six synthetic events through local processing and two demonstration agents."""
    from .demo import run_demo

    try:
        report = run_demo(output_dir, seed)
    except FileExistsError as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(f"Synthetic demo complete. Open {report.resolve()}")


@app.command()
def review(zarr_in: Path, output_dir: Path, claims_path: Path | None = None):
    """Create a local HTML/JSON review packet from recording annotations."""
    from .detectors import assemble_candidates
    from .review import write_review
    from .store import CanonicalStore

    store = CanonicalStore(zarr_in)
    try:
        report = write_review(store, assemble_candidates(store), output_dir, claims_path)
    except (FileExistsError, FileNotFoundError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(f"Review packet written. Open {report.resolve()}")


if __name__ == "__main__":
    app()
