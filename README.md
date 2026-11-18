# The World in One Day — news-image-20261118

[![make.fun · news-image-20261118](https://make.fun/badge/news-image-20261118.svg)](https://make.fun/bounty/news-image-20261118?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261118)
[![rank](https://make.fun/badge/news-image-20261118/sudoRmMyLife/news-image-20261118/rank.svg)](https://make.fun/bounty/news-image-20261118/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261118)
[![reward](https://make.fun/badge/news-image-20261118/sudoRmMyLife/news-image-20261118/reward.svg)](https://make.fun/bounty/news-image-20261118?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261118)

My entry for the [news-image-20261118 bounty on make.fun](https://make.fun/bounty/news-image-20261118).

A one-image newspaper front page summing up the world news of the day
(see data.py for the stories, SOURCES.md for where each was reported).

Run it (Python 3.13, standard library only, no network):

    python3 main.py            # writes /output/entry.png
    MAKEFUN_OUTPUT_DIR=out python3 main.py   # writes out/entry.png

The program is deterministic: two runs write identical bytes.
main.py renders everything itself — paper, masthead, typography (glyph
bitmaps baked into fontdata.py at build time) and the lead illustration
are drawn programmatically. Output: 1024x1024 PNG, well under 1 MiB.
License: MIT (see LICENSE).
