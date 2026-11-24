#!/bin/bash
file="$1"
dir=$(dirname "$file")
base=$(basename "$file")
new_base=$(echo "$base" | sed 's/[ @^()]/_/g')
new_file="$dir/$new_base"

if [[ "$file" != "$new_file" ]]; then
    echo "Renaming '$file' to '$new_file'"
    mv "$file" "$new_file"
fi
