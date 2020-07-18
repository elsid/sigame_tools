#!/usr/bin/env python3

import Levenshtein
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
    ThemeMetadata,
    decode_answer,
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
    make_preferred_filter,
)

from sigame_tools.weighted import (
    make_get_weight,
)

@click.command()
@click.option('--index_path', type=click.Path(exists=True, dir_okay=False), required=True)
@click.option('--output', type=click.Path(), required=True)
@click.option('--rounds', type=int, default=3, show_default=True)
@click.option('--themes_per_round', type=int, default=3, show_default=True)
@click.option('--min_questions_per_theme', type=int, default=5, show_default=True)
@click.option('--max_questions_per_theme', type=int, default=10, show_default=True)
@click.option('--filter', type=str, nargs=3, multiple=True,
              help='Triple of <prefer|include|exclude> <field> <pattern> that is used'
                   ' to filter in or out themes applying conditions in a given order. prefer'
                   ' will put themes into package with higher priority that include.')
@click.option('--random_seed', type=int, default=None)
@click.option('--package_name', type=str, default='Generated pack')
@click.option('--unique_theme_names', type=click.Choice(('true', 'false')), default='true', show_default=True)
@click.option('--unique_right_answers', type=click.Choice(('true', 'false')), default='true', show_default=True)
@click.option('--obfuscate', type=click.Choice(('true', 'false')), default='false', show_default=True)
@click.option('--unify_price', type=click.Choice(('true', 'false')), default='true', show_default=True)
@click.option('--shuffle', type=click.Choice(('true', 'false')), default='true', show_default=True)
@click.option('--check_right_answers_similarity', type=click.Choice(('true', 'false')), default='true', show_default=True)
@click.option('--exclude_index_path', type=click.Path(exists=True, dir_okay=False), multiple=True)
@click.option('--output_index', type=click.Path(), default=None)
@click.option('--weight', type=str, nargs=3, multiple=True,
              help='Triple of <field> <pattern> <weight> that is used to sample filtered'
                   ' themes accoding to their mean weight or all field values. Weight is'
                   ' assigned to a field if its values matching the pattern. Default weight'
                   ' is 1. If field value matches multiple patterns mean weight is used.')
@click.option('--final_themes', type=int, default=None)
def main(index_path, output, rounds, themes_per_round, min_questions_per_theme,
         max_questions_per_theme, random_seed, package_name, unique_theme_names,
         unique_right_answers, obfuscate, unify_price, shuffle, check_right_answers_similarity,
         exclude_index_path, output_index, weight, final_themes, **kwargs):
    assert rounds > 0
    assert themes_per_round > 0
    assert min_questions_per_theme > 0
    assert min_questions_per_theme <= max_questions_per_theme
    random.seed(random_seed)
    filters = tuple(list(kwargs['filter']) + list(exclude_by_indices(exclude_index_path)))
    weights = tuple((v[0], v[1], float(v[2])) for v in weight)
    rounds = generate_rounds(
        metadata=read_index(index_path).themes,
        rounds_number=rounds,
        themes_per_round=themes_per_round,
        min_questions_per_theme=min_questions_per_theme,
        max_questions_per_theme=max_questions_per_theme,
        filter_f=make_filter(args=filters, types=THEME_METADATA_FIELDS),
        is_preferred=make_preferred_filter(args=filters, types=THEME_METADATA_FIELDS),
        use_unique_theme_names=unique_theme_names == 'true',
        use_unique_right_answers=unique_right_answers == 'true',
        shuffle=shuffle == 'true',
        check_right_answers_similarity=check_right_answers_similarity == 'true',
        get_weight=make_get_weight(args=weights, types=THEME_METADATA_FIELDS),
        final_themes=themes_per_round if final_themes is None else final_themes,
    )
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


def exclude_by_indices(paths):
    for path in paths:
        yield from exclude_by_index(read_index(path))


