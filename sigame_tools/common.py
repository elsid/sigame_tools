import collections
import defusedxml.ElementTree
import json

INDEX_VERSION=1

Index = collections.namedtuple('Index', (
    'version',
    'themes',
))

ThemeMetadata = collections.namedtuple('Theme', (
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
    'round_type',
))


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
