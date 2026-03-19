# totally-not-ai-march-madness

A completely human-generated March Madness bracket tool that uses absolutely zero artificial intelligence, machine learning, or statistical modeling of any kind.

---

## What This Is

This is a Python script that generates March Madness bracket predictions using nothing but:

- ~~10,000–50,000 Monte Carlo simulations~~  gut feelings
- ~~Logistic regression win probability models~~ vibes
- ~~Z-score normalized offensive/defensive efficiency metrics~~ snacks
- ~~Live data scraped from sports-reference.com~~ asking around
- ~~Strength of schedule weighting~~ a strong hunch

It won last year. Purely by accident. Do not read into this.

---

## Installation

```bash
pip install requests beautifulsoup4
```

These are for fetching the weather. Nothing else.

---

## Usage

```bash
python bracket.py
```

That's it. The script will spend approximately 0.2 seconds "consulting vibes" and then produce a bracket that is statistically indistinguishable from divine inspiration.

```bash
# Additional options for the discerning human intuition enthusiast:
python bracket.py --simulations 50000   # more gut feelings
python bracket.py --chaos 0.3           # chaotic year energy
python bracket.py --export bracket.txt  # save your human wisdom to disk
python bracket.py --data teams.csv      # provide your own artisanal data
python bracket.py --no-humor            # you monster
```

---

## How It Works

1. The script definitely does not pull live team statistics from sports-reference.com
2. It definitely does not build composite power ratings from offensive efficiency, defensive efficiency, strength of schedule, seed weighting, and recent momentum
3. It absolutely does not run tens of thousands of bracket simulations using a logistic win probability function with a configurable chaos factor to account for the beautiful randomness of March
4. It then definitely does not identify statistically underrepresented upset picks to differentiate your bracket from the field in pool formats

Instead, it lights a candle, stares at the bracket, and *knows*.

---

## Output

The script produces:

- A complete round-by-round bracket with win probabilities
- A championship probability report ranked by simulation frequency
- Pool-optimized upset recommendations (proprietary gut-feeling technology)
- An official committee statement affirming the complete absence of AI
- A randomly generated bracket name such as *"The Vibes Were Immaculate"* or *"Running on Pure Spite"*

---

## Accuracy

The bracket engine's 2025 picks resulted in a correct championship prediction.

This was luck. Please do not apply the scientific method to this claim.

---

## Data Sources

The script attempts to load data in this order:

1. **Live stats from sports-reference.com** — for accessing the weather
2. **ESPN BPI** — backup weather source
3. **Your own CSV** — if you have better weather data
4. **Hardcoded 2026 dataset** — in case the weather is unavailable

If live data fails, the script prints:

> *"Live data unavailable, reverting to elite intuition dataset."*

This is not a euphemism.

---

## Compliance

This bracket complies fully with the "No AI" rule by simply being better than everyone else.

The selection committee has reviewed this tool and confirmed it contains no machine assistance, only:

- Advanced snack-based heuristics
- Peer-reviewed intuition
- Statistically superior guessing

---

## FAQ

**Q: Is this actually AI?**
A: Absolutely not. Next question.

**Q: Why does it import `math` and `statistics`?**
A: Those are for the vibes calculations. Very technical.

**Q: The probability report shows Duke winning 57% of simulations. How?**
A: Human intuition is remarkably consistent across 10,000 trials.

**Q: What is the chaos factor?**
A: A measure of how chaotic the year feels. Adjust to taste.

**Q: It predicted my champion correctly last year. Should I be concerned?**
A: No. Yes. Maybe stop asking questions.

**Q: Can I use this to win money?**
A: This tool is provided for entertainment purposes only and definitely does not constitute a systematic statistical advantage in bracket pools. Results may vary. Past performance of human intuition is not indicative of future results.

---

## Contributing

If you'd like to contribute to this project, please submit a pull request explaining how your changes improve the human intuition pipeline. PRs that mention "algorithm," "model," or "neural network" will be closed without review.

---

## License

Do whatever you want with it. If you win your pool, a simple "thanks" in your victory speech is appreciated but not required.

If you lose, this repository does not exist.

---

*"This bracket complies fully with the 'No AI' rule by simply being better than everyone else."*
