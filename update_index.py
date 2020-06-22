#!/usr/bin/env python3

import click
import deepdiff
import json
import os.path
import zipfile

from sigame_tools.common import (
    INDEX_VERSION,
    NoContentXml,
    ThemeMetadata,
    build_themes_index,
    get_file_name,
    get_themes_metadata,
    read_content,
    read_index,
)


@click.command()
@click.option('--index_path', type=str, required=True)
@click.option('--output', type=str, required=True)
@click.option('--force', type=str, multiple=True)
@click.argument('paths', nargs=-1, type=str, required=True)
def main(index_path, output, force, paths):
    old_index = read_index(index_path)
    processed_paths = set()
    themes = list(update_themes(index=old_index, processed_paths=processed_paths, force=force))
    themes.extend(list(build_themes_index(paths=paths, ignore_paths=processed_paths)))
    new_index = dict(
        version=INDEX_VERSION,
        themes=[v._asdict() for v in themes],
    )
    with open(output, 'w') as stream:
        json.dump(new_index, stream, ensure_ascii=False)


def update_themes(index, processed_paths, force):
    contents = dict()
    for theme in index.themes:
        content_themes = contents.get(theme.path)
        if content_themes is None:
            if not os.path.exists(theme.path):
                print(f'Ignore {theme.path}: file is missing')
                continue
            try:
                content_themes = make_content_themes(theme.path)
            except (zipfile.BadZipFile, NoContentXml) as e:
                print(f'Ignore {path}: {str(e)}')
                continue
            contents[theme.path] = content_themes
        new_theme = content_themes.get((theme.round_number, theme.theme_number))
        if new_theme is None:
            print(f'Theme with round_number={theme.round_number} and theme_number={theme.theme_number} is missing,'
                  f' old id={theme.id}, will reindex {theme.path}')
            continue
        new_theme = theme_with_id(new_theme, theme.id)
        if theme != new_theme:
            exclude_paths = []
            if index.version < 3:
                exclude_paths.extend(['root.images_num', 'root.video_num', 'root.voice_num'])
            if index.version < 2:
                exclude_paths.add('root.file_name')
            diff = deepdiff.DeepDiff(theme, new_theme, exclude_paths=exclude_paths)
            if diff and theme.id not in force:
                raise RuntimeError(f'New theme is not equal to old, remove theme from the index or run with --force={theme.id}: {diff}')
            elif diff:
                print(f'New theme is not equal to old, this will invalidate theme with id {theme.id} due to reindexing: {diff}')
                continue
        yield theme_with_id(new_theme, theme.id)
        del content_themes[(theme.round_number, theme.theme_number)]
        if not content_themes:
            processed_paths.add(theme.path)


def make_content_themes(path):
    file_name = get_file_name(path)
    content = read_content(path)
    content_themes = dict()
    for content_theme in get_themes_metadata(path=path, content=content, file_name=file_name):
        content_themes[(content_theme.round_number, content_theme.theme_number)] = content_theme
    return content_themes


def theme_with_id(theme, value):
    theme_dict = theme._asdict()
    theme_dict['id'] = value
    return ThemeMetadata(**theme_dict)


if __name__ == "__main__":
    main()
