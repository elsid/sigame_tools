#!/usr/bin/env python3

import base64
import click
import collections
import functools
import json
import os.path
import pyquery
import random
import requests
import retry
import time
import urllib.parse

from sigame_tools.common import (
    read_json,
)


@click.command()
@click.option('--offset', type=int, default=0)
@click.option('--pages', type=int, default=1)
@click.option('--vk_group_url', type=str, default='https://m.vk.com/topic-135725718_34975471')
@click.option('--user_agent', type=str, default='Mozilla/5.0 (iPhone; CPU OS 13_4_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) FxiOS/26.0 Mobile/15E148 Safari/605.1.15')
@click.option('--cache_dir', type=str, required=True)
@click.option('--speed_limit', type=float, default=None)
def main(offset, pages, vk_group_url, user_agent, cache_dir, speed_limit):
    download_files(
        urls=get_siq_urls(
            offset=offset,
            pages=pages,
            vk_group_url=vk_group_url,
            cache_dir=cache_dir,
            user_agent=user_agent,
        ),
        cache_dir=cache_dir,
        user_agent=user_agent,
        speed_limit=speed_limit,
    )


def download_files(urls, user_agent, cache_dir, speed_limit):
    avg_speed = MovingSpeedAverage(10)
    avg_speed.add(time=time.time(), distance=0)
    for url in urls:
        try:
            while speed_limit and avg_speed.get() > speed_limit:
                time.sleep(random.normalvariate(mu=1, sigma=0.1))
                avg_speed.add(time=time.time(), distance=0)
            content, meta = get_file(url=url, user_agent=user_agent, cache_dir=cache_dir)
            avg_speed.add(time=time.time(), distance=len(content) * (not meta.get('cached')))
            print(f'Recent speed: {int(avg_speed.get())} B/s (limit: {speed_limit} B/s)')
        except RuntimeError as e:
            print(f'Error while downloading {url}: {str(e)}')


class MovingSpeedAverage:
    def __init__(self, window_duration):
        self.__window_duration = window_duration
        self.__sum_distance = 0
        self.__time = collections.deque()
        self.__distance = collections.deque()

    def add(self, time, distance):
        self.__time.append(time)
        self.__distance.append(distance)
        self.__sum_distance += distance
        while self.__time[-1] - self.__time[0] > self.__window_duration and len(self.__time) >= 2:
            self.__time.popleft()
            self.__sum_distance -= self.__distance.popleft()

    def get(self):
        duration = self.__time[-1] - self.__time[0]
        return self.__sum_distance / duration if duration else 0


def get_siq_urls(offset, pages, vk_group_url, cache_dir, user_agent):
    base_url = urllib.parse.urlparse(vk_group_url)
    for page in range(pages):
        url = make_page_url(offset=offset, page=page, vk_group_url=vk_group_url)
        content, _ = get_page(url=url, user_agent=user_agent, cache_dir=cache_dir)
        for siq_link in get_siq_links(content):
            yield urllib.parse.urlunparse(urllib.parse.ParseResult(
                scheme=base_url.scheme,
                netloc=base_url.netloc,
                path=siq_link,
                params=None,
                query=None,
                fragment=None,
            ))


def get_urls(offset, pages, vk_group_url):
    for page in range(pages):
        yield make_page_url(offset=offset, page=page, vk_group_url=vk_group_url)


def get_siq_links(content):
    html = pyquery.PyQuery(content)
    for item in html('a.mr_label.medias_link').items():
        yield item.attr['href']


def fs_cached(extension, mode_suffix):
    def decorator(f):
        @functools.wraps(f)
        def impl(url, cache_dir, *args, **kwargs):
            os.makedirs(cache_dir, exist_ok=True)
            name = base64.b32encode(url.encode('utf-8')).decode('utf-8')
            data_path = os.path.join(cache_dir, '.'.join((name, extension)))
            meta_path = os.path.join(cache_dir, '.'.join((name, extension, 'meta', 'json')))
            print(f'Read {url} from cache {data_path}')
            if os.path.exists(data_path) and os.path.exists(meta_path):
                with open(data_path, 'r' + mode_suffix) as stream:
                    content = stream.read()
                meta = read_json(meta_path)
                meta['cached'] = True
                return content, meta
            content, meta = f(url=url, *args, **kwargs)
            print(f'Write {url} to cache {data_path}')
            try:
                with open(data_path, 'w' + mode_suffix) as stream:
                    stream.write(content)
                with open(meta_path, 'w') as stream:
                    json.dump(meta, stream)
            except:
                if os.path.exists(data_path):
                    os.remove(data_path)
                if os.path.exists(meta_path):
                    os.remove(meta_path)
                raise
            return content, meta
        return impl
    return decorator


class BadResponse(RuntimeError):
    pass


class EmptyHistory(RuntimeError):
    pass


@fs_cached(extension='siq', mode_suffix='b')
def get_file(url, user_agent, **kwargs):
    print(f'Download file from {url}')
    response = requests.get(url=url, headers={'User-Agent': user_agent})
    if not response.status_code == 200:
        raise BadResponse(f'Response is not 200 OK: {response.status_code}')
    if not response.history:
        raise EmptyHistory(f'No file info')
    name = os.path.basename(urllib.parse.urlparse(response.history[-1].headers['Location']).path)
    return response.content, dict(name=name)


@fs_cached(extension='html', mode_suffix='')
@retry.retry(BadResponse, tries=3, delay=0.1, backoff=1.5)
def get_page(url, user_agent, **kwargs):
    print(f'Download page from {url}')
    response = requests.get(url=url, headers={'User-Agent': user_agent})
    if not response.status_code == 200:
        raise BadResponse(f'Response is not 200 OK: {response.status_code}')
    return response.content.decode(response.encoding), dict()


def make_page_url(offset, page, vk_group_url):
    return f'{vk_group_url}?offset={offset + 20 * page}'


if __name__ == "__main__":
    main()
