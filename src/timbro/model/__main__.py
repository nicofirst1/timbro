"""Smoke-test entry point: `uv run python -m timbro.model` (CLAUDE.md's core smoke
test). The block moved verbatim from model.py's `if __name__ == "__main__":` (#106),
which a package would otherwise swallow silently."""

from timbro.model import VoiceModel

if __name__ == "__main__":
    # Smoke test: a draft in the seed voice must score closer than an alien one.
    plain = [
        "The cat sat by the door. It was small and grey.",
        "We went to the shop. The shop was shut, so we walked home.",
        "He likes tea. She likes coffee. They share a pot all the same.",
        "Rain fell all day. The street was wet. The dog stayed in.",
        "I read the book twice. The first time was slow. The second was quick.",
        "The bread was warm. We ate it with butter and a bit of jam.",
        "She ran to the bus. It left without her. So she took the next one.",
        "The light was low. We lit a candle and sat and talked.",
    ]
    model = VoiceModel.fit(plain)
    near = model.score("The bird flew off. It was quick and small.").distance
    far = model.score(
        "Henceforth the dialectical synthesis necessitates rigorous deconstruction of ontological categories."
    ).distance
    assert near < far, f"voice region failed to separate: near={near} far={far}"
    print(f"ok: in-voice={near:.2f} < out-of-voice={far:.2f}")
