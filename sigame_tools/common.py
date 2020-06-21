import collections
import defusedxml.ElementTree
import json

INDEX_VERSION=3

Index = collections.namedtuple('Index', (
    'version',
    'themes',
))

THEME_MEDATA_FIELDS = collections.OrderedDict(
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

ThemeMetadata = collections.namedtuple('Theme', tuple(THEME_MEDATA_FIELDS.keys()))


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
