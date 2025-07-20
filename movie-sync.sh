#!/bin/bash

# === PARSE FLAGS ===
debug=false
enable_logging=false
for arg in "$@"; do
  if [[ "$arg" == "--log" ]]; then
    enable_logging=true
  fi
  if [[ "$arg" == "--debug" ]]; then
    debug=true
  fi
done

# === GLOBAL VARIABLE FOR LOCAL PATH MEMORY ===
remembered_local_path=""

# === PROMPT WITH DEFAULT FUNCTION ===
prompt_with_default() {
  local prompt_text="$1"
  local default_value="$2"
  local result_var="$3"

  if [[ -n "$default_value" ]]; then
    echo -n "$prompt_text [Press enter for: $default_value]: "
  else
    echo -n "$prompt_text: "
  fi

  read -r user_input

  if [[ -z "$user_input" ]] && [[ -n "$default_value" ]]; then
    eval "$result_var=\"$default_value\""
  else
    eval "$result_var=\"$user_input\""
  fi
}

# === FUNCTION TO CHECK AND REMEMBER LOCAL PATH ===
remember_local_path() {
  local path="$1"

  # Check if this looks like a local path (not remote with user@host: format)
  if [[ ! "$path" =~ ^[^@]+@[^:]+: ]] && [[ -n "$path" ]]; then
    if [[ -z "$remembered_local_path" ]]; then
      remembered_local_path="$path"
      echo "📝 Remembered local path: $remembered_local_path"
    fi
  fi
}

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

