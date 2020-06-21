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
