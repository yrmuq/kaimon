<div align="center">

# Kaimon

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![checks](https://github.com/yrmuq/kaimon/actions/workflows/checks.yml/badge.svg?branch=dev)](https://github.com/yrmuq/kaimon/actions/workflows/checks.yml)

</div>

---

> [!NOTE]
> Kaimon is in active development. Behavior can change, bugs may occur, and a saved language or theme in the browser may no longer match a newer version.

---

Kaimon opens one text file and shows two views of it, scrolled to places that repeat or say the same thing in different words, so those notes can be cleaned by hand. The page is a small web application. The file stays one document: nothing is stored as cut-up records.

![Two panels of one Russian text file with similar passages marked](assets/screenshot.png)

---

## Features

- Open one `.txt` file and edit it in two panels
- Open a `.txt` file from the mounted notes folder
- Find repeated passages and Russian paraphrases locally, without an external API
- Set how close a meaning or a wording match must be
- Save the edited file, and restore unsaved edits after a restart
- Move through the pairs with Next; the mark is only a guide
- Delete the extra text yourself with Backspace
- Download the edited file
- English and Russian interface
- Light, dark, and system theme

---

<details>
<summary><h2>Controls & Shortcuts</h2></summary>

| Input | Action |
| --- | --- |
| Open | Load a `.txt` file into both panels |
| Notes | Open a `.txt` file from the mounted folder |
| Save | Write the edited text back to that file |
| Download | Download the edited text |
| Meaning | Hide pairs below this semantic similarity |
| Wording | Hide pairs below this word similarity |
| Next | Scroll each panel to the next similar place |
| Backspace | Delete the selection in the panel being edited |
| Language | Switch between English and Russian |
| Theme | Light, dark, or match the system |

Both panels are the same file. A deletion in one panel changes the other. The mark can be shorter or longer than the text you want to remove. A pair stays visible when at least one score is high enough. Moving a slider does not scan the file again. Reloading the tab keeps the file, the edits, the pair, and the place in the text. A comparison keeps running if the tab reloads.

</details>

---

## Installation & Usage

### Architecture & Format Support

No desktop package is published. The container dev image is `linux/amd64` only.

| Format | x86_64 | arm64 |
| --- | --- | --- |
| `AppImage` | ❌ | ❌ |
| `Flatpak` | ❌ | ❌ |

| Architecture | Status |
| --- | --- |
| `x86_64` | ✅ `ghcr.io/yrmuq/kaimon:dev` |
| `arm64` | ❌ |

### Release Scheme

Stable releases are `X.Y.0`. A version `X.Y.Z` with `Z > 0` is an automatic dependency-update prerelease. No stable release has been published yet. The full list is on the [releases page](https://github.com/yrmuq/kaimon/releases).

### AppImage

Kaimon is not distributed as an AppImage.

### Flatpak

Flatpak is not available.

### Docker / Self-Hosted

The compose file is `docker-compose.yml`. It pulls `ghcr.io/yrmuq/kaimon:dev`, which GitHub builds on every push to `dev`. That tag is not the stable `latest` image.

```bash
docker compose pull
docker compose up -d
```

`.env`:

```
TZ=Europe/Amsterdam
KAIMON=8080
LOCATION=/opt/docker
```

| Container path | Purpose |
| --- | --- |
| `/data/files` | `.txt` notes shown in the side list |
| `/data/data` | Scan results and unsaved edits in `.temp` |

Put `.txt` files in `${LOCATION}/docker/data/kaimon/files`. Save writes a notes file there. Edits are also stored under `${LOCATION}/docker/data/kaimon/data` until Save, and offered again if the page or the container stops first. The model is inside the image.

---

## License & Attribution

Kaimon is released under the [GNU General Public License v3.0](https://www.gnu.org/licenses/gpl-3.0). See `LICENSE`.

| Component | Upstream | License | Integration Details |
| --- | --- | --- | --- |
| paraphrase-multilingual-mpnet-base-v2 | [sentence-transformers/paraphrase-multilingual-mpnet-base-v2](https://huggingface.co/sentence-transformers/paraphrase-multilingual-mpnet-base-v2) | Apache-2.0 | Local similarity model, baked into the image |
| FastEmbed | [qdrant/fastembed](https://github.com/qdrant/fastembed) | Apache-2.0 | Runs that model on CPU |
| RapidFuzz | [rapidfuzz/RapidFuzz](https://github.com/rapidfuzz/RapidFuzz) | MIT | Scores near-duplicate wording |