def exclude_by_index(index):
    for theme in index.themes:
        yield 'exclude', 'id', theme.id


def generate_rounds(metadata, rounds_number, themes_per_round, min_questions_per_theme,
                    max_questions_per_theme, filter_f, is_preferred, use_unique_theme_names,
                    use_unique_right_answers, shuffle, check_right_answers_similarity, get_weight,
                    final_themes):
    print(f'Generate rounds from {len(metadata)} themes...')
    def is_acceptable(theme):
        if theme.round_type is None and not (min_questions_per_theme <= theme.questions_num <= max_questions_per_theme):
            return False
        return filter_f(theme)
    accepted, preferred = prepare_themes(
        metadata=metadata,
        is_acceptable=is_acceptable,
        is_preferred=is_preferred,
    )
    print(f"Got {sum_themes(preferred.get(None))} normal and {sum_themes(preferred.get('final'))} final preferred"
          + f" and {sum_themes(accepted.get(None))} normal and {sum_themes(accepted.get('final'))} final accepted"
          + ' themes')
    rounds = tuple(make_rounds(rounds_number))
    populate_rounds_with_preferred(
        rounds=rounds,
        themes_per_round=themes_per_round,
        min_questions_per_theme=min_questions_per_theme,
        max_questions_per_theme=max_questions_per_theme,
        themes=preferred,
        get_weight=get_weight,
        final_themes=final_themes,
    )
    used_theme_names = get_theme_names(rounds) if use_unique_theme_names else None
    used_right_answers = get_right_answers(rounds) if use_unique_right_answers else None
    is_used = make_filter_used_by(
        used_theme_names=used_theme_names,
        used_right_answers=used_right_answers,
        check_right_answers_similarity=check_right_answers_similarity,
    )
    populate_rounds(
        rounds=rounds,
        themes_per_round=themes_per_round,
        min_questions_per_theme=min_questions_per_theme,
        max_questions_per_theme=max_questions_per_theme,
        is_used=is_used,
        themes=accepted,
        used_theme_names=used_theme_names,
        used_right_answers=used_right_answers,
        get_weight=get_weight,
        final_themes=final_themes,
    )
    if shuffle:
        shuffle_themes(rounds)
    return rounds


def shuffle_themes(rounds):
    themes = collections.defaultdict(list)
    for round_ in rounds:
        if round_.type != 'final':
            themes[round_.themes[0].questions_num].extend(round_.themes)
    for value in themes.values():
        random.shuffle(value)
    for round_ in rounds:
        if round_.type != 'final':
            number = len(round_.themes)
            questions_num = round_.themes[0].questions_num
            round_.themes.clear()
            round_.themes.extend(themes[questions_num][-number:])
            themes[questions_num] = themes[questions_num][:-number]


def get_theme_names(rounds):
    result = set()
    for round_ in rounds:
        result.update(get_themes_theme_names(round_.themes))
    return result


def get_themes_theme_names(themes):
    result = set()
    for theme in themes:
        result.add(theme.theme_name.strip())
    return result


def get_right_answers(rounds):
    result = set()
    for round_ in rounds:
        result.update(get_themes_right_answers(round_.themes))
    return result


def get_themes_right_answers(themes):
    result = set()
    for theme in themes:
        result.update(decode_right_answers(theme.base64_encoded_right_answers))
    return result


def decode_right_answers(values):
    return (decode_answer(v).strip() for v in values)


def sum_themes(typed_themes):
    if not typed_themes:
        return 0
    return sum(len(v) for v in typed_themes.values())


def make_rounds(rounds_number):
    for round_number in range(rounds_number - 1):
        yield Round(name=f'Round {round_number}', type=None, themes=list())
    yield Round(name='Final round', type='final', themes=list())


