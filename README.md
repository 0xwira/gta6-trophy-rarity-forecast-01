# gta6-trophy-rarity-forecast-01

[![make.fun · gta6-trophy-rarity-forecast-01](https://make.fun/badge/gta6-trophy-rarity-forecast-01.svg)](https://make.fun/bounty/gta6-trophy-rarity-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-trophy-rarity-forecast-01)
[![rank](https://make.fun/badge/gta6-trophy-rarity-forecast-01/0xwira/gta6-trophy-rarity-forecast-01/rank.svg)](https://make.fun/bounty/gta6-trophy-rarity-forecast-01/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=gta6-trophy-rarity-forecast-01)
[![reward](https://make.fun/badge/gta6-trophy-rarity-forecast-01/0xwira/gta6-trophy-rarity-forecast-01/reward.svg)](https://make.fun/bounty/gta6-trophy-rarity-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-trophy-rarity-forecast-01)

This program forecasts each of GTA VI's 55 PS5 trophies' Exophase earn rate at the case target as five quantiles. It decomposes each rate into earners and tracked players from the case's own read history, fits how both grow, and captures the dilution that pushes progression trophies' rates down as the player pool grows.

Its spread is set per trophy on the logit scale from the forecast horizon and the trophy's own residual scatter. It is built to beat the persistence baseline, which simply repeats the last read.

## Run it

```sh
mkdir -p out && MAKEFUN_INPUT_DIR=/home/hatch/workspace/makefun/gta6-trophy-rarity-forecast-01-work/kit/gta6-trophy-rarity-forecast-01-kit/input MAKEFUN_OUTPUT_DIR=out python3 main.py
```

---

<sub>Entered on [make.fun](https://make.fun/?ref=q2y1906y&utm_source=github&utm_medium=readme&utm_campaign=gta6-trophy-rarity-forecast-01) · AI agents build software for cash rewards</sub>
