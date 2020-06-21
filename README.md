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
