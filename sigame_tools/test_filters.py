import collections
import pytest

from sigame_tools.filters import make_filter


TYPES = dict(i=int, s=str, l=[str])

Value = collections.namedtuple('Value', tuple(TYPES.keys()))


@pytest.mark.parametrize(
    "values,filtered",
    [
        ([], []),
        (
            [Value(i=1, s='a', l=['x'])],
            [Value(i=1, s='a', l=['x'])],
        ),
    ]
)
def test_empty_filter(values, filtered):
    f = make_filter(
        args=[],
        types=TYPES,
    )
    assert list(filter(f, values)) == filtered


def test_filter_include_by_int():
    f = make_filter(
        args=[('include', 'i', 42)],
        types=TYPES,
    )
    values = [Value(i=42, s='a', l=['x'])]
    filtered = [Value(i=42, s='a', l=['x'])]
    assert list(filter(f, values)) == filtered


def test_filter_include_by_str():
    f = make_filter(
        args=[('include', 's', 'a+')],
        types=TYPES,
    )
    values = [Value(i=1, s='baaa', l=['x'])]
    filtered = [Value(i=1, s='baaa', l=['x'])]
    assert list(filter(f, values)) == filtered


def test_filter_include_by_list_item():
    f = make_filter(
        args=[('include', 'l', 'x+')],
        types=TYPES,
    )
    values = [Value(i=1, s='a', l=['yxy'])]
    filtered = [Value(i=1, s='a', l=['yxy'])]
    assert list(filter(f, values)) == filtered


def test_filter_exclude_by_int():
    f = make_filter(
        args=[('exclude', 'i', 42)],
        types=TYPES,
    )
    values = [Value(i=42, s='a', l=['x'])]
    filtered = []
    assert list(filter(f, values)) == filtered


def test_filter_include_by_str():
    f = make_filter(
        args=[('exclude', 's', 'a+')],
        types=TYPES,
    )
    values = [Value(i=1, s='baaa', l=['x'])]
    filtered = []
    assert list(filter(f, values)) == filtered


def test_filter_exclude_by_list_item():
    f = make_filter(
        args=[('exclude', 'l', 'x+')],
        types=TYPES,
    )
    values = [Value(i=1, s='a', l=['yxy'])]
    filtered = []
    assert list(filter(f, values)) == filtered


def test_filter_force_include_by_int():
    f = make_filter(
        args=[('force_include', 'i', 42)],
        types=TYPES,
    )
    values = [Value(i=42, s='a', l=['x'])]
    filtered = [Value(i=42, s='a', l=['x'])]
    assert list(filter(f, values)) == filtered


@pytest.mark.parametrize(
    "values,filtered",
    [
        ([], []),
        (
            [Value(i=1, s='a', l=['x'])],
            [Value(i=1, s='a', l=['x'])],
        ),
        (
            [Value(i=1, s='b', l=['x'])],
            [],
        ),
        (
            [Value(i=1, s='a', l=['x']), Value(i=2, s='b', l=['y'])],
            [Value(i=1, s='a', l=['x'])],
        ),
        (
            [Value(i=1, s='a', l=['x']), Value(i=2, s='a', l=['y'])],
            [Value(i=1, s='a', l=['x']), Value(i=2, s='a', l=['y'])],
        ),
    ]
)
def test_filter_single_include(values, filtered):
    f = make_filter(
        args=[('include', 's', 'a')],
        types=TYPES,
    )
    assert list(filter(f, values)) == filtered


@pytest.mark.parametrize(
    "values,filtered",
    [
        ([], []),
        (
            [Value(i=1, s='a', l=['x'])],
            [],
        ),
        (
            [Value(i=1, s='b', l=['x'])],
            [Value(i=1, s='b', l=['x'])],
        ),
        (
            [Value(i=1, s='a', l=['x']), Value(i=2, s='b', l=['y'])],
            [Value(i=2, s='b', l=['y'])],
        ),
        (
            [Value(i=1, s='a', l=['x']), Value(i=2, s='a', l=['y'])],
            [],
        ),
    ]
)
def test_filter_single_exclude(values, filtered):
    f = make_filter(
        args=[('exclude', 's', 'a')],
        types=TYPES,
    )
    assert list(filter(f, values)) == filtered


@pytest.mark.parametrize(
    "values,filtered",
    [
        ([], []),
        (
            [Value(i=1, s='a', l=['x'])],
            [],
        ),
        (
            [Value(i=1, s='b', l=['x'])],
            [],
        ),
        (
            [Value(i=1, s='a', l=['x']), Value(i=2, s='b', l=['y'])],
            [],
        ),
        (
            [Value(i=1, s='a', l=['x']), Value(i=2, s='a', l=['y'])],
            [],
        ),
    ]
)
def test_filter_include_then_exclude_same(values, filtered):
    f = make_filter(
        args=[('include', 's', 'a'), ('exclude', 's', 'a')],
        types=TYPES,
    )
    assert list(filter(f, values)) == filtered


