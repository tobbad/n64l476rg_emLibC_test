#!/bin/bash
# zip_sources.sh
#
# Erstellt ein ZIP mit allen Dateien, die bestimmte Endungen haben
# (inkl. versteckter Dateien mit Punkt vorne).
# Blacklist blendet typische Build-Ordner und Artefakte aus.

if [ "$#" -lt 2 ]; then
    echo "Usage: $0 output.zip ext1 [ext2 ...]"
    exit 1
fi

OUTPUT="$1"
shift   # erster Parameter = Ziel-Archiv
EXTS=("$@")

# Sicherstellen, dass OUTPUT auf .zip endet
if [[ "$OUTPUT" != *.zip ]]; then
    OUTPUT="${OUTPUT}.zip"
fi

EXCLUDE_DIRS=(.git build debug  out .idea .vscode)
EXCLUDE_FILES=("*.o" "*.a" "*.so" "*.exe" "*.class")

TMPFILE=$(mktemp)

# Dateien mit den gewünschten Endungen sammeln
for ext in "${EXTS[@]}"; do
    find . \( -type f -o -type l \) \
        \( -name "*.${ext}" -o -name ".*.${ext}" \) \
        $(for d in "${EXCLUDE_DIRS[@]}"; do echo "-not -path \"./$d/*\""; done) \
        $(for f in "${EXCLUDE_FILES[@]}"; do echo "-not -name \"$f\""; done) \
        >> "$TMPFILE"
done

# ZIP erstellen
if [ -s "$TMPFILE" ]; then
    zip -r "$OUTPUT" -@ < "$TMPFILE"
    echo "Archiv erstellt: $OUTPUT"
else
    echo "Keine Dateien mit den angegebenen Endungen gefunden."
fi

rm -f "$TMPFILE"
