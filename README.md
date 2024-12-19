# Kahoot Bot
A bot to join Kahoot lobbies and vote randomly.

## Installation
1. Install Firefox
    * On Windows: Download installer [here](https://www.mozilla.org/da/firefox/new/)
    * On macOS: Download installer [here](https://www.mozilla.org/da/firefox/new/) or install with Homebrew: `brew install --cask firefox`
    * On Debian-based Linux distros: `sudo apt install firefox`
    * On Red Hat-based Linux distros: `sudo dnf install firefox`
    * On Arch Linux: `sudo pacman -S firefox`

2. Install Python dependencies with `pip3 install -r requirements.txt`
3. Run with `python3 -m kahooter <lobby_id> <bot_count> [--headless]`

## Usage
- `<lobby_id>` is the lobby ID
- `<bot_count>` is the number of bots to create
- `-h`, `--headless` is an optional flag to run the bots headless (no window appears)
- `-v`, `--verbose` is an optional flag to print debug messages
- `-no`, `--no-optimization` is an optional flag to disable optimization

Example: `python -m kahooter 4402901 5 --headless`
