#!/usr/bin/env python3

import click
import collections
import datetime
import lxml.etree
import math
import os.path
import random
import string
import urllib.parse
import uuid
import xml.etree.ElementTree
import zipfile

from sigame_tools.common import (
    SIQ_FILE_TYPE_DIRS,
    THEME_METADATA_FIELDS,
    get_content,
    get_prices,
    read_index,
    write_content_xml,
    write_index,
    write_siq_const_files,
    write_siq_file,
)

from sigame_tools.filters import (
    make_filter,
    make_high_priority_filter,
)


@click.command()
@click.option('--index_path', type=click.Path(exists=True, dir_okay=False), required=True)
@click.option('--output', type=click.Path(), required=True)
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
@click.option('--obfuscate', type=click.Choice(('true', 'false')), default='false', show_default=True)
@click.option('--unify_price', type=click.Choice(('true', 'false')), default='true', show_default=True)
@click.option('--output_index', type=click.Path(), default=None)
def main(index_path, output, rounds, themes_per_round, min_questions_per_theme,
         max_questions_per_theme, random_seed, package_name, unique_theme_names,
         unique_right_answers, obfuscate, unify_price, output_index, **kwargs):
    assert rounds > 0
    assert themes_per_round > 0
    assert min_questions_per_theme > 0
    assert min_questions_per_theme <= max_questions_per_theme
    random.seed(random_seed)
    rounds = tuple(generate_rounds(
        metadata=read_index(index_path).themes,
        rounds=rounds,
        themes_per_round=themes_per_round,
        min_questions_per_theme=min_questions_per_theme,
        max_questions_per_theme=max_questions_per_theme,
        filter_f=make_filter(args=kwargs['filter'], types=THEME_METADATA_FIELDS),
        is_high_priority=make_high_priority_filter(args=kwargs['filter'], types=THEME_METADATA_FIELDS),
        use_unique_theme_names=unique_theme_names == 'true',
        use_unique_right_answers=unique_right_answers == 'true',
    ))
    content_xml, files = generate_content_xml(
        name=package_name,
        rounds=rounds,
        use_obfuscation=obfuscate == 'true',
        use_unified_price=unify_price == 'true',
    )
    write_package(
        content_xml=content_xml,
        files=files,
        output=output,
    )
    if output_index:
        write_index(themes=(w for v in rounds for w in v.themes), output=output_index)


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


def write_package(content_xml, files, output):
    with zipfile.ZipFile(output, 'w') as siq:
        write_siq_const_files(siq)
        write_content_xml(siq=siq, content_xml=content_xml)
        copy_files_from_siq(dst_siq=siq, files=files)


def copy_files_from_siq(dst_siq, files):
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


def read_siq_file(siq, path):
    with siq.open(path) as stream:
        return stream.read()


def generate_content_xml(name, rounds, use_obfuscation, use_unified_price):
    package_element = lxml.etree.Element('package', attrib=dict(
        name=name,
        version='4',
        id=str(uuid.uuid1()),
        date=datetime.datetime.now().strftime(r'%d.%m.%Y'),
        difficutly='5',
        xmlns='http://vladimirkhil.com/ygpackage3.0.xsd',
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
                elif atom_type is None and atom.text and use_obfuscation:
                    atom.text = obfuscate(atom.text)
            if use_obfuscation:
                for answer in questions_element.iter('answer'):
                    if answer.text:
                        answer.text = obfuscate(answer.text)
            if use_unified_price:
                if round_.type is None:
                    num = sum(1 for _ in questions_element.iter('question'))
                    for question, price in zip(questions_element.iter('question'), get_prices(num)):
                        question.attrib['price'] = str(price)
                elif round_.type == 'final':
                    for question in questions_element.iter('question'):
                        question.attrib['price'] = '0'
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


def obfuscate(text):
    result = str()
    for symbol in text:
        if symbol.isalnum():
            symbol = random.choice(string.ascii_uppercase if symbol.isupper() else string.ascii_lowercase)
        elif symbol.isnumeric():
            symbol = str(random.randint(1, 9))
        result += symbol
    return result


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


Round = collections.namedtuple('Round', (
    'name',
    'type',
    'themes',
))


if __name__ == "__main__":
    main()
