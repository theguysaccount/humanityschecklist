#!/bin/sh
# Wraps humanitys-checklist.html in a full HTML document for static hosting.
# Writes docs/index.html and docs/CNAME, the folder GitHub Pages serves.
# Usage: sh build.sh
set -e
cd "$(dirname "$0")"
SRC=humanitys-checklist.html
OUT=docs
mkdir -p "$OUT"

{
  cat <<'EOF'
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="description" content="Every world problem grows from a few sources. Humanity's Checklist names the six, the beachhead that flips each one, and why $5 million apiece is the most effective systemic giving there is.">
<meta property="og:type" content="website">
<meta property="og:url" content="https://humanityschecklist.com/">
<meta property="og:title" content="Humanity's Checklist">
<meta property="og:description" content="Six things to fix so we can fix everything else.">
<meta name="twitter:card" content="summary">
<meta name="twitter:title" content="Humanity's Checklist">
<meta name="twitter:description" content="Six things to fix so we can fix everything else.">
<meta name="theme-color" content="#EDF1ED" media="(prefers-color-scheme: light)">
<meta name="theme-color" content="#0B1613" media="(prefers-color-scheme: dark)">
<link rel="canonical" href="https://humanityschecklist.com/">
<link rel="icon" type="image/svg+xml" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='-3 -4.6 30 30'><rect x='-3' y='-4.6' width='30' height='30' rx='7' fill='%23EDF1ED'/><polygon points='12,0 18,10.39 6,10.39' fill='%23D23560'/><polygon points='6,10.39 12,20.78 0,20.78' fill='%230F2621'/><polygon points='18,10.39 24,20.78 12,20.78' fill='%230F2621'/></svg>">
EOF
  # The page's own head material: everything up to and including </style>.
  awk '{ print } /<\/style>/ { exit }' "$SRC" | grep -v 'claude:viewport-fit-sides'
  printf '</head>\n<body>\n'
  awk 'seen { print } /<\/style>/ { seen = 1 }' "$SRC"
  printf '</body>\n</html>\n'
} > "$OUT/index.html"

printf 'humanityschecklist.com\n' > "$OUT/CNAME"
echo "Built $OUT/index.html ($(wc -c < "$OUT/index.html" | tr -d ' ') bytes)"