def populate_rounds_with_preferred(rounds, themes_per_round, min_questions_per_theme, max_questions_per_theme,
                                   themes, get_weight, final_themes):
    for round_ in rounds:
        if round_.type == 'final':
            questions_num = 1
            themes_num = final_themes
        else:
            questions_num = max(
                range(min_questions_per_theme, max_questions_per_theme + 1),
                key=lambda v: len(themes[round_.type][v]),
            )
            themes_num = themes_per_round
        print(f'Populate {round_.name} with preferred themes of {questions_num} questions...')
        populate_round_with_preferred(
            round_=round_,
            themes_num=themes_num,
            themes=themes[round_.type][questions_num],
            get_weight=get_weight,
            final_themes=final_themes,
        )


def populate_round_with_preferred(round_, themes_num, themes, get_weight, final_themes):
    if not themes:
        return
    population = sorted(themes)
    samples = random.choices(
        population=population,
        k=min(len(themes), themes_num),
        weights=tuple(get_weight(v) for v in population),
    )
    round_.themes.extend(samples)
    themes.difference_update(samples)


def populate_rounds(rounds, themes_per_round, min_questions_per_theme, max_questions_per_theme, is_used,
                    themes, used_theme_names, used_right_answers, get_weight, final_themes):
    for round_ in rounds:
        themes_num = themes_per_round
        if round_.themes:
            questions_nums = [round_.themes[0].questions_num]
        elif round_.type == 'final':
            questions_nums = [1]
            themes_num = final_themes
        else:
            questions_nums = list(range(min_questions_per_theme, max_questions_per_theme + 1))
            random.shuffle(questions_nums)
        populated = populate_round(
            round_=round_,
            themes_num=themes_num,
            questions_nums=questions_nums,
            is_used=is_used,
            themes=themes[round_.type],
            used_theme_names=used_theme_names,
            used_right_answers=used_right_answers,
            get_weight=get_weight,
        )
        if not populated:
            raise RuntimeError("Can't get themes for round: not enough samples for a"
                               + f' {round_.type or "normal"} round with [{min_questions_per_theme},'
                               + f' {max_questions_per_theme}] question(s)')


def populate_round(round_, themes_num, questions_nums, is_used, themes,
                   used_theme_names, used_right_answers, get_weight):
    need = themes_num - len(round_.themes)
    if need <= 0:
        return True
    print(f'Populate {round_.name} round, need {need} themes...')
    for questions_num in questions_nums:
        print(f'Use {len(themes[questions_num])} themes with {questions_num} questions...')
        filtered = tuple(v for v in themes[questions_num] if not is_used(v))
        print(f'Filtered themes: {len(filtered)} themes are left')
        if len(filtered) < need:
            continue
        samples = get_unique_samples(
            number=themes_num,
            is_used=is_used,
            themes=set(themes[questions_num]),
            used_theme_names=used_theme_names,
            used_right_answers=used_right_answers,
            get_weight=get_weight,
        )
        if not samples:
            continue
        round_.themes.extend(samples)
        themes[questions_num].difference_update(samples)
        return True
    return False


def get_unique_samples(number, is_used, themes, used_theme_names, used_right_answers, get_weight):
    currently_used_theme_names = set()
    currently_used_right_answers = set()
    selected = list()
    while len(selected) < number:
        need = number - len(selected)
        print(f'Need {need} sample(s)')
        if len(themes) < need:
            if used_theme_names is not None:
                used_theme_names.difference_update(currently_used_theme_names)
            if used_right_answers is not None:
                used_right_answers.difference_update(currently_used_right_answers)
            return
        filtered = tuple(v for v in themes if not is_used(v))
        population = sorted(filtered)
        print(f'Filtered themes: {len(population)} themes are left')
        samples = random.choices(
            population=population,
            k=need,
            weights=tuple(get_weight(v) for v in population),
        )
        for sample in samples:
            if is_used(sample):
                continue
            selected.append(sample)
            themes.remove(sample)
            if used_theme_names is not None:
                used_theme_names.add(sample.theme_name.strip())
                currently_used_theme_names.add(sample.theme_name.strip())
            if used_right_answers is not None:
                used_right_answers.update(decode_right_answers(sample.base64_encoded_right_answers))
                currently_used_right_answers.update(decode_right_answers(sample.base64_encoded_right_answers))
        themes = set(filtered)
    return selected