# === ANALYZE RSYNC OUTPUT FUNCTION ===
analyze_rsync_output() {
  local rsync_output_file=$1
  local source_path=$2
  declare -a successful_transfers=()
  declare -a failed_transfers=()

  if [[ ! -f "$rsync_output_file" ]]; then
    echo "⚠️ Warning: Could not find rsync output file for analysis"
    return 1
  fi

  if [[ "$debug" == "true" ]] then
    echo "🔍 Debug: Analyzing rsync output from: $rsync_output_file"
  fi

  # Parse rsync output to identify successful vs failed transfers
  local in_file_list=false
  while IFS= read -r line; do
    # Skip empty lines
    [[ -z "$line" ]] && continue

    # Detect start of file list
    if [[ "$line" == "sending incremental file list" ]]; then
      in_file_list=true
      continue
    fi

    # Skip lines before file list starts
    if [[ "$in_file_list" == false ]]; then
      continue
    fi

    # Skip summary lines at the end
    if [[ "$line" =~ ^sent\ [0-9] ]] || [[ "$line" =~ ^total\ size ]] || [[ "$line" =~ speedup ]]; then
      break
    fi

    # Look for error lines
    if [[ "$line" =~ rsync:.*error ]] || [[ "$line" =~ failed ]] || [[ "$line" =~ "cannot" ]]; then
      failed_transfers+=("$line")
      echo "❌ Found error: $line"
      continue
    fi

    # Look for file/directory entries
    # Files with transfer info look like: "filename    size  100%  speed  time (xfr#n, to-chk=n/n)"
    # Directories look like: "dirname/"
    # Plain files without size info are just listed as: "filename"
    # Transfer progress lines look like: "          1.66G  99%   15.44MB/s    0:00:00"

    # Skip pure transfer progress lines (start with whitespace and contain only numbers/units/percentages)
    if [[ "$line" =~ ^[[:space:]]+[0-9.,]+[KMGT]?[[:space:]]+[0-9]+%[[:space:]]+[0-9.,]+[KMGT]?B/s ]]; then
      echo "⏭️ Skipping transfer progress line: $line"
      continue
    fi

    if [[ "$line" =~ ^[[:space:]]*(.+/)$ ]]; then
      # Directory entry (ends with /)
      filename="${BASH_REMATCH[1]}"
      # Remove trailing slash for directory name
      filename="${filename%/}"
      if [[ -n "$filename" && "$filename" != "./" && "$filename" != "." ]]; then
        successful_transfers+=("$filename")
        echo "📁 Found directory: $filename"
      fi
    elif [[ "$line" =~ ^[[:space:]]*([^[:space:]]+.*[^/])$ ]] && [[ ! "$line" =~ "100%" ]] && [[ ! "$line" =~ ^[[:space:]]+[0-9.,]+[KMGT]? ]]; then
      # File entry without transfer stats (just filename) - but exclude lines that start with size info
      filename="${BASH_REMATCH[1]}"
      if [[ -n "$filename" && "$filename" != "./" && "$filename" != "." ]]; then
        successful_transfers+=("$filename")
        echo "📄 Found file: $filename"
      fi
    elif [[ "$line" =~ ^([^[:space:]]+.+)[[:space:]]+[0-9.,]+[KMGT]?[[:space:]]+100% ]]; then
      # File entry with transfer stats (has size and 100%) - filename comes first
      filename="${BASH_REMATCH[1]}"
      if [[ -n "$filename" && "$filename" != "./" && "$filename" != "." ]]; then
        successful_transfers+=("$filename")
        echo "📄 Found transferred file: $filename"
      fi
    fi
  done < "$rsync_output_file"

  if [[ "$debug" == "true" ]] then
    echo "🔍 Debug: Found ${#successful_transfers[@]} successful transfers, ${#failed_transfers[@]} failures"
  fi

  # Export arrays for use in main script
  printf '%s\n' "${successful_transfers[@]}" > /tmp/successful_transfers.txt

  # Only create failed_transfers file if there are actually failures
  if [[ ${#failed_transfers[@]} -gt 0 ]]; then
    printf '%s\n' "${failed_transfers[@]}" > /tmp/failed_transfers.txt
  else
    # Remove any existing failed transfers file to ensure clean state
    rm -f /tmp/failed_transfers.txt
  fi

  # Debug output
  if [[ "$debug" == "true" ]] then
    if [[ ${#successful_transfers[@]} -gt 0 ]]; then
      echo "🔍 Debug: Successful transfers written to /tmp/successful_transfers.txt:"
      cat /tmp/successful_transfers.txt
    fi
  fi
}

# === DELETE SUCCESSFUL TRANSFERS FUNCTION ===
delete_successful_files() {
  local source_path=$1
  local logfile=$2
  declare -a deleted_items=()
  declare -a kept_items=()
  local delete_count=0
  local keep_count=0

  # Function to output to both stdout and logfile
  log_and_echo() {
    local message="$1"
    echo "$message"
    if [[ -n "$logfile" ]] && [[ -n "$2" ]]; then
      echo "$message" >> "$2"
    fi
  }

  log_and_echo "🗑️ DELETION SUMMARY:"
  log_and_echo "============================================================"

  if [[ ! -f /tmp/successful_transfers.txt ]]; then
    log_and_echo "❌ No transfer data available for deletion analysis"
    return 1
  fi

  log_and_echo "✅ Successfully transferred and deleting:"

  # Read successful transfers and attempt deletion
  while IFS= read -r item; do
    [[ -z "$item" ]] && continue

    local full_path="$source_path/$item"

    if [[ -d "$full_path" ]]; then
      # It's a directory
      if rm -rf "$full_path" 2>/dev/null; then
        log_and_echo "├── 🗑️ Deleted folder: $item"
        deleted_items+=("$item")
        ((delete_count++))
      else
        log_and_echo "├── ❌ Failed to delete folder: $item"
        kept_items+=("$item")
        ((keep_count++))
      fi
    elif [[ -f "$full_path" ]]; then
      # It's a file
      if rm "$full_path" 2>/dev/null; then
        log_and_echo "└── 🗑️ Deleted file: $item"
        deleted_items+=("$item")
        ((delete_count++))
      else
        log_and_echo "└── ❌ Failed to delete file: $item"
        kept_items+=("$item")
        ((keep_count++))
      fi
    fi
  done < /tmp/successful_transfers.txt

  # Show items kept due to transfer failures
  if [[ -f /tmp/failed_transfers.txt ]] && [[ -s /tmp/failed_transfers.txt ]]; then
    log_and_echo ""
    log_and_echo "❌ Transfer failures - NOT deleted (kept on local machine):"
    while IFS= read -r failure; do
      [[ -z "$failure" ]] && continue
      log_and_echo "└── ❌ Kept due to transfer failure: $failure"
      ((keep_count++))
    done < /tmp/failed_transfers.txt
  fi

  log_and_echo ""
  if [[ $keep_count -gt 0 ]]; then
    log_and_echo "⚠️ Summary: $delete_count items deleted, $keep_count items kept due to failures."
  else
    log_and_echo "✅ Summary: $delete_count items deleted successfully, no failures!"
  fi

  # Cleanup temp files
  rm -f /tmp/successful_transfers.txt /tmp/failed_transfers.txt
}

# === RUN DEDUPE PROMPT ===
echo
read -rp "Run deduplication before syncing? [y/N]: " run_dedupe
if [[ "$run_dedupe" =~ ^[Yy]$ ]]; then
  echo

  # Use the remembered local path as default for dedupe prompt
  dedupe_path=""
  prompt_with_default "Enter path to dedupe (e.g. /mnt/hdd/Movies)" "$remembered_local_path" "dedupe_path"

  # Remember this path if it's local and we don't have one yet
  remember_local_path "$dedupe_path"

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

  # Use remembered local path as default for source path
  source_path=""
  prompt_with_default "Enter the full LOCAL source path" "$remembered_local_path" "source_path"

  # Remember this path since it's local
  remember_local_path "$source_path"

  # Auto-adjust trailing slash for directories (rsync behavior optimization)
  if [[ -d "$source_path" ]] && [[ "$source_path" != */ ]]; then
    source_path="$source_path/"
    echo "📁 Detected directory - adjusted path to: $source_path"
    remember_local_path "$source_path"
  fi

  read -rp "Enter the REMOTE destination path (e.g. user@192.168.0.99:/mnt/hdd/): " destination_path

elif [[ "$choice" == "2" ]]; then
  echo
  echo "You chose to PULL files from the server."
  read -rp "Enter the REMOTE source path (e.g. user@192.168.0.100:/home/jasin/Movies/): " source_path

  # Use remembered local path as default for destination path
  destination_path=""
  prompt_with_default "Enter the LOCAL destination path" "$remembered_local_path" "destination_path"

  # Remember this path since it's local
  remember_local_path "$destination_path"

  # Auto-adjust trailing slash for local destination directories
  if [[ -d "$destination_path" ]] && [[ "$destination_path" != */ ]]; then
    destination_path="$destination_path/"
    echo "📁 Detected directory - adjusted path to: $destination_path"
    remember_local_path "$destination_path"
  fi

else
  echo "Invalid option. Please run the script again and choose 1 or 2."
  exit 1
fi

# === NEW: DELETE ORIGINAL FILES PROMPT ===
echo
read -rp "Delete original files after successful transfer? [y/N]: " delete_originals
delete_after_transfer=false
if [[ "$delete_originals" =~ ^[Yy]$ ]]; then
  delete_after_transfer=true
  echo "🗑️ Will delete originals after successful transfer"
else
  echo "📁 Will keep original files after transfer"
fi

echo
read -rp "Do a dry run first? [y/N]: " dry_run_choice
dry_run_flag=""
if [[ "$dry_run_choice" =~ ^[Yy]$ ]]; then
  dry_run_flag="--dry-run"
  echo "Performing dry run..."
  if $delete_after_transfer; then
    echo "⚠️ Note: Dry run mode - no files will be deleted regardless of delete setting"
    delete_after_transfer=false
  fi
else
  echo "Proceeding with real transfer..."
fi

echo
read -rp "Use sudo on the REMOTE side? [y/N]: " remote_sudo_choice
remote_sudo_flag=()
if [[ "$remote_sudo_choice" =~ ^[Yy]$ ]]; then
  remote_sudo_flag=(--rsync-path="sudo rsync")
fi

echo
read -rp "Run in background with nohup? [Y/n]: " bg_choice
run_in_background=true
create_logfile=false
logfile=""

if [[ "$bg_choice" =~ ^[Nn]$ ]]; then
  run_in_background=false
  create_logfile=false
  echo "Will run in foreground with output to screen only"
else
  echo
  read -rp "Log background process to file? [y/N]: " log_choice
  if [[ "$log_choice" =~ ^[Yy]$ ]]; then
    create_logfile=true
    timestamp=$(date +"%Y-%m-%d_%H-%M-%S")
    logfile="movie_sync_$timestamp.log"
    echo "Will run in background with logging to: $logfile"
  else
    create_logfile=false
    echo "Will run in background with no logging (silent mode)"
  fi
fi

# === DISPLAY PROCESSING INFO ===
echo
echo "🎬 Processing Jellyfin Media Directory: $source_path"
if [[ "$choice" == "1" ]]; then
  echo "📤 Server destination: $destination_path"
else
  echo "📥 Local destination: $destination_path"
fi
if $delete_after_transfer; then
  echo "🗑️ Will delete originals after successful transfer"
fi
echo "============================================================"

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
if [[ "$debug" == "true" ]] then
  echo "Debug info:"
  printf "rsync_args: '%s'\n" "${rsync_args[@]}"
  echo
fi

# === EXECUTE SYNC ===
rsync_exit_code=0
temp_rsync_output=""

if $run_in_background; then
  echo "Running in background with nohup..."
  if $create_logfile; then
    nohup rsync "${rsync_args[@]}" > "$logfile" 2>&1 &
    rsync_pid=$!
    echo "Command is running in the background (PID: $rsync_pid). You can monitor progress with:"
    echo "  tail -f $logfile"
    temp_rsync_output="$logfile"

    if $delete_after_transfer; then
      echo
      echo "⏳ Waiting for rsync to complete before processing deletions..."
      wait $rsync_pid
      rsync_exit_code=$?
    fi
  else
    # Even in silent mode, capture output to temp file for deletion analysis if needed
    if $delete_after_transfer; then
      temp_rsync_output="/tmp/rsync_output_$(date +%s).txt"
      nohup rsync "${rsync_args[@]}" > "$temp_rsync_output" 2>&1 &
      rsync_pid=$!
      echo "Command is running in the background silently (PID: $rsync_pid)."
      echo
      echo "⏳ Waiting for rsync to complete before processing deletions..."
      wait $rsync_pid
      rsync_exit_code=$?
    else
      nohup rsync "${rsync_args[@]}" >/dev/null 2>&1 &
      rsync_pid=$!
      echo "Command is running in the background silently (PID: $rsync_pid, no logging)."
    fi
  fi
else
  # Foreground mode - capture output to temp file for deletion analysis if needed
  if $delete_after_transfer; then
    temp_rsync_output="/tmp/rsync_output_$(date +%s).txt"
    rsync "${rsync_args[@]}" | tee "$temp_rsync_output"
    rsync_exit_code=${PIPESTATUS[0]}
  else
    rsync "${rsync_args[@]}"
    rsync_exit_code=$?
  fi
fi

# === HANDLE POST-SYNC DELETION ===
if $delete_after_transfer && [[ $rsync_exit_code -eq 0 ]]; then
  echo
  echo "📋 Analyzing transfer results for deletion processing..."

  # Only proceed with deletion for push operations (choice 1) since we're deleting from local
  if [[ "$choice" == "1" ]]; then
    if [[ -n "$temp_rsync_output" ]] && [[ -f "$temp_rsync_output" ]]; then
      analyze_rsync_output "$temp_rsync_output" "$source_path"
      delete_successful_files "$source_path" "$logfile"

      # Cleanup temp file if it's not the user's log file
      if [[ "$temp_rsync_output" != "$logfile" ]]; then
        rm -f "$temp_rsync_output"
      fi
    else
      echo "⚠️ No rsync output available for deletion analysis."
    fi
  else
    echo "⚠️ Note: Deletion only supported for push operations (local → remote)"
  fi
elif $delete_after_transfer && [[ $rsync_exit_code -ne 0 ]]; then
  echo
  echo "❌ Rsync failed (exit code: $rsync_exit_code). Skipping deletion for safety."

  # Cleanup temp file
  if [[ -n "$temp_rsync_output" ]] && [[ "$temp_rsync_output" != "$logfile" ]]; then
    rm -f "$temp_rsync_output"
  fi
fi

echo
echo "🎉 Sync operation completed!"
