#!/usr/bin/env python3

import click
import collections
import datetime
import lxml.etree
import math
import os.path
import random
import urllib.parse
import uuid
import xml.etree.ElementTree
import zipfile

from sigame_tools.common import (
    THEME_MEDATA_FIELDS,
    get_content,
    read_index,
)

from sigame_tools.filters import (
    make_filter,
    make_high_priority_filter,
)


@click.command()
@click.option('--index_path', type=click.Path(), required=True)
@click.option('--output', type=str, required=True)
@click.option('--rounds', type=int, default=3, show_default=True)
@click.option('--themes_per_round', type=int, default=3, show_default=True)
@click.option('--min_questions_per_theme', type=int, default=5, show_default=True)
@click.option('--max_questions_per_theme', type=int, default=10, show_default=True)
@click.option('--filter', type=str, nargs=3, multiple=True,
              help='Triple of <force_include|include|exclude> <field> <pattern> that is used'
                   ' to filter in or out themes applying conditions in a given order. force_include'
                   ' will put themes into package with higher priority that include.')
@click.option('--random_seed', type=int, default=None)
@click.option('--package_name', type=str, default='Generated pack')
@click.option('--unique_theme_names', type=click.Choice(('true', 'false')), default='true', show_default=True)
@click.option('--unique_right_answers', type=click.Choice(('true', 'false')), default='true', show_default=True)
def main(index_path, output, rounds, themes_per_round, min_questions_per_theme,
         max_questions_per_theme, random_seed, package_name, unique_theme_names,
         unique_right_answers, **kwargs):
    assert rounds > 0
    assert themes_per_round > 0
    assert min_questions_per_theme > 0
    assert min_questions_per_theme <= max_questions_per_theme
    random.seed(random_seed)
    generate_package(
        name=package_name,
        output=output,
        rounds=generate_rounds(
            metadata=read_index(index_path).themes,
            rounds=rounds,
            themes_per_round=themes_per_round,
            min_questions_per_theme=min_questions_per_theme,
            max_questions_per_theme=max_questions_per_theme,
            filter_f=make_filter(args=kwargs['filter'], types=THEME_MEDATA_FIELDS),
            is_high_priority=make_high_priority_filter(args=kwargs['filter'], types=THEME_MEDATA_FIELDS),
            use_unique_theme_names=unique_theme_names == 'true',
            use_unique_right_answers=unique_right_answers == 'true',
        ),
    )


def generate_rounds(metadata, rounds, themes_per_round, min_questions_per_theme,
                    max_questions_per_theme, filter_f, is_high_priority, use_unique_theme_names,
                    use_unique_right_answers):
    def is_proper_theme(theme):
        if theme.round_type == None and not (min_questions_per_theme <= theme.questions_num <= max_questions_per_theme):
            return False
        return filter_f(theme)
    available, high_priority = filter_themes(
        metadata=metadata,
        is_proper_theme=is_proper_theme,
        is_high_priority=is_high_priority,
    )
    print(f'Generate rounds, filtered in {len(available[None]) + len(high_priority[None])} normal '
          + f'{len(available["final"]) + len(high_priority["final"])} final and themes and out of {len(metadata)}...')
    for round_type in (None, 'final'):
        if len(available[round_type]) + len(high_priority[round_type]) == 0:
            raise RuntimeError(f'No themes to generate {round_type or "normal"} rounds: all themes are filtered out')
    used_theme_names = set()
    used_right_answers = set()
    filter_by_used = make_filter_used_by(
        used_theme_names=used_theme_names,
        use_unique_theme_names=use_unique_theme_names,
        used_right_answers=used_right_answers,
        use_unique_right_answers=use_unique_right_answers,
    )
    for round_number in range(rounds):
        if round_number == rounds - 1:
            round_name = 'Final round'
            round_type = 'final'
            high_priority_num = themes_per_round
            min_questions_per_theme = 1
            max_questions_per_theme = 1
        else:
            round_name = f'Round {round_number}'
            round_type = None
            high_priority_num = min(int(math.ceil(themes_per_round / (rounds - 1))), themes_per_round)
        print(f'Generate {round_type or "normal"} round {round_number}: {len(high_priority[round_type])}'
              + f' high priority and {len(available[round_type])} regular themes are available...')
        questions_nums = list(range(min_questions_per_theme, max_questions_per_theme + 1))
        random.shuffle(questions_nums)
        for questions_num in questions_nums:
            high_priority_samples = sorted(v for v in high_priority[round_type] if v.questions_num == questions_num)
            regular_samples = sorted(v for v in available[round_type] if v.questions_num == questions_num)
            if len(high_priority_samples) + len(regular_samples) < themes_per_round:
                raise RuntimeError("Can't get themes for round: not enough samples, got only"
                                    + f' {len(high_priority_samples) + len(regular_samples)}/{themes_per_round} themes'
                                    + f' for a {round_type or "normal"} round with {questions_num} question(s)')
            if len(high_priority_samples) < high_priority_num:
                first_selected = high_priority_samples
            else:
                first_selected = random.sample(population=high_priority_samples, k=high_priority_num)
            high_priority[round_type].difference_update(first_selected)
            second_selected = list()
            while len(first_selected) + len(second_selected) < themes_per_round:
                new_selected = random.sample(
                    population=regular_samples,
                    k=themes_per_round - len(first_selected) - len(second_selected),
                )
                new_selected = list(filter_by_used(themes=new_selected, available=available[round_type]))
                second_selected.extend(new_selected)
                total_selected_num = len(first_selected) + len(second_selected)
                if total_selected_num < themes_per_round:
                    print(f'Filtered out duplicate theme names, {total_selected_num}/{themes_per_round} thems are left')
                    regular_samples = sorted(v for v in available[round_type] if v.questions_num == questions_num)
                    has_num = len(high_priority_samples) + len(regular_samples) + len(first_selected) + len(second_selected)
                    if has_num < themes_per_round:
                        raise RuntimeError("Can't get themes for round: not enough samples, got only"
                                            + f' {has_num}/{themes_per_round} themes for a'
                                            + f' {round_type or "normal"} round with {questions_num} question(s)')
                    continue
            selected = sorted(first_selected + second_selected)
            random.shuffle(selected)
            yield Round(name=round_name, type=round_type, themes=selected)
            break
        if len(selected) < themes_per_round:
            raise RuntimeError("Can't get themes for round: not enough samples for a"
                                + f' {round_type or "normal"} round with [{min_questions_per_theme},'
                                + f' {max_questions_per_theme}] question(s)')


