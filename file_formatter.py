#!/usr/bin/env python3
"""
Media File Formatter
Formats movie files and folders to standard naming convention: Title (Year)
Handles subtitles, removes unwanted files, and shows directory tree structure.
"""

import argparse
import re
import shutil
from pathlib import Path
from typing import List, Tuple, Optional


class Colors:
    """ANSI color codes for terminal output"""
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    RESET = '\033[0m'
    BOLD = '\033[1m'


class JellyfinFormatter:
    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        
        # Video file extensions
        self.video_extensions = {
            ".mp4",
            ".mkv",
            ".avi",
            ".mov",
            ".wmv",
            ".flv",
            ".webm",
            ".m4v",
        }

        # Subtitle file extensions
        self.subtitle_extensions = {
            ".srt",
            ".sub",
            ".ass",
            ".ssa",
            ".vtt",
            ".idx",
            ".sup",
        }

        # Files to remove
        self.unwanted_extensions = {
            ".txt",
            ".url",
            ".lnk",
            ".nfo",
            ".jpg",
            ".jpeg",
            ".png",
            ".gif",
            ".bmp",
            ".exe",
            ".msi",
            ".zip",
            ".rar",
            ".7z",
        }

        # Common release group patterns to remove
        self.release_patterns = [
            r"\[.*?YTS.*?\]",
            r"\[.*?RARBG.*?\]",
            r"\[.*?1080p.*?\]",
            r"\[.*?720p.*?\]",
            r"\[.*?480p.*?\]",
            r"\[.*?WEBRip.*?\]",
            r"\[.*?BluRay.*?\]",
            r"\[.*?BRRip.*?\]",
            r"\[.*?HDRip.*?\]",
            r"\[.*?DVDRip.*?\]",
            r"\[.*?x264.*?\]",
            r"\[.*?x265.*?\]",
            r"\[.*?HEVC.*?\]",
            r"\[.*?5\.1.*?\]",
            r"\[.*?AAC.*?\]",
            r"\.1080p\.",
            r"\.720p\.",
            r"\.480p\.",
            r"\.WEBRip\.",
            r"\.BluRay\.",
            r"\.BRRip\.",
            r"\.HDRip\.",
            r"\.DVDRip\.",
            r"\.x264\.",
            r"\.x265\.",
            r"\.HEVC\.",
            r"\.AAC5?\.1",
            r"-\[YTS\.MX\]",
            r"-RARBG",
            r"\.YTS\.MX",
            r"\.RARBG",
        ]

    def print_action(self, prefix: str, old_name: str, new_name: str = None, action: str = "rename"):
        """Print an action with appropriate coloring"""
        if action == "delete":
            arrow = f"{Colors.RED} -> {Colors.RESET}"
            target = f"{Colors.RED}DELETE{Colors.RESET}"
            action_text = f"{Colors.RED}🗑️  Delete:{Colors.RESET}"
        else:  # rename/move
            arrow = f"{Colors.GREEN} -> {Colors.RESET}"
            target = f"{Colors.GREEN}{new_name}{Colors.RESET}"
            action_text = f"{Colors.GREEN}📝 Rename:{Colors.RESET}"
        
        if self.dry_run:
            print(f"{prefix}[DRY RUN] {action_text} {old_name}{arrow}{target}")
        else:
            if action == "delete":
                print(f"{prefix}🗑️  Removed: {old_name}")
            else:
                print(f"{prefix}📝 {old_name} → {new_name}")

    def extract_title_year(self, filename: str) -> Optional[Tuple[str, str]]:
        """Extract title and year from filename."""
        # Remove file extension
        name = Path(filename).stem

        # Handle malformed names like "Title ( (2007)" - fix the double parentheses issue
        name = re.sub(r"\s*\(\s*\(\s*", " (", name)  # Replace " ( (" with " ("
        name = re.sub(r"\s*\)\s*\)\s*", ") ", name)  # Replace ") )" with ") "

        # Look for year pattern in parentheses: "Title (Year)" format
        # First try to match 4-digit year
        year_in_parens = re.search(r"^(.+?)\s*\(\s*((19|20)\d{2})\s*\).*$", name)
        if year_in_parens:
            title = year_in_parens.group(1).strip()
            year_full = year_in_parens.group(2)
            # Clean up title
            for pattern in self.release_patterns:
                title = re.sub(pattern, "", title, flags=re.IGNORECASE)
            title = re.sub(r"[._]+", " ", title)
            title = re.sub(r"\s+", " ", title).strip()
            title = title.strip(" .-_()[]{}")
            return (title, year_full) if title else None

        # Handle truncated 2-digit years like "(19)" or "(20)"
        truncated_year = re.search(r"^(.+?)\s*\(\s*(19|20)\s*\).*$", name)
        if truncated_year:
            title = truncated_year.group(1).strip()
            year_prefix = truncated_year.group(2)

            # Try to guess the full year based on context
            # For "19" assume 1990s, for "20" assume 2020s (most recent decade)
            if year_prefix == "19":
                year_full = "1999"  # Default to late 90s
            else:  # year_prefix == "20"
                year_full = "2020"  # Default to 2020s

            # Clean up title
            for pattern in self.release_patterns:
                title = re.sub(pattern, "", title, flags=re.IGNORECASE)
            title = re.sub(r"[._]+", " ", title)
            title = re.sub(r"\s+", " ", title).strip()
            title = title.strip(" .-_()[]{}")

            warning_msg = f"    ⚠️  Found truncated year ({year_prefix}) - using {year_full} as default"
            if self.dry_run:
                print(f"[DRY RUN] {warning_msg}")
            else:
                print(warning_msg)
            return (title, year_full) if title else None

    def format_name(self, title: str, year: str) -> str:
        """Format title and year to Jellyfin standard."""
        return f"{title} ({year})"

    def get_tree_prefix(self, is_last: bool, is_item: bool = True) -> str:
        """Get the tree prefix for directory structure display."""
        if is_item:
            return "└── " if is_last else "├── "
        else:
            return "    " if is_last else "│   "

    def remove_unwanted_files(self, directory: Path) -> List[str]:
        """Remove unwanted files from directory."""
        removed_files = []

        for file_path in directory.rglob("*"):
            if (
                file_path.is_file()
                and file_path.suffix.lower() in self.unwanted_extensions
            ):
                removed_files.append(str(file_path))
                self.print_action("    ", file_path.name, action="delete")
                
                if not self.dry_run:
                    try:
                        file_path.unlink()
                    except Exception as e:
                        print(f"    ❌ Error removing {file_path.name}: {e}")

        return removed_files

    def organize_subtitles(self, movie_dir: Path, movie_name: str):
        """Organize subtitle files in movie directory."""
        subtitle_files = []

        # Find all subtitle files
        for file_path in movie_dir.iterdir():
            if (
                file_path.is_file()
                and file_path.suffix.lower() in self.subtitle_extensions
            ):
                subtitle_files.append(file_path)

        if not subtitle_files:
            return

        # Create Subs folder if needed and there are multiple subtitle files
        if len(subtitle_files) > 1:
            subs_dir = movie_dir / "Subs"
            
            if self.dry_run:
                print(f"    [DRY RUN] 📁 Create directory: Subs/")
            else:
                subs_dir.mkdir(exist_ok=True)

            # Move additional subtitles to Subs folder
            for i, sub_file in enumerate(subtitle_files[1:], 1):
                new_name = f"{movie_name}.{sub_file.suffix}"
                if i > 1:
                    new_name = f"{movie_name}.{i}{sub_file.suffix}"

                new_path = subs_dir / new_name
                self.print_action("    ", f"{sub_file.name}", f"Subs/{new_name}", "move")
                
                if not self.dry_run:
                    try:
                        shutil.move(str(sub_file), str(new_path))
                    except Exception as e:
                        print(f"    ❌ Error moving subtitle: {e}")

        # Rename the main subtitle file to match movie name
        if subtitle_files:
            main_sub = subtitle_files[0]
            new_sub_name = f"{movie_name}{main_sub.suffix}"
            new_sub_path = movie_dir / new_sub_name

            if main_sub.name != new_sub_name:
                self.print_action("    ", main_sub.name, new_sub_name)
                
                if not self.dry_run:
                    try:
                        main_sub.rename(new_sub_path)
                    except Exception as e:
                        print(f"    ❌ Error renaming subtitle: {e}")

    def process_directory(self, base_path: Path):
        """Process the entire directory structure."""
        if not base_path.exists():
            print(f"❌ Directory does not exist: {base_path}")
            return

        mode_text = f"{Colors.CYAN}[DRY RUN MODE]{Colors.RESET}" if self.dry_run else ""
        print(f"\n🎬 Processing Jellyfin Media Directory: {base_path} {mode_text}")
        print("=" * 60)

        # Get all items to process
        items = list(base_path.iterdir())
        items.sort(key=lambda x: (x.is_file(), x.name.lower()))

        for i, item_path in enumerate(items):
            is_last = i == len(items) - 1

            if item_path.is_file():
                self.process_file(item_path, is_last)
            elif item_path.is_dir():
                self.process_folder(item_path, is_last)

    def process_file(self, file_path: Path, is_last: bool = False):
        """Process a single file."""
        prefix = self.get_tree_prefix(is_last)

        # Skip if not a video file
        if file_path.suffix.lower() not in self.video_extensions:
            return

        # Extract title and year
        title_year = self.extract_title_year(file_path.name)
        if not title_year:
            print(f"{prefix}⚠️  Could not extract year: {file_path.name}")
            return

        title, year = title_year
        formatted_name = self.format_name(title, year)
        new_name = f"{formatted_name}{file_path.suffix}"
        new_path = file_path.parent / new_name

        if file_path.name != new_name:
            self.print_action(prefix, file_path.name, new_name)
            
            if not self.dry_run:
                try:
                    file_path.rename(new_path)
                except Exception as e:
                    print(f"{prefix}❌ Error renaming file: {e}")
        else:
            print(f"{prefix}✅ {file_path.name} (already formatted)")

    def process_folder(self, folder_path: Path, is_last: bool = False):
        """Process a folder and its contents."""
        prefix = self.get_tree_prefix(is_last)

        # Extract title and year from folder name
        title_year = self.extract_title_year(folder_path.name)
        if not title_year:
            print(f"{prefix}📁 {folder_path.name} (no year found)")
            self.process_folder_contents(folder_path, is_last, folder_path.name)
            return

        title, year = title_year
        formatted_name = self.format_name(title, year)
        new_folder_path = folder_path.parent / formatted_name

        # Rename folder if needed
        if folder_path.name != formatted_name:
            self.print_action(prefix, folder_path.name, formatted_name)
            
            if not self.dry_run:
                try:
                    folder_path.rename(new_folder_path)
                    folder_path = new_folder_path
                except Exception as e:
                    print(f"{prefix}❌ Error renaming folder: {e}")
                    return
            # In dry run mode, keep using the original folder_path since it still exists
        else:
            print(f"{prefix}📁 {folder_path.name} (already formatted)")

        # Process folder contents (use original folder_path in dry run, new path if actually renamed)
        self.process_folder_contents(folder_path, is_last, formatted_name)

    def process_folder_contents(
        self, folder_path: Path, is_last_folder: bool, folder_name: str
    ):
        """Process contents of a folder."""
        # Remove unwanted files first
        removed = self.remove_unwanted_files(folder_path)

        # Find video files
        video_files = []
        for file_path in folder_path.iterdir():
            if (
                file_path.is_file()
                and file_path.suffix.lower() in self.video_extensions
            ):
                video_files.append(file_path)

        # Process video files
        for i, video_file in enumerate(video_files):
            is_last_item = i == len(video_files) - 1
            child_prefix = "    " if is_last_folder else "│   "
            item_prefix = child_prefix + self.get_tree_prefix(is_last_item)

            # Rename video file to match folder name
            new_video_name = f"{folder_name}{video_file.suffix}"
            new_video_path = video_file.parent / new_video_name

            if video_file.name != new_video_name:
                self.print_action(item_prefix, video_file.name, new_video_name)
                
                if not self.dry_run:
                    try:
                        video_file.rename(new_video_path)
                    except Exception as e:
                        print(f"{item_prefix}❌ Error renaming video: {e}")
            else:
                print(f"{item_prefix}✅ {video_file.name} (already formatted)")

        # Organize subtitles
        if video_files:
            self.organize_subtitles(folder_path, folder_name)


