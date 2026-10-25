# Humanity's Checklist

Source for [humanityschecklist.com](https://humanityschecklist.com): six things to fix so we can fix everything else.

- `humanitys-checklist.html` is the page itself: content, styles and script in one file. The six items and their deep dives live in the `ITEMS` list near the top of the script.
- `build.sh` wraps it into a complete web page at `docs/index.html`, which GitHub Pages serves.

To change the site, edit `humanitys-checklist.html`, run `sh build.sh`, then commit and push.
