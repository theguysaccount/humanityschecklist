# Humanity's Checklist

Source for [humanityschecklist.org](https://humanityschecklist.org): six things to fix so we can fix everything else.

Hundreds of billions of dollars go to charity every year. What if $5 million, spent correctly, was all it actually took? The world doesn't have a charity problem. It has a coordination, vision and status problem. The only effective altruism is systemic.

This project grew out of [Charitology](https://charitology.com), the study of charity.

## Contribute

Pull requests are welcome, from people and from AI agents. Start with [CONTRIBUTING.md](CONTRIBUTING.md); agents should read [AGENTS.md](AGENTS.md).

- `humanitys-checklist.html`: the main page; the six items live in `ITEMS` near the top of the script
- `questions.json`: the Questions page at [/questions/](https://humanityschecklist.org/questions/)
- `build.py`: builds the site into `docs/`; GitHub Actions runs it and deploys on every push to `main`

```bash
python3 build.py
python3 -m http.server 8000 --directory docs
```

## License

Code is under the [MIT License](LICENSE). Written content (the text of the site and `questions.json`) is under [Creative Commons Attribution 4.0](https://creativecommons.org/licenses/by/4.0/): share and adapt it freely with credit to Humanity's Checklist.
