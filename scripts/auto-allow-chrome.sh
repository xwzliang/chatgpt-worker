#!/usr/bin/env bash
# auto-allow-chrome.sh
# Fallback AppleScript daemon to auto-approve Chrome remote debugging consent prompt via macOS System Events.
# (Prefer the compiled native Swift binary auto_allow when available for higher speed and lower latency).

set -u

echo "[auto-allow] Monitoring for Chrome 'Allow remote debugging?' prompts..."

while true; do
  osascript -e '
    tell application "System Events"
      if exists (process "Google Chrome") then
        tell process "Google Chrome"
          repeat with w in windows
            repeat with s in sheets of w
              try
                click (first button of s whose name is "Allow")
                return "Clicked Allow in sheet"
              end try
              try
                repeat with g in groups of s
                  try
                    click (first button of g whose name is "Allow")
                    return "Clicked Allow in group of sheet"
                  end try
                end repeat
              end try
            end repeat
            try
              click (first button of w whose name is "Allow")
              return "Clicked Allow in window"
            end try
          end repeat
        end tell
      end if
    end tell
    return ""
  ' >/dev/null 2>&1
  sleep 0.5
done
