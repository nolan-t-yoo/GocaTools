# GocaTools

This toolset is primarily for Ambassadors in the Pokémon GO Ambassador Program.

Each month, we get a set of codes via email. Some groups send them in PM's in Campfire, some groups
use a web app. We prefer old-school.

Claude helped. A lot.

*ahem* Turn a list of Pokémon GO offer codes into **printable "gift" cards**. Copy your codes from
the email into a .csv file. Pick a background, setup your message. Have them printed on cardstock,
or DIY at home. Then, hand them out to your community!

There is a point-and-click UI, a small CLI, and one-click launch scripts for Windows, macOS and
Linux.

> **Not affiliated with Nintendo, The Pokémon Company or Niantic.** Only generate cards for codes
> you are entitled to distribute.

## Quick start

1. Install [Python 3.9+](https://www.python.org/downloads/) — or let the quickstart script do it
   for you (see below).
2. Launch the app:

   | Platform | Command |
   | --- | --- |
   | Windows | double-click **`launch.bat`** |
   | macOS / Linux | `./launch.sh` |

The launcher creates a private `.venv` folder next to the scripts, installs the two dependencies on
first run, and then opens the window.

### Windows: no Python yet?

Right-click **`_quickstart.ps1`** and choose *Run with PowerShell*, or run:

```powershell
powershell -ExecutionPolicy Bypass -File .\_quickstart.ps1
```

It checks for Python 3.9+ with tkinter, installs a per-user copy of Python 3.12 when none is found
(via winget, or the official python.org installer verified against a pinned SHA-256), then hands
over to `launch.bat`. No administrator rights are needed. Add `-NoLaunch` to set up Python without
opening the UI, or `-WhatIf` to see what it would do.

The window has three numbered sections — **1 · Redemption codes**, **2 · Printable PDF**, and a live
**Log** with a progress bar — plus a **Preview** of a single card beside the log:

- **Generate cards only** — writes `<cards folder>/<CODE>/message.txt` and `QR.png` for every code,
  emptying the cards folder first.
- **Build PDF only** — lays out whatever is already in the cards folder.
- **Generate + Build PDF** — does both in one go (probably what you want).

Tick **Open the PDF when finished** and the PDF opens in your usual viewer as soon as it is written.

The **Preview** redraws as you edit the template, expiry date or background — same fractions,
padding and font size the PDF uses, so you can see line breaks and any text that gets trimmed
*before* you print.

## Using the UI

1. **Codes file** — a `.csv` or `.txt` with one code per cell or per line. Commas, multiple rows,
   quoted multi-line cells, blank lines and `#` comments are all handled. A first cell like
   `code`/`passcode` is treated as a header and skipped.
2. **Message template** — see [Template variables](#template-variables).
3. **Expiry date** — free text substituted into `${EXPIRY}`, e.g. `July 31st 2026`.
4. **Cards folder** — where the per-code folders are created (default `./output`). It is **emptied
   at the start of every run**, so the PDF only ever contains the codes you just generated.
5. **PDF output** — where the finished PDF is written (default `./cards.pdf`). The checkbox below
   it opens the PDF in your default viewer once the run finishes.
6. **Background image** — *optional*; centred and cropped to fill each card. If a file named
   `background.png` / `background.jpg` sits next to the scripts it is picked automatically.

The **Preview** panel shows the first code from your codes file rendered on one card, so you can
check the wording, the expiry text and the background before generating everything.

![The GocaTools window: code file, template, expiry, cards folder, PDF output and background
picker, a card preview, and a live log with a status bar](docs/ui.png)

## Command line usage

Both scripts work without the UI and accept `-h`.

```bash
# Step 1 - card data: ./output/<CODE>/message.txt + QR.png
python pokemon.py codes.csv template.txt --expiry "July 31st 2026"

# Keep folders from earlier runs instead of starting clean:
python pokemon.py codes.csv template.txt --no-clean

# Step 2 - printable PDF: ./cards.pdf
python createpdf.py --pdf cards.pdf --background art.png
```

| Script | Arguments |
| --- | --- |
| `pokemon.py` | `csv` (required), `template` (default `template.txt`), `-o/--output` (default `./output`), `-e/--expiry` (default `N/A`), `--clean/--no-clean` (default `--clean`) |
| `createpdf.py` | `output_dir` (default `./output`), `-p/--pdf` (default `./cards.pdf`), `-b/--background` (optional) |

You can also start the UI from the command line:

```bash
python -m goca
```

## Template variables

`template.txt` is plain text. Two placeholders are replaced:

| Placeholder | Replaced with |
| --- | --- |
| `${CODE}` | The redemption code |
| `${EXPIRY}` | The `--expiry` value |

Blank trailing lines are ignored and each line is trimmed to the card width, so keep lines short —
around 22 characters fits comfortably.

## Card layout

| Property | Value |
| --- | --- |
| Card size | 3.5" × 2" (standard business card) |
| Grid | 2 columns × 5 rows per US Letter page |
| Left 2/3 | Semi-transparent white box with the message text |
| Right 1/3 | QR code pointing at `https://store.pokemongo.com/offer-redemption?passcode=<CODE>` |
| Background | Optional image, scaled to fill and clipped to the card |

Print at **100% / actual size** — do not let the print dialog scale the page.

## Manual installation

The launchers do this for you; do it by hand if you prefer:

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install "qrcode[pil]" reportlab
```

## Project layout

```
_quickstart.ps1          Windows helper: install Python if needed, then run launch.bat
launch.bat / launch.sh   one-click launchers (create .venv, install deps, open the UI)
goca/                    the application
  codes.py               reading code lists, rendering messages, QR images
  generator.py           one folder per code (message.txt + QR.png)
  pdf.py                 business-card PDF layout
  preview.py             on-screen card preview (mirrors the PDF layout)
  gui.py                 tkinter UI
pokemon.py               CLI wrapper for step 1
createpdf.py             CLI wrapper for step 2
template.txt             default message template
tests/                   pytest suite
```

## Development

```bash
python -m pytest
```

The suite covers parsing, generation, PDF pagination, the card preview, both CLIs and the UI
(UI tests are skipped automatically when no display is available).

## Keep your codes private

Redemption codes are single-use and valuable. `.gitignore` already excludes `codes.csv`,
`unused_codes*.txt`, the `output/` folder, any `*.pdf` and all images, so `git status` stays clean
even when you work with real data. Card artwork and Pokémon imagery is copyrighted — bring your own
and keep it out of the repository.

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| No Python installed (Windows) | Run `_quickstart.ps1` — it installs a per-user Python 3.12 and then launches the app. |
| `python` opens the Microsoft Store (Windows) | The Store alias is shadowing Python. Run `_quickstart.ps1`, install from python.org, or disable *App execution aliases* for `python.exe`. The launcher also searches `%LOCALAPPDATA%\Programs\Python`. |
| `_quickstart.ps1` will not run | Windows blocks unsigned scripts by double-click; use `powershell -ExecutionPolicy Bypass -File .\_quickstart.ps1`, or right-click the file and choose *Run with PowerShell*. |
| `ModuleNotFoundError: tkinter` (Linux) | `sudo apt install python3-tk` (Debian/Ubuntu) or `sudo dnf install python3-tkinter` (Fedora); macOS: `brew install python-tk`. |
| QR code will not scan | Print at actual size on a laser/inkjet printer; avoid scaling to "fit page". |
| Codes look truncated on the card | Shorten the template lines — they are trimmed to the card width. |

## License

[MIT](LICENSE)
