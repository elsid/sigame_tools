#!/usr/bin/env python3

import base64
import click
import json
import os.path
import uuid
import zipfile

from sigame_tools.common import (
    INDEX_VERSION,
    ThemeMetadata,
    get_content,
)


@click.command()
@click.option('--output', type=str, required=True)
@click.argument('paths', nargs=-1, type=str, required=True)
def main(output, paths):
    themes = [v._asdict() for v in process_files(paths)]
    index = dict(
        version=INDEX_VERSION,
        themes=themes,
    )
    with open(output, 'w') as stream:
        json.dump(index, stream, ensure_ascii=False)


def process_files(paths):
    for path in paths:
        if not os.path.exists(path):
            print(f'Ignore {path}: path does not exist')
            continue
        if os.path.isdir(path):
            print(f'Process directory {path}')
            yield from process_files((os.path.join(path, v) for v in os.listdir(path)))
            continue
        if not path.endswith('.siq'):
            print(f'Ignore {path}: not .siq file')
            continue
        print(f'Read .siq file {path}')
        try:
            with zipfile.ZipFile(path) as siq:
                if not 'content.xml' in siq.namelist():
                    print(f'Error: no content.xml in {path}: {siq.namelist()}')
                    continue
                yield from get_themes_metadata(path=path, content=get_content(siq))
        except zipfile.BadZipFile as e:
            print(f'Read {path} error: {str(e)}')


def get_themes_metadata(path, content):
    package = content.getroot()
    authors = tuple(sorted({v.text for v in package.iter('author') if v.text}))
    round_number = 0
    for round_ in package.iter('round'):
        round_number += 1
        theme_number = 0
        for theme in round_.iter('theme'):
            theme_number += 1
            yield ThemeMetadata(
                id=str(uuid.uuid1()),
                round_number=round_number,
                theme_number=theme_number,
                path=path,
                package_name=package.attrib['name'],
                round_name=round_.attrib['name'],
                theme_name=theme.attrib['name'],
                questions_num=get_number_of_questions(theme),
                authors=authors,
                base64_encoded_right_answers=tuple(get_base64_encoded_right_answers(theme)),
                round_type=round_.attrib.get('type'),
            )


def get_number_of_questions(theme):
    return sum(1 for _ in theme.iter('question'))


def get_base64_encoded_right_answers(theme):
    for right in theme.iter('right'):
        for answer in right.iter('answer'):
            if answer.text:
                yield base64.b64encode(answer.text.encode('utf-8')).decode('utf-8')


if __name__ == "__main__":
    main()
