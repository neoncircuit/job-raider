#!/bin/bash
# Records GPU, RAM, paging, committed memory, the vmmemWSL size, and the loaded
# Ollama models every 10 s, until a STOP file exists or 45 minutes pass.
# Windows host only (uses powershell.exe from WSL).
# Usage: bash profile_recorder.sh <output-dir>   (stop with: touch <output-dir>/STOP)
S="${1:?output directory required}"
OUT="$S/profile.csv"
rm -f "$S/STOP"
echo "time,gpu_mib,ram_free_gb,pages_per_sec,committed_gb,vmmem_gb,ollama_models" > "$OUT"
end=$((SECONDS + 2700))
while [ $SECONDS -lt $end ] && [ ! -f "$S/STOP" ]; do
  ts=$(date +%H:%M:%S)
  sys=$(powershell.exe -NoProfile -Command "\$g=(Get-Counter '\GPU Process Memory(*)\Dedicated Usage').CounterSamples; \$os=Get-CimInstance Win32_OperatingSystem; \$p=(Get-Counter '\Memory\Pages/sec').CounterSamples[0].CookedValue; \$c=(Get-Counter '\Memory\Committed Bytes').CounterSamples[0].CookedValue; \$v=(Get-Process vmmemWSL -ErrorAction SilentlyContinue | Measure-Object WorkingSet64 -Sum).Sum; '{0:F0},{1:F2},{2:F0},{3:F2},{4:F2}' -f ((\$g|Measure-Object CookedValue -Sum).Sum/1MB), (\$os.FreePhysicalMemory/1MB), \$p, (\$c/1GB), (\$v/1GB)" 2>/dev/null | tr -d '\r')
  models=$(ollama ps 2>/dev/null | tail -n +2 | awk '{print $1" "$3$4" "$5$6}' | paste -sd';' -)
  echo "$ts,$sys,${models:-none}" >> "$OUT"
  sleep 10
done
echo "stopped $(date +%H:%M:%S)" >> "$OUT"
