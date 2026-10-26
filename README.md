# The Quorum Engine

A card-driven engine for running a town vote or council session at the table.
Deal the hand, watch the room make up its mind, then argue to decide who
actually turns up.

## Running it

Python 3.10 or newer. No dependencies - standard library only.

    python quorum_engine.py

On Windows, `pythonw quorum_engine.py` skips the console window.

## How it works

The bill serves one domain and spends another. A bloc's *lean* is its rating in
the served domain, or minus its rating in the spent domain, whichever is
bigger.

Each bloc draws a card. Card value plus lean plus momentum is its score; the
pass difficulty is the line it must reach to be for the bill. **The card
decides the mind.**

A face card means that bloc takes the floor: it draws again for its real vote,
and every extra face card in a row makes the speech louder.

**Speeches never change a mind.** They decide turnout - a speech rallies the
blocs of its own suit who already agree, and dampens the ones who don't.

A zealous bloc will not vote against. An apathetic bloc will not vote for.

## Controls

- Right-click a row, or click the apa / zea boxes, to flag someone.
- Click a speech to select it, then click someone to land it on them.
- Ctrl+S saves. The save is a local JSON file beside the script.

## Privacy

No network calls, no telemetry.

## Licence

MIT - see [LICENSE](LICENSE).