def make_filter_used_by(used_theme_names, used_right_answers, check_right_answers_similarity):
    def impl(theme):
        if used_theme_names is not None and theme.theme_name.strip() in used_theme_names:
            return True
        if used_right_answers is not None:
            right_answers = decode_right_answers(theme.base64_encoded_right_answers)
            if used_right_answers.intersection(right_answers):
                return True
            if check_right_answers_similarity:
                for answer in right_answers:
                    if contains_similar(values=used_right_answers, target=answer):
                        return True
        return False
    return impl


def contains_similar(values, target):
    if len(target) < 5:
        return False
    target = target.lower()
    for value in values:
        value = value.lower()
        if Levenshtein.distance(target, value) <= max(1, max(len(target), len(value)) // 10):
            return True
    return False


def prepare_themes(metadata, is_acceptable, is_preferred):
    accepted = collections.defaultdict(lambda: collections.defaultdict(set))
    preferred = collections.defaultdict(lambda: collections.defaultdict(set))
    for value in metadata:
        if value.round_type not in ('final', None):
            value = theme_with_round_type(value, None)
        if is_acceptable(value):
            if is_preferred(value):
                preferred[value.round_type][value.questions_num].add(value)
            else:
                accepted[value.round_type][value.questions_num].add(value)
    return accepted, preferred


def theme_with_round_type(theme, value):
    theme_dict = theme._asdict()
    theme_dict['round_type'] = value
    return ThemeMetadata(**theme_dict)


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
            theme_theme_element, theme_authors_element = read_theme_and_authors(theme)
            for atom in theme_theme_element.iter('atom'):
                atom_type = atom.attrib.get('type')
                if atom_type and atom.text and atom.text.startswith('@'):
                    extension = atom.text.rsplit('.', 1)[-1]
                    file_name = f'{str(uuid.uuid1())}.{extension}'
                    files[theme.path].add((atom_type, atom.text[1:], file_name, theme.id))
                    atom.text = f'@{file_name}'
                elif atom_type is None and atom.text and use_obfuscation:
                    atom.text = obfuscate(atom.text)
            if use_obfuscation:
                for answer in theme_theme_element.iter('answer'):
                    if answer.text:
                        answer.text = obfuscate(answer.text)
            if use_unified_price:
                if round_.type is None:
                    num = sum(1 for _ in theme_theme_element.iter('question'))
                    for question, price in zip(theme_theme_element.iter('question'), get_prices(num)):
                        question.attrib['price'] = str(price)
                elif round_.type == 'final':
                    for question in theme_theme_element.iter('question'):
                        question.attrib['price'] = '0'
            theme_theme_xml = xml.etree.ElementTree.tostring(theme_theme_element, encoding='utf-8')
            theme_element.extend(lxml.etree.fromstring(theme_theme_xml))
            for author in theme_authors_element:
                if not author.text:
                    continue
                if author.text not in authors:
                    authors[author.text] = set()
                authors[author.text].add(theme.package_name)
    answers = collections.Counter()
    for right in package_element.iter('right'):
        for answer in right.iter('answer'):
            answers[answer.text] += 1
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


def read_theme_and_authors(metadata):
    with zipfile.ZipFile(metadata.path) as siq:
        content = get_content(siq)
        return (
            get_theme(content=content, metadata=metadata),
            get_authors(content)
        )


def get_authors(content):
    yield from content.iter('author')


def get_theme(content, metadata):
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
            return theme


Round = collections.namedtuple('Round', (
    'name',
    'type',
    'themes',
))


if __name__ == "__main__":
    main()
