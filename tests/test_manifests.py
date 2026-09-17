from pathlib import Path

from epilepsy_agentry.agents import load_manifests

ROOT = Path(__file__).resolve().parents[1]


def test_all_manifests_load_and_prompts_exist():
    ms = load_manifests(ROOT / "aspects")
    assert {m.name for m in ms} >= {"artifact_adversary", "onset_lateralization", "report_reconciler"}
    for m in ms:
        assert (ROOT / m.prompt_file).exists(), m.prompt_file
