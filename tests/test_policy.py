"""Every bot committed for the server runs the same in NumPy as it did in
PyTorch when it was exported (ADR 0013). No PyTorch needed: the export carries
its own inputs and the logits PyTorch gave for them."""

import numpy as np

from app.game.policy import BOT_DIR, Policy, deployed


def test_every_committed_bot_matches_its_export():
    for path in sorted(BOT_DIR.glob("*.npz")):
        data = np.load(path)
        got = Policy(path).logits(data["check_planes"], data["check_scalars"])
        assert np.allclose(got, data["check_logits"], atol=1e-4), path.name


def test_the_deployed_bot_exists_if_one_is_named():
    pointer = BOT_DIR / "current.txt"
    if pointer.exists():
        assert deployed() is not None, f"current.txt names {pointer.read_text().strip()}, which isn't in {BOT_DIR}"


def test_every_bot_the_server_names_is_a_checked_export():
    """The deployed bot, the balanced bot (ADR 0023), the bot on show and every trained teammate bot in the
    study are among the exports checked above, so none ships unchecked."""
    from app.game import study

    checked = {path.stem for path in BOT_DIR.glob("*.npz")}
    named = {(BOT_DIR / f).read_text().strip() for f in ("current.txt", "watch.txt", "balanced.txt") if (BOT_DIR / f).exists()}
    named |= {b for b in study.TEAMMATE_BOTS if b != "scripted"}
    assert named <= checked, f"named but not exported: {named - checked}"
    assert {"cur4", "fcp1"} <= named
