#!/usr/bin/env python3

import base64
import click
import collections
import defusedxml.ElementTree
import json
import os.path
import uuid
import zipfile


@click.command()
@click.option('--output', type=str, required=True)
@click.argument('paths', nargs=-1, type=str, required=True)
def main(output, paths):
    data = [v._asdict() for v in process_files(paths)]
    with open(output, 'w') as stream:
        json.dump(data, stream, ensure_ascii=False)


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
            print(f'Read {path} error: {str(e)}')


def get_metadata(path, content):
    package = content.getroot()
    authors = tuple(sorted({v.text for v in package.iter('author') if v.text}))
    round_number = 0
    for round_ in package.iter('round'):
        round_number += 1
        theme_number = 0
        for theme in round_.iter('theme'):
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
                authors=authors,
                base64_encoded_right_answers=tuple(get_base64_encoded_right_answers(theme)),
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
    'authors',
    'base64_encoded_right_answers',
))


def get_number_of_questions(theme):
    return sum(1 for _ in theme.iter('question'))


def get_base64_encoded_right_answers(theme):
    for right in theme.iter('right'):
        for answer in right.iter('answer'):
            if answer.text:
                yield base64.b64encode(answer.text.encode('utf-8')).decode('utf-8')


def get_content(siq):
    with siq.open('content.xml') as content:
        tree = defusedxml.ElementTree.parse(content)
        for element in tree.iter():
            element.tag = remove_namespace(element.tag)
        return tree


def remove_namespace(tag):
    return tag.split('}', 1)[1]


if __name__ == "__main__":
    main()