def main():
    """Main function to run the Jellyfin formatter."""
    parser = argparse.ArgumentParser(
        description="Format media files for Jellyfin naming convention",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python jellyfin_formatter.py /path/to/movies
  python jellyfin_formatter.py --dry-run /path/to/movies
  python jellyfin_formatter.py -n /path/to/movies
        """
    )
    
    parser.add_argument(
        "directory",
        nargs="?",
        help="Directory path containing media files"
    )
    
    parser.add_argument(
        "--dry-run", "-n",
        action="store_true",
        help="Show what would be changed without making actual changes"
    )
    
    args = parser.parse_args()
    
    print("🎬 Jellyfin Media Formatter")
    print("=" * 30)
    print("This script will format your media files to Jellyfin naming convention:")
    print("Format: Title (Year)")
    print("Example: Jojo Rabbit (2019)")
    print()

    # Get directory path
    if args.directory:
        directory_path = Path(args.directory.strip("\"'"))
    else:
        while True:
            user_path = input(
                "Enter the directory path containing your media files: "
            ).strip()

            if not user_path:
                print("❌ Please enter a valid path.")
                continue

            # Handle quotes around path
            user_path = user_path.strip("\"'")
            directory_path = Path(user_path)
            break

    # Validate directory
    if not directory_path.exists():
        print(f"❌ Directory does not exist: {directory_path}")
        return

    if not directory_path.is_dir():
        print(f"❌ Path is not a directory: {directory_path}")
        return

    # Show dry run status
    if args.dry_run:
        print(f"\n📂 Directory to process: {directory_path}")
        print(f"{Colors.CYAN}🔍 DRY RUN MODE: No files will be modified{Colors.RESET}")
        print()
    else:
        # Confirm before processing in normal mode
        print(f"\n📂 Directory to process: {directory_path}")
        confirm = input("Do you want to proceed? (y/N): ").strip().lower()

        if confirm not in ["y", "yes"]:
            print("❌ Operation cancelled.")
            return

    # Process the directory
    formatter = JellyfinFormatter(dry_run=args.dry_run)
    formatter.process_directory(directory_path)

    if args.dry_run:
        print(f"\n{Colors.CYAN}🔍 DRY RUN COMPLETED!{Colors.RESET}")
        print("No files were actually modified. Run without --dry-run to apply changes.")
    else:
        print("\n✅ Processing completed!")
        print("Your media files have been formatted for Jellyfin.")


if __name__ == "__main__":
    main()
