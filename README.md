# fuji

A quiet view of Mount Fuji in black & white ASCII, for your terminal.

Moon, faint stars, slow clouds and mist, and a lake that mirrors the mountain.
Every minute or two a small flock of birds drifts across the sky.

Pure Python 3, standard library only. Works on any Linux terminal (tested for Fedora / Void style setups).

## Install (one command)

    mkdir -p ~/.local/bin && curl -fsSL https://raw.githubusercontent.com/89ghoul/fuji/main/fuji.py -o ~/.local/bin/fuji && chmod +x ~/.local/bin/fuji

No curl? Use wget instead:

    mkdir -p ~/.local/bin && wget -qO ~/.local/bin/fuji https://raw.githubusercontent.com/89ghoul/fuji/main/fuji.py && chmod +x ~/.local/bin/fuji

Then just run:

    fuji

If `fuji` is not found, add `~/.local/bin` to your PATH (`export PATH="$HOME/.local/bin:$PATH"` in your `~/.bashrc` or `~/.zshrc`).

To update, run the same command again. To remove: `rm ~/.local/bin/fuji`.

## Run without installing

    git clone https://github.com/89ghoul/fuji && python3 fuji/fuji.py

## Controls

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
