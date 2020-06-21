#!/usr/bin/env python3

import click
import collections
import datetime
import json
import lxml.etree
import math
import os.path
import random
import re
import urllib.parse
import uuid
import xml.etree.ElementTree
import zipfile

from sigame_tools.common import (
    Metadata,
    get_content,
    read_metadata,
)


@click.command()
@click.option('--index_path', type=click.Path(), required=True)
@click.option('--output', type=str, required=True)
@click.option('--rounds', type=int, default=1, show_default=True)
@click.option('--themes_per_round', type=int, default=1, show_default=True)
@click.option('--min_questions_per_theme', type=int, default=10, show_default=True)
@click.option('--max_questions_per_theme', type=int, default=10, show_default=True)
@click.option('--include_theme_by_name', type=str, multiple=True)
@click.option('--exclude_theme_by_name', type=str, multiple=True)
@click.option('--include_theme_by_id', type=str, multiple=True)
@click.option('--exclude_theme_by_id', type=str, multiple=True)
@click.option('--random_seed', type=int, default=None)
@click.option('--package_name', type=str, default='Generated pack')
def main(index_path, output, rounds, themes_per_round, min_questions_per_theme,
         max_questions_per_theme, include_theme_by_name, exclude_theme_by_name,
         random_seed, package_name, include_theme_by_id, exclude_theme_by_id):
    assert rounds >= 0
    assert themes_per_round >= 0
    assert min_questions_per_theme >= 0
    assert min_questions_per_theme <= max_questions_per_theme
    random.seed(random_seed)
    generate_package(
        name=package_name,
        output=output,
        rounds=generate_rounds(
            metadata=read_metadata(index_path),
            rounds=rounds,
            themes_per_round=themes_per_round,
            min_questions_per_theme=min_questions_per_theme,
            max_questions_per_theme=max_questions_per_theme,
            include_theme_by_name=re.compile('|'.join(include_theme_by_name)) if include_theme_by_name else None,
            exclude_theme_by_name=re.compile('|'.join(exclude_theme_by_name)) if exclude_theme_by_name else None,
            include_theme_by_ids=frozenset(include_theme_by_id),
            exclude_theme_by_ids=frozenset(exclude_theme_by_id),
        ),
    )


def generate_rounds(metadata, rounds, themes_per_round, min_questions_per_theme,
                    max_questions_per_theme, include_theme_by_name, exclude_theme_by_name,
                    include_theme_by_ids, exclude_theme_by_ids):
    def is_proper_theme(theme):
        if not (min_questions_per_theme <= theme.questions_num <= max_questions_per_theme):
            return False
        if theme.id in include_theme_by_ids or theme.id not in exclude_theme_by_ids:
            return True
        return (
            include_theme_by_name and re.search(include_theme_by_name, theme.theme_name)
            or exclude_theme_by_name and not re.search(exclude_theme_by_name, theme.theme_name)
        )
    available = {v for v in metadata if is_proper_theme(v)}
    high_priority = {v for v in available if v.id in include_theme_by_ids}
    available = available.difference(high_priority)
    high_priority_num = min(int(math.ceil(themes_per_round / rounds)), themes_per_round)
    if len(available) + len(high_priority) == 0:
        raise RuntimeError('No themes to generate rounds: all themes are filtered out')
    print(f'Generate rounds, filtered in {len(available) + len(high_priority)} themes out of {len(metadata)}...')
    for n in range(rounds):
        print(f'Generate round {n}, {len(available)} themes are available...')
        try_number = 0
        questions_num = random.randint(min_questions_per_theme, max_questions_per_theme)
        while True:
            samples = sorted(v for v in available if v.questions_num == questions_num)
            high_priority_samples = sorted(v for v in high_priority if v.questions_num == questions_num)
            if len(samples) + len(high_priority_samples) < themes_per_round:
                print(f'Not enough samples for round with {questions_num} question(s): got only {len(samples)}')
                if min_questions_per_theme == max_questions_per_theme or try_number > 0 and questions_num == max_questions_per_theme:
                    raise RuntimeError("Can't get sample themes for round: not enough samples")
                questions_num = min_questions_per_theme + try_number
                try_number += 1
                continue
            print(f'Sample {len(samples)} themes with {questions_num} question(s)...')
            if len(high_priority_samples) < high_priority_num:
                first_selected = list(high_priority_samples)
            else:
                first_selected = random.sample(population=high_priority_samples, k=themes_per_round)
            high_priority = high_priority.difference(first_selected)
            selected = random.sample(population=samples, k=themes_per_round - len(first_selected))
            available = available.difference(selected)
            selected.extend(high_priority_samples)
            random.shuffle(sorted(selected))
            yield f'Round {n}', selected
            break


def generate_package(name, output, rounds):
    content, files = generate_content(name=name, rounds=rounds)
    with zipfile.ZipFile(output, 'w') as siq:
        for path, data in CONST_FILES:
            write_siq_file(siq=siq, path=path, data=data.encode('utf-8'))
        write_content(siq=siq, content=content)
        copy_files(dst_siq=siq, files=files)


