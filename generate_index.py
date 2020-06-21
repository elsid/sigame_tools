#!/usr/bin/env python3

import click
import collections
import defusedxml.ElementTree
import json
import os.path
import sys
import uuid
import zipfile


@click.command()
@click.option('--output', type=str, required=True)
@click.argument('paths', nargs=-1, type=str, required=True)
def main(output, paths):
    data = [v._asdict() for v in process_files(paths)]
    with open(output, 'w') as stream:
        json.dump(data, stream, indent=2, ensure_ascii=False)


def process_files(paths):
    for path in paths:
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
                yield from get_metadata(path=path, content=get_content(siq))
        except zipfile.BadZipFile as e:
            print(f'Error: {str(e)}')


def get_metadata(path, content):
    package = content.getroot()
    round_number = 0
    for rounds in package.getchildren():
        if not rounds.tag.endswith('rounds'):
            continue
        for round_ in rounds.getchildren():
            if not round_.tag.endswith('round'):
                continue
            round_number += 1
            theme_number = 0
            for themes in round_.getchildren():
                if not themes.tag.endswith('themes'):
                    continue
                for theme in themes.getchildren():
                    if not theme.tag.endswith('theme'):
                        continue
                    theme_number += 1
                    yield Metadata(
                        id=str(uuid.uuid1()),
                        round_number=round_number,
                        theme_number=theme_number,
                        path=path,
                        package_name=package.attrib['name'],
                        round_name=round_.attrib['name'],
                        theme_name=theme.attrib['name'],
                        questions_num=get_number_of_questions(theme),
                    )


Metadata = collections.namedtuple('Metadata', (
    'id',
    'round_number',
    'theme_number',
    'path',
    'package_name',
    'round_name',
    'theme_name',
    'questions_num',
))


def get_number_of_questions(theme):
    result = 0
    for questions in theme.getchildren():
        if not questions.tag.endswith('questions'):
            continue
        for question in questions.getchildren():
            result += question.tag.endswith('question')
    return result


def get_content(siq):
    with siq.open('content.xml') as content:
        return defusedxml.ElementTree.parse(content)


if __name__ == "__main__":
    main()
