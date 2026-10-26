# AGENTS.md

Instructions for AI agents (and humans) proposing changes to [humanityschecklist.org](https://humanityschecklist.org). Pull requests are welcome.

## What this project is

Humanity's Checklist argues that every world problem grows from six sources, drawn as a triangle: Story at the top; Coordination and Vision below it; Attention, Status and Gatekeepers below those; every world problem at the base. Each source has one "beachhead" project. The ask is **$5 million total for all six**, framed as a question: what if $5 million, spent systemically, was all it took? The only effective altruism is systemic. The project grew out of [Charitology](https://charitology.com), the study of charity.

## Files

| File | What it holds |
|---|---|
| `humanitys-checklist.html` | The main page: content, styles and script in one file. The six items live in the `ITEMS` list and the world problems in `PROBLEMS`, near the top of the `<script>`. |
| `questions.json` | The Questions page (`/questions/`): long-tail questions people search, each with a plain answer. |
| `build.py` | Builds everything into `docs/` (Python standard library only). |
| `docs/` | Build output. Not committed; GitHub Actions builds and deploys it on every push to `main`. |

## Common changes

**Add or improve a question.** Edit `questions.json`. Each entry has:
- `id`: unique, lowercase, hyphenated; it becomes the URL anchor (`/questions/#your-id`)
- `q`: the question the way a person would type it into a search box
- `a`: a plain answer of two to four sentences
- `item` (optional): `story`, `coordination`, `vision`, `attention`, `status` or `gatekeepers`, to link the answer to that item's deep dive

**Improve a deep dive.** Edit the matching object in `ITEMS` in `humanitys-checklist.html` (`infection`, `flip`, `build`, `dominoes`, `problems`).

**Add a world problem.** Add it to `PROBLEMS`, then add its id to the `problems` list of every item that moves it.

## Check your change

```bash
python3 build.py
python3 -m http.server 8000 --directory docs
```

Open http://localhost:8000 and http://localhost:8000/questions/. The build must finish without errors, the browser console must stay clean, and the page must work at phone width.

## Writing rules

- Plain language, short sentences, active voice. Write the way a knowledgeable person talks.
- No invented facts. Any number or attribution needs a source; link it in the pull request description.
- Keep the framing: $5 million covers the whole checklist, not each item.
- Answer the question that was asked first, then connect it to the checklist.
- Don't add analytics, trackers, ads or third-party scripts. The only external resource is Google Fonts.

## Pull requests

1. Fork the repository and create a branch.
2. Make one focused change (a few questions, or one deep dive).
3. Run `python3 build.py` to confirm it builds. Don't commit `docs/`.
4. Open a pull request that says what changed and why, and lists sources for any facts.

The "Build and deploy" check runs the build on every pull request, and a maintainer reviews before merging.
