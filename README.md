# Movie Sync

**Can be used on any files, not just movies! (that totally aren't on a hosting site on a server somewhere...)**

A bash script to **deduplicate** and **sync** directories between local and remote machines. Easy UI in the terminal to simplify user transfers.

**Bonus**: Includes [optional media formatter](#media-formatter-bonus-tool) for clean file naming!

**Do you**

- Hate downloading/using another program to only FTP?
- Having duplicates in your data?
- Need to move files from your local to a remote server?

Well strap in because Movie Sync has got you covered!

---

## Features

- Deduplicate files in a directory using [`rdfind`](https://github.com/paulharry/rdfind) with optional dry-run and logging
- Sync files **to** or **from** a remote server using `rsync` with optional dry-run, sudo on remote, background execution, and logging
- All functionality combined in a single interactive script
- Logging for both deduplication and sync controlled by a single `--log` CLI flag

---

## Requirements

- Linux/macOS with bash shell
- [`rdfind`](https://github.com/paulharry/rdfind) installed and available in `$PATH`
- `rsync` installed
- SSH access configured for remote sync
- Optional: `sudo` rights on remote machine if you want to sync using remote sudo
- Optional: Python 3 for the media formatter script

---

## Usage

Make the script executable:

```bash
chmod +x movie-sync.sh
```

**Optional**: Format your media files first:

```bash
python3 format.py
```

Run the main script:

```bash
./movie-sync.sh [--log]
```

- Use `--log` to enable logging of dedupe and rsync output to timestamped log files.
- Without `--log`, no logs are saved.

The script will prompt you to:

1. Run deduplication (yes/no) and configure dry-run for dedupe
2. Choose Push (local → remote) or Pull (remote → local) mode
3. Enter source and destination paths
4. Choose dry-run for sync
5. Use sudo on remote side (yes/no)
6. Run sync in background (yes/no)

---

## Logs

If logging is enabled with `--log`:

- Deduplication logs are saved as `dedupe_YYYY-MM-DD_HH-MM-SS.txt`
- Rsync logs are saved as `movie_sync_YYYY-MM-DD_HH-MM-SS.log`

---

## Example

**Format media files first (optional):**

```bash
python3 format.py
```

**Then run with logging enabled:**

```bash
./movie-sync.sh --log
```

Sample interaction:

```
Run deduplication before syncing? [y/N]: y
Enter path to dedupe (e.g. /mnt/hdd/): /mnt/hdd/
Dry run dedupe (no deletions)? [y/N]: y
Choose an option [1 or 2]: 1
Enter the full LOCAL source path: /mnt/hdd/
Enter the REMOTE destination path (e.g. user@host:/path): user@192.168.0.2:/mnt/backup/Movies
Do a dry run first? [y/N]: n
Use sudo on the REMOTE side? [y/N]: n
Run in background with nohup? [Y/n]: n
```

---

## Screenshots

**Media Formatter in Action:**

```
🎬 Processing Media Directory: /mnt/movies
============================================================
├── 📁 Awesome.Action.Flick.2022.1080p.WEBRip → Awesome Action Flick (2022)
│   └── 🎥 Awesome.Action.Flick.2022.1080p.WEBRip.mp4 → Awesome Action Flick (2022).mp4
│   📝 Subtitle: Awesome.Action.Flick.2022.srt → Awesome Action Flick (2022).srt
│   🗑️  Removed: sample.txt
└── ⚠️  Found truncated year (20) - using 2020 as default
    📁 Comedy.Special.(20) → Comedy Special (2020)
    └── 🎥 Comedy.Special.(20).mkv → Comedy Special (2020).mkv
```

**Deduplication (Dry Run):**
![Deduplication Screenshot](images/dedupe.png)

**Rsync Syncing to Remote:**
![Sync Screenshot](images/sync.png)

---

## Media Formatter (Bonus Tool)

**🎬 Format your media files to standard naming convention before syncing!**

We've included an optional Python script `format.py` that formats your movie files and folders to the standard media naming convention: `Title (Year)`. This is super helpful to run **before** using the main sync script to ensure your media library is properly organized.

### What it does:

- ✅ Renames files and folders to `Title (Year)` format (e.g., `Action Hero Movie (2019)`)
- ✅ Handles truncated years like `(20)` → `(2020)` with smart defaults
- ✅ Organizes subtitle files and creates `Subs/` folders when needed
- ✅ Removes unwanted files (`.txt`, `.url`, `.jpg`, etc.)
- ✅ Cleans up release group tags (`[YTS]`, `[RARBG]`, etc.)
- ✅ Shows a nice tree view of changes being made

### Quick usage:

```bash
python3 format.py
```

Then enter your media directory path and confirm. The script will show you exactly what it's going to change before doing it.

**Tip**: Run this on your media files first, then use the main sync script to transfer your nicely formatted collection!

---

## License

MIT License — see [LICENSE](LICENSE) file.

---

## Contributions & Issues

Feel free to open issues or pull requests to improve the script!

---

Enjoy syncing your files hassle-free! 🎬🚀
