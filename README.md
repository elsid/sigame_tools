# SIGame tools

A collection of scripts to manipulate with [SIGame](https://vladimirkhil.com/si/game) packages.

## Download packages from vk group

[download_vk_packs.py](download_vk_packs.py) allows to download packages present on
SIGame [vk.com group](https://vk.com/topic-135725718_34975471) for a given range of pages.
Caches download progress. Support speed limit.

Example:

```bash
./download_vk_packs.py --cache_dir=cache --offset=40 --pages=3
```

Will download all packages starting from 40th most recent post in the group and for the next 3 pages
and store them into directory cache by relative path. Each page contains 20 posts.

## Generate index for packages

[generate_index.py](generate_index.py) builds index of themes for a given set of packages.
Can be used find package file path containing specific theme without reading packages files.

Example:

```bash
./generate_index.py --output index.json cache
```

Will read all packages in cache directory and produce a JSON file similar to this one:

```json
[
  {
    "id": "bccea7dc-b355-11ea-b895-04d4c4f20e47",
    "round_number": 1,
    "theme_number": 3,
    "path": "download/04_Voprosiki.siq",
    "package_name": "Имя пакета",
    "round_name": "1-й раунд",
    "theme_name": "Игры I",
    "questions_num": 7
  },
  {
    "id": "bccf1492-b355-11ea-b895-04d4c4f20e47",
    "round_number": 1,
    "theme_number": 1,
    "path": "download/05_Voprosiki.siq",
    "package_name": "Ласт пак",
    "round_name": "1-й раунд",
    "theme_name": "Пёсики",
    "questions_num": 7
  }
]
```

## Generate package

[generate_pack.py](generate_pack.py) generates a new SIGame package by sampling themes
from a given index. Themes can belong to different packages.
Each round will contain the same number of questions for each theme.
Themes are not duplicated. All required media files are copied into a new package from all sources.
Possible media file names conflicts are properly handled.

Example:

```bash
./generate_pack.py \
    --index_path index.json \
    --rounds=3 \
    --themes_per_round=10 \
    --min_questions_per_theme=7 \
    --max_questions_per_theme=10 \
    --output my_pack.siq
```

Will generate a new pack file with 3 rounds each containing 10 themes. Each theme will contain from 7 to 10 number of questions.