def copy_files(dst_siq, files):
    for path, path_files in files.items():
        print(f'Copy files from {path}...')
        with zipfile.ZipFile(path) as src_siq:
            src_siq_file_paths = {urllib.parse.unquote(v): v for v in src_siq.namelist()}
            for file_type, src_file_name, dst_file_name in path_files:
                print(f'Request {file_type} file {src_file_name}...')
                file_dir = SIQ_FILE_TYPE_DIRS[file_type]
                src_file_path = src_siq_file_paths[os.path.join(file_dir, src_file_name)]
                dst_file_path = os.path.join(file_dir, dst_file_name)
                print(f'Copy {path} package file {src_file_path} to {dst_file_path}...')
                data = read_siq_file(siq=src_siq, path=src_file_path)
                write_siq_file(siq=dst_siq, path=dst_file_path, data=data)


def write_content(siq, content):
    with siq.open('content.xml', 'w') as stream:
        content.write(stream, xml_declaration=True, encoding='utf-8')


def write_siq_file(siq, path, data):
    with siq.open(path, 'w') as stream:
        stream.write(data)


def read_siq_file(siq, path):
    with siq.open(path) as stream:
        return stream.read()


def generate_content(name, rounds):
    package_element = lxml.etree.Element('package', attrib=dict(
        name=name,
        version='4',
        id=str(uuid.uuid1()),
        date=datetime.datetime.now().strftime(r'%d.%m.%Y'),
        difficutly='5',
        xmlns="http://vladimirkhil.com/ygpackage3.0.xsd",
    ))
    info_element = lxml.etree.SubElement(package_element, 'info', attrib=dict())
    authors_element = lxml.etree.SubElement(info_element, 'authors', attrib=dict())
    authors = collections.OrderedDict({'elsid': {'Composition'}})
    rounds_element = lxml.etree.SubElement(package_element, 'rounds', attrib=dict())
    files = collections.defaultdict(set)
    for name, themes in rounds:
        round_element = lxml.etree.SubElement(rounds_element, 'round', attrib=dict(name=name))
        themes_element = lxml.etree.SubElement(round_element, 'themes', attrib=dict())
        for theme in themes:
            theme_element = lxml.etree.SubElement(themes_element, 'theme', attrib=dict(name=theme.theme_name))
            questions_element, theme_authors_element = read_questions_and_authors(theme)
            for atom in questions_element.iter('atom'):
                atom_type = atom.attrib.get('type')
                if atom_type and atom.text and atom.text.startswith('@'):
                    extension = atom.text.rsplit('.', 1)[-1]
                    file_name = f'{str(uuid.uuid1())}.{extension}'
                    files[theme.path].add((atom_type, atom.text[1:], file_name))
                    atom.text = f'@{file_name}'
            questions_xml = xml.etree.ElementTree.tostring(questions_element, encoding='utf-8')
            theme_element.append(lxml.etree.fromstring(questions_xml))
            for author in theme_authors_element:
                if author.text not in authors:
                    authors[author.text] = set()
                authors[author.text].add(theme.package_name)
    for author in authors.keys():
        authors_and_roles = f'{author} ({", ".join(sorted(authors[author]))})'
        lxml.etree.SubElement(authors_element, 'author', attrib=dict()).text = authors_and_roles
    return lxml.etree.ElementTree(package_element), files


def read_questions_and_authors(metadata):
    with zipfile.ZipFile(metadata.path) as siq:
        content = get_content(siq)
        return (
            get_question(content=content, metadata=metadata),
            get_authors(content)
        )


def get_authors(content):
    yield from content.iter('author')


def get_question(content, metadata):
    round_number = 0
    for round_ in content.iter('round'):
        round_number += 1
        theme_number = 0
        if round_.attrib['name'] != metadata.round_name:
            continue
        for theme in round_.iter('theme'):
            theme_number += 1
            if theme.attrib['name'] != metadata.theme_name:
                continue
            if round_number != metadata.round_number:
                continue
            if theme_number != metadata.theme_number:
                continue
            for questions in theme.iter('questions'):
                return questions


CONTENT_TYPES = (
    r'<?xml version="1.0" encoding="utf-8"?>'
    + r'<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
    + r'<Default Extension="xml" ContentType="si/xml" />'
    + r'</Types>'
)

TEXTS_AUTHORS = r'<?xml version="1.0" encoding="utf-8"?><Authors />'

TEXTS_SOURCES = r'<?xml version="1.0" encoding="utf-8"?><Sources />'

CONST_FILES = (
    ('[Content_Types].xml', CONTENT_TYPES),
    ('Texts/authors.xml', TEXTS_AUTHORS),
    ('Texts/sources.xml', TEXTS_SOURCES),
)

SIQ_FILE_TYPE_DIRS = dict(
    image='Images',
    video='Video',
    voice='Audio',
)


if __name__ == "__main__":
    main()
