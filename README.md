# SIGame tools

A collection of scripts to manipulate with [SIGame](https://vladimirkhil.com/si/game) packages.

## Download packages from vk group

[download_vk_packs.py](download_vk_packs.py) allows to download packages present on
SIGame [vk.com group](https://vk.com/topic-135725718_34975471) for a given range of pages.
Caches download progress. Support speed limit.

### Usage example

```bash
./download_vk_packs.py --cache_dir=cache --offset=40 --pages=3
```

Will download all packages starting from 40th most recent post in the group and for the next 3 pages
and store them into directory cache by relative path. Each page contains 20 posts.

## Generate index for packages

[generate_index.py](generate_index.py) builds index of themes for a given set of packages.
Can be used find package file path containing specific theme without reading packages files.

### Usage example

```bash
./generate_index.py --output index.json cache
```

Will read all packages in cache directory and produce a JSON file similar to this one:

```json
{
    "version": 1,
    "themes": [
        {
            "id": "ce44f7ec-b3d1-11ea-a01c-04d4c4f20e47",
            "round_number": 1,
            "theme_number": 1,
            "path": "cache/Package_2010_11.siq",
            "package_name": "2010_11",
            "round_name": "1-й раунд",
            "theme_name": "ФРАНЦУЗКИЕ ПИИТЫ",
            "questions_num": 5,
            "authors": [
                "Александр Ланин",
                "Владимир Хиль",
                "Михаил Перлин"
            ],
            "base64_encoded_right_answers": [
                "0JbQsNC90L3QsCDQlCfQkNGA0Lo=",
                "0JDRgNCw0LzQuNGB",
                "0KTRgNCw0L3RgdGD0LAg0JLQuNC50L7QvQ==",
                "0JLQuNC50L7QvQ==",
                "0K3QstCw0YDQuNGB0YIg0J/QsNGA0L3QuA==",
                "0J/QsNGA0L3QuA==",
                "0JzQsNGA0Y0="
            ],
            "round_type": null
        }
    ]
}
```

## Generate package

[generate_pack.py](generate_pack.py) generates a new SIGame package by sampling themes
from a given index. Themes can belong to different packages.
Each round will contain the same number of questions for each theme.
Themes are not duplicated. All required media files are copied into a new package from all sources.
Possible media file names conflicts are properly handled.

### Filters

Format: `--filter <include|exclude|force_include> <file_name> <pattern>`

By default all themes are filtered in. `include` or `force_include` will filter out all themes that does not match
pattern for a given `field_name`. But multiple includes create union across the same and different fields:

```bash
--filter include theme_name physics
--filter include theme_name mathematics
```

will filter in both themes `physics` and `mechanics`.

```bash
--filter include theme_name physics
--filter include file_name mathematics_pack
```

will filter in theme `physics` and pack `mathematics_pack`.

`exclude` will filter in a theme even if there is an explicit include:

```bash
--filter include theme_name physics
--filter exclude theme_name physics
```

will filter out `physics`.

Excludes also create union:

```bash
--filter exclude theme_name physics
--filter exclude theme_name mathematics
```

will filter out `physics` and `mathematics`.

`force_include` works as `include` but increase priority for a theme to be added to generated package.

`pattern` can be regular expression for strings or exact value for integers. For lists pattern is used to match one of the values inside the list.

### Usage example

```bash
./generate_pack.py \
    --index_path index.json \
    --rounds=3 \
    --themes_per_round=10 \
    --min_questions_per_theme=7 \
    --max_questions_per_theme=10 \
    --output my_pack.siq \
    --filter force_include file_name 'Physics' \
    --filter include theme_name 'Mechanics' \
    --filter exclude theme_name 'Quantum' \
```

Will generate a new pack file with 3 rounds each containing 10 themes. Each theme will contain from 7 to 10 number of questions.
1. Include all themes from a package files with a name containing `Physics` (`My Physics.siq` and `Physics Pack.siq` are included)
   and make sure to have them all in the new package if there is a space.
2. Also include from these and other packages all themes with a name containing
   `[Mm]echanics` (`Quantum Mechanics` from `Physics Pack.siq` and `Classical mechanics` form `Mechanics.siq` are included).
3. But exclude all themes containing `Quantum` (`Quantum Mechanics` is excluded).
