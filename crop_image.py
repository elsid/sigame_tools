#!/usr/bin/env python3

import PIL.Image
import click
import os.path


@click.command()
@click.option('--base_x', type=int, default=0)
@click.option('--base_y', type=int, default=0)
@click.option('--max_border_height', type=int, default=10)
@click.option('--min_border_length', type=int, default=150)
@click.option('--min_boder_gray', type=int, default=40)
@click.argument('path', default='', type=click.Path())
def main(path, base_x, base_y, max_border_height, min_border_length, min_boder_gray):
    basename, extension = os.path.basename(path).rsplit('.', 1)
    out_path = os.path.dirname(path)
    with PIL.Image.open(path) as image:
        borders = tuple(get_borders(
            pixels=image.load(),
            height=image.height,
            base_x=base_x,
            base_y=base_y,
            max_border_height=max_border_height,
            min_border_length=min_border_length,
            min_boder_gray=min_boder_gray,
        ))
        crops = list(get_crops(borders))
        num_size = len(crops) // 10 + 1
        for number, border in enumerate(crops):
            top, bottom = border
            crop = image.crop((0, top + 5, image.width, bottom - 5))
            crop.save(os.path.join(out_path, f'{basename}.{str(number).zfill(num_size)}.{extension}'))


def get_crops(borders):
    border = 0
    top = max(borders[0] - 20, 0)
    for i in range(1, len(borders) - 2, 2):
        bottom = int((borders[i] + borders[i + 1]) / 2)
        yield top, bottom
        top = bottom
    yield top, borders[-1] + 20


def get_borders(pixels, height, base_x, base_y, max_border_height, min_border_length, min_boder_gray):
    state = 'space'
    last_border = 0
    for y in range(base_y, height):
        if state == 'space':
            if y - last_border >= max_border_height and is_border(pixels, y, base_x, min_border_length, min_boder_gray):
                state = 'crop'
                last_border = y
                yield y
        elif state == 'crop':
            if y - last_border >= max_border_height and is_border(pixels, y, base_x, min_border_length, min_boder_gray):
                state = 'space'
                last_border = y
                yield y


def is_border(pixels, y, base_x, length, min_gray):
    return all(is_border_color(pixels[x, y], min_gray) for x in range(base_x, base_x + length))


def is_border_color(color, min_gray):
    return (
        color[0] == color[1] == color[2] and color[0] <= min_gray or
        color == (1, 0, 0)
    )


if __name__ == "__main__":
    main()
