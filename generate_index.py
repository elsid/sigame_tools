#!/usr/bin/env python3

import click
import json

from sigame_tools.common import (
    INDEX_VERSION,
    build_themes_index,
)


@click.command()
@click.option('--output', type=str, required=True)
@click.argument('paths', nargs=-1, type=str, required=True)
def main(output, paths):
    index = dict(
        version=INDEX_VERSION,
        themes=[v._asdict() for v in build_themes_index(paths)],
    )
    with open(output, 'w') as stream:
        json.dump(index, stream, ensure_ascii=False)


if __name__ == "__main__":
    main()
