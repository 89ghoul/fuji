# fuji

A quiet view of Mount Fuji in black & white ASCII, for your terminal.

Moon, faint stars, slow clouds and mist, and a lake that mirrors the mountain.
Every minute or two a small flock of birds drifts across the sky.

Pure Python 3, standard library only. Works on any Linux terminal (tested for Fedora / Void style setups).

## Run

    python3 fuji.py

| Key | Action |
|-----|--------|
| `q` / Esc / Ctrl-C | quit |
| `b` | call the birds now |

## Options

    --interval MIN MAX   seconds between bird flocks (default 60 120)
    --first MIN MAX      delay before the first flock (default 15 30)
    --fps N              frames per second (default 12)
    --plain              no colour, characters only
    --seed N             change cloud / mountain details

Needs a terminal of at least 40x14; looks best at 120x40 or larger.

## Install (optional)

    install -m755 fuji.py ~/.local/bin/fuji
