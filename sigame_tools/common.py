import collections
import defusedxml.ElementTree
import json

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


def read_metadata(path):
    with open(path) as stream:
        data = json.load(stream)
        return [make_metadata(**v) for v in data]


def make_metadata(authors, base64_encoded_right_answers, **kwargs):
    return Metadata(
        authors=tuple(authors),
        base64_encoded_right_answers=tuple(base64_encoded_right_answers),
        **kwargs,
    )