def make_filter_used_by(used_theme_names, use_unique_theme_names, used_right_answers, use_unique_right_answers):
    def impl(themes, available):
        for theme in themes:
            if use_unique_theme_names and theme.theme_name.strip() in used_theme_names:
                continue
            if use_unique_right_answers and used_right_answers.intersection(theme.base64_encoded_right_answers):
                continue
            yield theme
            used_theme_names.add(theme.theme_name.strip())
            used_right_answers.update(theme.base64_encoded_right_answers)
            available.remove(theme)
    return impl


def filter_themes(metadata, is_proper_theme, is_high_priority):
    available = collections.defaultdict(set)
    high_priority = collections.defaultdict(set)
    for v in metadata:
        if is_proper_theme(v):
            if is_high_priority(v):
                high_priority[v.round_type].add(v)
            else:
                available[v.round_type].add(v)
    return available, high_priority


def generate_package(name, output, rounds):
    content, files = generate_content(name=name, rounds=rounds)
    with zipfile.ZipFile(output, 'w') as siq:
        for path, data in CONST_FILES:
            write_siq_file(siq=siq, path=path, data=data.encode('utf-8'))
        write_content(siq=siq, content=content)
        copy_files(dst_siq=siq, files=files)


def copy_files(dst_siq, files):
    for path in sorted(files.keys()):
        path_files = sorted(files[path])
        print(f'Copy files from {path}...')
        with zipfile.ZipFile(path) as src_siq:
            src_siq_file_paths = {urllib.parse.unquote(v): v for v in src_siq.namelist()}
            for file_type, src_file_name, dst_file_name, theme_id in path_files:
                print(f'Request {file_type} file {src_file_name}...')
                file_dir = SIQ_FILE_TYPE_DIRS[file_type]
                src_file_path = src_siq_file_paths.get(os.path.join(file_dir, src_file_name))
                if src_file_path is None:
                    raise RuntimeError(f"Can't find referenced {file_type} file {src_file_name} from {path}:"
                                       + f" package doesn't contain file, fix files or exclude theme by id {theme_id}")
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
    for round_ in rounds:
        round_element = lxml.etree.SubElement(rounds_element, 'round', attrib=get_round_attrib(round_))
        themes_element = lxml.etree.SubElement(round_element, 'themes', attrib=dict())
        for theme in round_.themes:
            theme_element = lxml.etree.SubElement(themes_element, 'theme', attrib=dict(name=theme.theme_name))
            questions_element, theme_authors_element = read_questions_and_authors(theme)
            for atom in questions_element.iter('atom'):
                atom_type = atom.attrib.get('type')
                if atom_type and atom.text and atom.text.startswith('@'):
                    extension = atom.text.rsplit('.', 1)[-1]
                    file_name = f'{str(uuid.uuid1())}.{extension}'
                    files[theme.path].add((atom_type, atom.text[1:], file_name, theme.id))
                    atom.text = f'@{file_name}'
            questions_xml = xml.etree.ElementTree.tostring(questions_element, encoding='utf-8')
            theme_element.append(lxml.etree.fromstring(questions_xml))
            for author in theme_authors_element:
                if not author.text:
                    continue
                if author.text not in authors:
                    authors[author.text] = set()
                authors[author.text].add(theme.package_name)
    for author in sorted(authors.keys()):
        authors_and_roles = f'{author} ({", ".join(sorted(authors[author]))})'
        lxml.etree.SubElement(authors_element, 'author', attrib=dict()).text = authors_and_roles
    return lxml.etree.ElementTree(package_element), files


def get_round_attrib(round_):
    attrib = dict(name=round_.name)
    if round_.type:
        attrib['type'] = round_.type
    return attrib


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

Round = collections.namedtuple('Round', (
    'name',
    'type',
    'themes',
))


if __name__ == "__main__":
    main()