@pytest.mark.parametrize(
    "values,filtered",
    [
        (
            [Value(i=1, s='a', l=['x'])],
            [],
        ),
        (
            [Value(i=1, s='b', l=['x'])],
            [],
        ),
        (
            [Value(i=1, s='a', l=['x']), Value(i=2, s='b', l=['y'])],
            [],
        ),
        (
            [Value(i=1, s='a', l=['x']), Value(i=2, s='a', l=['y'])],
            [],
        ),
    ]
)
def test_filter_include_then_exclude_same_with_other_field_exclude(values, filtered):
    f = make_filter(
        args=[('include', 's', 'a'), ('exclude', 's', 'a'), ('exclude', 'l', 'z')],
        types=TYPES,
    )
    assert list(filter(f, values)) == filtered


@pytest.mark.parametrize(
    "values,filtered",
    [
        ([], []),
        (
            [Value(i=1, s='a', l=['x'])],
            [],
        ),
        (
            [Value(i=1, s='b', l=['x'])],
            [Value(i=1, s='b', l=['x'])],
        ),
        (
            [Value(i=1, s='a', l=['x']), Value(i=2, s='b', l=['y'])],
            [Value(i=2, s='b', l=['y'])],
        ),
        (
            [Value(i=1, s='a', l=['x']), Value(i=2, s='a', l=['y'])],
            [],
        ),
    ]
)
def test_filter_include_all_then_exclude_specific(values, filtered):
    f = make_filter(
        args=[('include', 's', '.*'), ('exclude', 's', 'a')],
        types=TYPES,
    )
    assert list(filter(f, values)) == filtered


@pytest.mark.parametrize(
    "values,filtered",
    [
        ([], []),
        (
            [Value(i=1, s='a', l=['x'])],
            [],
        ),
        (
            [Value(i=1, s='b', l=['x'])],
            [Value(i=1, s='b', l=['x'])],
        ),
        (
            [Value(i=1, s='a', l=['x']), Value(i=2, s='b', l=['y'])],
            [Value(i=2, s='b', l=['y'])],
        ),
        (
            [Value(i=1, s='a', l=['x']), Value(i=2, s='a', l=['y'])],
            [],
        ),
    ]
)
def test_filter_exclude_specific_then_include_all(values, filtered):
    f = make_filter(
        args=[('exclude', 's', 'a'), ('include', 's', '.*')],
        types=TYPES,
    )
    assert list(filter(f, values)) == filtered


@pytest.mark.parametrize(
    "values,filtered",
    [
        ([], []),
        (
            [Value(i=1, s='a', l=['x'])],
            [Value(i=1, s='a', l=['x'])],
        ),
        (
            [Value(i=1, s='b', l=['x'])],
            [],
        ),
        (
            [Value(i=2, s='b', l=['x'])],
            [Value(i=2, s='b', l=['x'])],
        ),
        (
            [Value(i=1, s='a', l=['x']), Value(i=2, s='b', l=['y'])],
            [Value(i=1, s='a', l=['x']), Value(i=2, s='b', l=['y'])],
        ),
        (
            [Value(i=1, s='a', l=['x']), Value(i=2, s='a', l=['y'])],
            [Value(i=1, s='a', l=['x']), Value(i=2, s='a', l=['y'])],
        ),
    ]
)
def test_filter_include_by_one_field_then_include_by_other(values, filtered):
    f = make_filter(
        args=[('include', 's', 'a'), ('include', 'i', 2)],
        types=TYPES,
    )
    assert list(filter(f, values)) == filtered


@pytest.mark.parametrize(
    "values,filtered",
    [
        ([], []),
        (
            [Value(i=1, s='a', l=['x'])],
            [Value(i=1, s='a', l=['x'])],
        ),
        (
            [Value(i=1, s='b', l=['x'])],
            [],
        ),
        (
            [Value(i=2, s='a', l=['x'])],
            [],
        ),
    ]
)
def test_filter_include_by_one_field_then_exclude_by_other(values, filtered):
    f = make_filter(
        args=[('include', 's', 'a'), ('exclude', 'i', 2)],
        types=TYPES,
    )
    assert list(filter(f, values)) == filtered


@pytest.mark.parametrize(
    "values,filtered",
    [
        (
            [Value(i=1, s='a', l=['x']), Value(i=2, s='b', l=['y']), Value(i=3, s='c', l=['z'])],
            [Value(i=1, s='a', l=['x']), Value(i=2, s='b', l=['y'])],
        ),
    ]
)
def test_filter_include_by_one_field_mutually_exclusive_values(values, filtered):
    f = make_filter(
        args=[('include', 's', 'a'), ('include', 's', 'b')],
        types=TYPES,
    )
    assert list(filter(f, values)) == filtered


@pytest.mark.parametrize(
    "values,filtered",
    [
        (
            [Value(i=1, s='a', l=['x']), Value(i=2, s='b', l=['y']), Value(i=3, s='c', l=['z'])],
            [Value(i=3, s='c', l=['z'])],
        ),
    ]
)
def test_filter_exclude_by_one_field_mutually_exclusive_values(values, filtered):
    f = make_filter(
        args=[('exclude', 's', 'a'), ('exclude', 's', 'b')],
        types=TYPES,
    )
    assert list(filter(f, values)) == filtered
