#!/bin/bash

# === PARSE FLAGS ===
enable_logging=false
for arg in "$@"; do
  if [[ "$arg" == "--log" ]]; then
    enable_logging=true
  fi
done

# === DEDUPE FUNCTION ===
dedupe() {
  local dry_run=$1
  local target_dir=$2

  echo "Deduping path: $target_dir (dry run: $dry_run)"

  if [[ "$dry_run" == "true" ]]; then
    rdfind -dryrun true "$target_dir"
  else
    rdfind -deleteduplicates true "$target_dir"
  fi
}

# === RUN DEDUPE PROMPT ===
echo
read -rp "Run deduplication before syncing? [y/N]: " run_dedupe
if [[ "$run_dedupe" =~ ^[Yy]$ ]]; then
  echo
  read -rp "Enter path to dedupe (e.g. /mnt/hdd/Movies): " dedupe_path
  read -rp "Dry run dedupe (no deletions)? [y/N]: " dedupe_dryrun

  dedupe_timestamp=$(date +"%Y-%m-%d_%H-%M-%S")
  dedupe_log="dedupe_$dedupe_timestamp.txt"

  echo
  echo "Running dedupe..."
  if [[ "$dedupe_dryrun" =~ ^[Yy]$ ]]; then
    if $enable_logging; then
      dedupe "true" "$dedupe_path" > "$dedupe_log" 2>&1
    else
      dedupe "true" "$dedupe_path"
    fi
  else
    if $enable_logging; then
      dedupe "false" "$dedupe_path" > "$dedupe_log" 2>&1
    else
      dedupe "false" "$dedupe_path"
    fi
  fi

  dedupe_exit_code=$?
  if [[ $dedupe_exit_code -ne 0 ]]; then
    if $enable_logging; then
      echo -e "\033[1;31mDeduplication failed (exit code $dedupe_exit_code). Check log: $dedupe_log\033[0m"
    else
      echo -e "\033[1;31mDeduplication failed (exit code $dedupe_exit_code).\033[0m"
    fi
    read -rp "Continue to sync anyway? [y/N]: " continue_after_dedupe
    if [[ ! "$continue_after_dedupe" =~ ^[Yy]$ ]]; then
      echo "Aborting sync."
      exit 1
    fi
  else
    echo -e "\033[1;32mDeduplication completed successfully.\033[0m"
    if $enable_logging; then
      echo -e "Log saved to: \033[1;34m$dedupe_log\033[0m"
    fi
  fi
fi

# === SYNC PROMPTS ===
echo "=========================="
echo " Movie Sync Script "
echo "=========================="
echo "1) Push to server (local → remote)"
echo "2) Pull from server (remote → local)"
echo

read -rp "Choose an option [1 or 2]: " choice

if [[ "$choice" == "1" ]]; then
  echo
  echo "You chose to PUSH files to the server."
  read -rp "Enter the full LOCAL source path: " source_path
  read -rp "Enter the REMOTE destination path (e.g. user@192.168.0.99:/mnt/hdd/): " destination_path

elif [[ "$choice" == "2" ]]; then
  echo
  echo "You chose to PULL files from the server."
  read -rp "Enter the REMOTE source path (e.g. user@192.168.0.100:/home/jasin/Movies/): " source_path
  read -rp "Enter the LOCAL destination path: " destination_path

else
  echo "Invalid option. Please run the script again and choose 1 or 2."
  exit 1
fi

echo
read -rp "Do a dry run first? [y/N]: " dry_run_choice
dry_run_flag=""
if [[ "$dry_run_choice" =~ ^[Yy]$ ]]; then
  dry_run_flag="--dry-run"
  echo "Performing dry run..."
else
  echo "Proceeding with real transfer..."
fi

echo
read -rp "Use sudo on the REMOTE side? [y/N]: " remote_sudo_choice
remote_sudo_flag=()
if [[ "$remote_sudo_choice" =~ ^[Yy]$ ]]; then
  remote_sudo_flag=(--rsync-path="sudo rsync")
fi

timestamp=$(date +"%Y-%m-%d_%H-%M-%S")
logfile="movie_sync_$timestamp.log"

echo
read -rp "Run in background with nohup? [Y/n]: " bg_choice
run_in_background=true
if [[ "$bg_choice" =~ ^[Nn]$ ]]; then
  run_in_background=false
fi

echo
echo -e "Legend: \033[1;34mInfo\033[0m | \033[1;32mSuccess\033[0m | \033[1;31mError/Deletion\033[0m"
echo

# Build rsync argument array
rsync_args=(-avh --progress)
if [[ -n "$dry_run_flag" ]]; then
  rsync_args+=("$dry_run_flag")
fi
if [[ ${#remote_sudo_flag[@]} -gt 0 ]]; then
  rsync_args+=("${remote_sudo_flag[@]}")
fi
rsync_args+=("$source_path" "$destination_path")

# Debug output
echo "Debug info:"
printf "rsync_args: '%s'\n" "${rsync_args[@]}"
echo

# === EXECUTE SYNC ===
if $run_in_background; then
  echo "Running in background with nohup..."
  if $enable_logging; then
    nohup rsync "${rsync_args[@]}" > "$logfile" 2>&1 &
    echo "Command is running in the background. You can monitor progress with:"
    echo "  tail -f $logfile"
  else
    nohup rsync "${rsync_args[@]}" &
    echo "Command is running in the background (no logging)."
  fi
else
  if $enable_logging; then
    rsync "${rsync_args[@]}" | tee "$logfile"
  else
    rsync "${rsync_args[@]}"
  fi
fi
