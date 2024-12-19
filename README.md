# Kahoot Bot
A bot to join Kahoot lobbies and vote randomly.

## Installation
1. Install Chrome
- On Windows: Download installer [here](https://www.google.com/intl/en_US/chrome) or install with Chocolatey: `choco install googlechrome`
- On macOS: Download installer [here](https://www.google.com/intl/en_US/chrome) or install with Homebrew: `brew install --cask firefox`
- On Debian-based Linux distros: `sudo apt install google-chrome-stable`
- On Red Hat-based Linux distros:
```sh
sudo dnf install wget -y
wget https://dl.google.com/linux/direct/google-chrome-stable_current_x86_64.rpm
sudo dnf localinstall google-chrome-stable_current_x86_64.rpm -y
```
- On Arch based Linux distros:
```sh
sudo pacman -S --needed base-devel git
git clone https://aur.archlinux.org/yay-git.git
cd yay
makepkg -si
yay -S google-chrome
```

2. Install Python dependencies with `pip3 install -r requirements.txt`
3. Run with `python3 -m kahooter <lobby_id> <bot_count> [--headless]`

## Usage
- `<lobby_id>` is the lobby ID
- `<bot_count>` is the number of bots to create
- `-h`, `--headless` is an optional flag to run the bots headless (no window appears)
- `-v`, `--verbose` is an optional flag to print debug messages
- `-no`, `--no-optimization` is an optional flag to disable optimization

Example: `python -m kahooter 4402901 5 --headless`
