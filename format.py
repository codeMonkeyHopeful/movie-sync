#!/usr/bin/env python3
"""
Media File Formatter
Formats movie files and folders to standard naming convention: Title (Year)
Handles subtitles, removes unwanted files, and shows directory tree structure.
"""

# import os
import re
import shutil
from pathlib import Path
from typing import List, Tuple, Optional


class JellyfinFormatter:
    def __init__(self):
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

    def extract_title_year(self, filename: str) -> Optional[Tuple[str, str]]:
        """Extract title and year from filename."""
        # Remove file extension
        name = Path(filename).stem

        # Handle malformed names like "Title ( (2007)" - fix the double parentheses issue
        name = re.sub(r"\s*\(\s*\(\s*", " (", name)  # Replace " ( (" with " ("
        name = re.sub(r"\s*\)\s*\)\s*", ") ", name)  # Replace ") )" with ") "

        #        # Look for year pattern in parentheses: "Title (Year)" format
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

            print(
                f"    ⚠️  Found truncated year ({year_prefix}) - using {year_full} as default"
            )
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
                try:
                    file_path.unlink()
                    removed_files.append(str(file_path))
                    print(f"    🗑️  Removed: {file_path.name}")
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
            subs_dir.mkdir(exist_ok=True)

            # Move additional subtitles to Subs folder
            for i, sub_file in enumerate(subtitle_files[1:], 1):
                new_name = f"{movie_name}.{sub_file.suffix}"
                if i > 1:
                    new_name = f"{movie_name}.{i}{sub_file.suffix}"

                new_path = subs_dir / new_name
                try:
                    shutil.move(str(sub_file), str(new_path))
                    print(f"    📁 Moved to Subs/: {sub_file.name} → {new_name}")
                except Exception as e:
                    print(f"    ❌ Error moving subtitle: {e}")

        # Rename the main subtitle file to match movie name
        if subtitle_files:
            main_sub = subtitle_files[0]
            new_sub_name = f"{movie_name}{main_sub.suffix}"
            new_sub_path = movie_dir / new_sub_name

            if main_sub != new_sub_path:
                try:
                    main_sub.rename(new_sub_path)
                    print(f"    📝 Subtitle: {main_sub.name} → {new_sub_name}")
                except Exception as e:
                    print(f"    ❌ Error renaming subtitle: {e}")

    def process_directory(self, base_path: Path):
        """Process the entire directory structure."""
        if not base_path.exists():
            print(f"❌ Directory does not exist: {base_path}")
            return

        print(f"\n🎬 Processing Jellyfin Media Directory: {base_path}")
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
            try:
                file_path.rename(new_path)
                print(f"{prefix}📄 {file_path.name} → {new_name}")
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
            try:
                folder_path.rename(new_folder_path)
                print(f"{prefix}📁 {folder_path.name} → {formatted_name}")
                folder_path = new_folder_path
            except Exception as e:
                print(f"{prefix}❌ Error renaming folder: {e}")
                return
        else:
            print(f"{prefix}📁 {folder_path.name} (already formatted)")

        # Process folder contents
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
                try:
                    video_file.rename(new_video_path)
                    print(f"{item_prefix}🎥 {video_file.name} → {new_video_name}")
                except Exception as e:
                    print(f"{item_prefix}❌ Error renaming video: {e}")
            else:
                print(f"{item_prefix}✅ {video_file.name} (already formatted)")

        # Organize subtitles
        if video_files:
            self.organize_subtitles(folder_path, folder_name)


def main():
    """Main function to run the Jellyfin formatter."""
    print("🎬 Jellyfin Media Formatter")
    print("=" * 30)
    print("This script will format your media files to Jellyfin naming convention:")
    print("Format: Title (Year)")
    print("Example: Jojo Rabbit (2019)")
    print()

    # Get directory path from user
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

        if not directory_path.exists():
            print(f"❌ Directory does not exist: {directory_path}")
            continue

        if not directory_path.is_dir():
            print(f"❌ Path is not a directory: {directory_path}")
            continue

        break

    # Confirm before processing
    print(f"\n📂 Directory to process: {directory_path}")
    confirm = input("Do you want to proceed? (y/N): ").strip().lower()

    if confirm not in ["y", "yes"]:
        print("❌ Operation cancelled.")
        return

    # Process the directory
    formatter = JellyfinFormatter()
    formatter.process_directory(directory_path)

    print("\n✅ Processing completed!")
    print("Your media files have been formatted for Jellyfin.")


if __name__ == "__main__":
    main()
