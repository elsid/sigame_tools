#!/usr/bin/env python3

import click

from sigame_tools.common import (
    build_themes_index,
    write_index,
)


@click.command()
@click.option('--output', type=click.Path(), required=True)
@click.argument('paths', nargs=-1, type=str, required=True)
def main(output, paths):
    write_index(themes=build_themes_index(paths), output=output)


if __name__ == "__main__":
    main()
