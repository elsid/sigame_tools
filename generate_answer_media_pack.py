#!/usr/bin/env python3

import click
import collections
import datetime
import glob
import lxml.etree
import os.path
import urllib.parse
import uuid
import zipfile

from sigame_tools.common import (
    SIQ_FILE_TYPE_DIRS,
    THEME_METADATA_FIELDS,
    get_content,
    read_index,
    read_binary_file,
    write_content_xml,
    write_index,
    write_siq_const_files,
    write_siq_file,
)


@click.command()
@click.option('--author', type=str, multiple=True)
@click.option('--package_name', type=str, required=True)
@click.option('--round_name', type=str, required=True)
@click.option('--theme_name', type=str, required=True)
@click.option('--output', type=click.Path(), required=True)
@click.option('--media_path', type=click.Path(), required=True)
@click.option('--media_type', type=click.Choice(('image', 'video', 'voice', 'text')), required=True)
@click.option('--question_suffix', type=str, default='question',
              help='File name suffix like answer.suffix.ext to be used as question.'
                   + 'Then file name like answer.ext will be used as answer.')
@click.option('--comment', type=str)
def main(author, package_name, round_name, theme_name, output, media_path,
         question_suffix, media_type, comment):
    questions, file_paths = generate_questions(
        media_path=media_path,
        media_type=media_type,
        question_suffix=question_suffix,
    )
    content_xml = generate_content_xml(
        authors=author,
        package_name=package_name,
        round_name=round_name,
        theme_name=theme_name,
        comment=comment,
        questions=questions,
    )
    write_package(
        content_xml=content_xml,
        file_paths=file_paths,
        media_type=media_type,
        output=output,
    )


def generate_questions(media_path, media_type, question_suffix):
    answers = dict()
    file_paths = list()
    for path in glob.glob(media_path):
        file_paths.append(path)
        name, _ = os.path.basename(path).rsplit('.', 1)
        name_and_suffix = name.rsplit('.', 1)
        if len(name_and_suffix) > 1:
            if name_and_suffix[-1] == question_suffix:
                answers[name_and_suffix[0]] = path
                continue
        answers.setdefault(name, path)
    questions_element = lxml.etree.Element('questions', attrib=dict())
    for answer, path in sorted(answers.items()):
        question_element = lxml.etree.SubElement(questions_element, 'question', attrib=dict(price='100'))
        scenario_element = lxml.etree.SubElement(question_element, 'scenario', attrib=dict())
        atom_question_element = lxml.etree.SubElement(scenario_element, 'atom', attrib=get_media_type_attrib(media_type))
        atom_question_element.text = get_media_text(media_type=media_type, path=path)
        answer_path = get_answer_path(path=path, question_suffix=question_suffix)
        if answer_path is not None and os.path.exists(answer_path):
            lxml.etree.SubElement(scenario_element, 'atom', attrib=dict(type='marker'))
            atom_answer_element = lxml.etree.SubElement(scenario_element, 'atom', attrib=get_media_type_attrib(media_type))
            atom_answer_element.text = get_media_text(media_type=media_type, path=answer_path)
        right_element = lxml.etree.SubElement(question_element, 'right', attrib=dict())
        answer_element = lxml.etree.SubElement(right_element, 'answer', attrib=dict())
        answer_element.text = answer
    return questions_element, file_paths


def get_media_type_attrib(media_type):
    if media_type == 'text':
        return dict()
    return dict(type=media_type)


def get_media_text(media_type, path):
    if media_type == 'text':
        with open(path) as stream:
            return stream.read()
    return f'@{os.path.basename(path)}'


def get_answer_path(path, question_suffix):
    name, extension = os.path.basename(path).rsplit('.', 1)
    name_and_suffix = name.rsplit('.', 1)
    if len(name_and_suffix) <= 1:
        return None
    if name_and_suffix[-1] != question_suffix:
        return None
    return os.path.join(os.path.dirname(path), f'{name_and_suffix[0]}.{extension}')


def generate_content_xml(authors, package_name, round_name, theme_name, comment, questions):
    package_element = lxml.etree.Element('package', attrib=dict(
        name=package_name,
        version='4',
        id=str(uuid.uuid1()),
        date=datetime.datetime.now().strftime(r'%d.%m.%Y'),
        difficutly='5',
        xmlns='http://vladimirkhil.com/ygpackage3.0.xsd',
    ))
    info_element = lxml.etree.SubElement(package_element, 'info', attrib=dict())
    authors_element = lxml.etree.SubElement(info_element, 'authors', attrib=dict())
    for author in authors:
        lxml.etree.SubElement(authors_element, 'author', attrib=dict()).text = author
    rounds_element = lxml.etree.SubElement(package_element, 'rounds', attrib=dict())
    round_element = lxml.etree.SubElement(rounds_element, 'round', attrib=dict(name=round_name))
    themes_element = lxml.etree.SubElement(round_element, 'themes', attrib=dict())
    theme_element = lxml.etree.SubElement(themes_element, 'theme', attrib=dict(name=theme_name))
    theme_info_element = lxml.etree.SubElement(theme_element, 'info', attrib=dict())
    comments_element = lxml.etree.SubElement(theme_info_element, 'comments', attrib=dict())
    comments_element.text = comment
    theme_element.append(questions)
    return lxml.etree.ElementTree(package_element)


def write_package(content_xml, file_paths, media_type, output):
    with zipfile.ZipFile(output, 'w') as siq:
        write_siq_const_files(siq)
        write_content_xml(siq=siq, content_xml=content_xml)
        if media_type != 'text':
            copy_files(dst_siq=siq, file_paths=file_paths, media_type=media_type)


def copy_files(dst_siq, file_paths, media_type):
    for src_path in file_paths:
        file_dir = SIQ_FILE_TYPE_DIRS[media_type]
        dst_path = os.path.join(file_dir, urllib.parse.quote(os.path.basename(src_path)))
        write_siq_file(siq=dst_siq, path=dst_path, data=read_binary_file(src_path))


if __name__ == "__main__":
    main()
