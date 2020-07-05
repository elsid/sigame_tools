import base64
import click
import collections
import defusedxml.ElementTree
import json
import math
import os.path
import uuid
import zipfile

INDEX_VERSION=3

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

Index = collections.namedtuple('Index', (
    'version',
    'themes',
))

THEME_METADATA_FIELDS = collections.OrderedDict(
    id=str,
    round_number=int,
    theme_number=int,
    path=str,
    package_name=str,
    round_name=str,
    theme_name=str,
    questions_num=int,
    authors=[str],
    base64_encoded_right_answers=[str],
    round_type=str,
    file_name=str,
    images_num=int,
    videos_num=int,
    voices_num=int,
)

ThemeMetadata = collections.namedtuple('ThemeMetadata', tuple(THEME_METADATA_FIELDS.keys()))


def read_content(path):
    print(f'Read .siq file {path}...')
    with zipfile.ZipFile(path) as siq:
        if not 'content.xml' in siq.namelist():
            raise NoContentXml(f'No content.xml in {path}')
        return get_content(siq)


class NoContentXml(RuntimeError):
    pass


def get_content(siq):
    with siq.open('content.xml') as content:
        tree = defusedxml.ElementTree.parse(content)
        for element in tree.iter():
            element.tag = remove_namespace(element.tag)
        return tree


def remove_namespace(tag):
    return tag.split('}', 1)[1]


def read_index(path):
    index = read_json(path)
    if index['version'] < INDEX_VERSION:
        print(f'Index version {index["version"]} is outdated: this program is designed for index version {INDEX_VERSION}')
    if index['version'] > INDEX_VERSION:
        print(f'Index version {index["version"]} is too advanced: this program is designed for index version {INDEX_VERSION}')
    if index['version'] < 2:
        index['file_name'] = ''
    if index['version'] < 3:
        index['images_num'] = 0
        index['video_num'] = 0
        index['voice_num'] = 0
    return make_index(**index)


def make_index(themes, **kwargs):
    return Index(
        themes=tuple(make_theme_metadata(**v) for v in themes),
        **kwargs,
    )


def make_theme_metadata(authors, base64_encoded_right_answers, **kwargs):
    return ThemeMetadata(
        authors=tuple(authors),
        base64_encoded_right_answers=tuple(base64_encoded_right_answers),
        **kwargs,
    )


def read_json(path):
    with open(path) as stream:
        return json.load(stream)


def build_themes_index(paths, ignore_paths=tuple()):
    for path in paths:
        if path in ignore_paths:
            print(f'Ignore {path}: path is in ignore list')
            continue
        if not os.path.exists(path):
            print(f'Ignore {path}: path does not exist')
            continue
        if os.path.isdir(path):
            print(f'Process directory {path}...')
            yield from build_themes_index(
                paths=(os.path.join(path, v) for v in os.listdir(path)),
                ignore_paths=ignore_paths,
            )
            continue
        if not path.endswith('.siq'):
            print(f'Ignore {path}: not .siq file')
            continue
        file_name = get_file_name(path)
        try:
            content = read_content(path)
        except (zipfile.BadZipFile, NoContentXml) as e:
            print(f'Ignore {path}: {str(e)}')
            continue
        yield from get_themes_metadata(path=path, content=content, file_name=file_name)


def get_file_name(path):
    meta_path = path + '.meta.json'
    if os.path.exists(meta_path):
        print(f'Read .meta.json file {meta_path}...')
        return read_json(meta_path).get('name')
    else:
        return os.path.basename(path)


def get_themes_metadata(path, content, file_name):
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
                round_type='final' if round_.attrib.get('type') == 'final' else None,
                file_name=file_name,
                images_num=get_atom_num(theme=theme, atom_type='image'),
                videos_num=get_atom_num(theme=theme, atom_type='video'),
                voices_num=get_atom_num(theme=theme, atom_type='voice'),
            )


def get_number_of_questions(theme):
    return sum(1 for _ in theme.iter('question'))


def get_base64_encoded_right_answers(theme):
    for right in theme.iter('right'):
        for answer in right.iter('answer'):
            if answer.text:
                yield encode_answer(answer.text)


def encode_answer(value):
    return base64.b64encode(value.encode('utf-8')).decode('utf-8')


def decode_answer(value):
    return base64.b64decode(value.encode('utf-8')).decode('utf-8')


def get_atom_num(theme, atom_type):
    return sum(1 for v in theme.iter('atom') if v.attrib.get('type') == atom_type)


def write_index(themes, output):
    index = dict(
        version=INDEX_VERSION,
        themes=[v._asdict() for v in themes],
    )
    with open(output, 'w') as stream:
        json.dump(index, stream, ensure_ascii=False)


def get_prices(num, max_price=1000):
    if num == 0:
        return
    base = max_price // (int(math.ceil(num / 10)) * 10)
    if num % 10 == 0:
        for i in range(1, num + 1):
            yield i * base
        return
    half_price = max_price // 2
    for i in range(num // 2, 0, -1):
        yield half_price - i * base
    if num % 2 == 1:
        yield half_price
    for i in range(1, num // 2 + 1):
        yield half_price + i * base


def write_siq_const_files(siq):
    for path, data in CONST_FILES:
        write_siq_file(siq=siq, path=path, data=data.encode('utf-8'))


def write_siq_file(siq, path, data):
    with siq.open(path, 'w') as stream:
        stream.write(data)


def write_content_xml(siq, content_xml):
    with siq.open('content.xml', 'w') as stream:
        content_xml.write(stream, xml_declaration=True, encoding='utf-8')


def read_binary_file(path):
    with open(path, 'rb') as stream:
        return stream.read()
