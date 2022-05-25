# coding=utf-8
# Copyright 2022 The Fiddle-Config Authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Tests for fiddle.diff."""

import copy
import dataclasses
import re
from typing import Any
from absl.testing import absltest
import fiddle as fdl
from fiddle.experimental import daglish
from fiddle.experimental import diff


# Functions and classes that can be used to build Configs.
@dataclasses.dataclass
class SimpleClass:
  x: Any
  y: Any
  z: Any


@dataclasses.dataclass
class AnotherClass:
  x: Any
  y: Any
  a: Any
  b: Any


def make_pair(first, second):
  return (first, second)


def make_triple(first, second, third):
  return (first, second, third)


def basic_fn(arg1, arg2, kwarg1=0, kwarg2=None):
  return {'a': arg1 + arg2, 'b': arg2 + kwarg1, 'c': kwarg2}


# Helper function to make expected Paths easier to write (and read).
# Handles a limited set of paths (e.g., only Keys where type(key)=str.)
def parse_path(s: str) -> daglish.Path:
  """Build a daglish Path from a string."""
  make_path_re = re.compile(r'\.(?P<attr>\w+)|'
                            r'\[(?P<index>\d+)\]|'
                            r'\[(?P<key>\'[^\']*\'|\"[^\"]+\")\]|'
                            r'(?P<error>.)')

  path = []
  for m in make_path_re.finditer(s):
    if m.group('attr'):
      if m.group('attr') == '__fn_or_cls__':
        path.append(daglish.BuildableFnOrCls())
      else:
        path.append(daglish.Attr(m.group('attr')))
    elif m.group('index'):
      path.append(daglish.Index(int(m.group('index'))))
    elif m.group('key'):
      path.append(daglish.Key(m.group('key')[1:-1]))
    else:
      raise ValueError(f'Unable to parse path {s!r} at {m}')
  return tuple(path)


# Helper function to make expected References easier to write (and read).
def parse_reference(s: str) -> diff.Reference:
  """Build a diff.Reference from a string."""
  match = re.match(r'([^\.\[]*)(.*)', s)
  assert match is not None
  root, path = match.groups()
  return diff.Reference(root, parse_path(path))


class DiffAlignmentTest(absltest.TestCase):

  def test_constructor(self):
    old = fdl.Config(make_pair, fdl.Config(SimpleClass, 1, 2, 3),
                     fdl.Config(basic_fn, 4, 5, 6))
    new = fdl.Config(make_pair, fdl.Config(basic_fn, 1, 2, 3, 4),
                     fdl.Partial(SimpleClass, z=12))

    empty_alignment = diff.DiffAlignment(old, new)

    # No values should be aligned (including the root objects `old` and `new`).
    self.assertEmpty(empty_alignment.aligned_values())
    self.assertEmpty(empty_alignment.aligned_value_ids())
    self.assertFalse(empty_alignment.is_old_value_aligned(old))
    self.assertFalse(empty_alignment.is_new_value_aligned(new))
    self.assertEqual(empty_alignment.old_name, 'old')
    self.assertEqual(empty_alignment.new_name, 'new')

    self.assertEqual(
        repr(empty_alignment),
        "<DiffAlignment from 'old' to 'new': 0 object(s) aligned>")
    self.assertEqual(
        str(empty_alignment), 'DiffAlignment:\n    (no objects aligned)')

  def test_align(self):
    old = fdl.Config(make_pair, fdl.Config(SimpleClass, 1, 2, [3, 4]),
                     fdl.Config(basic_fn, 5, 6, 7))
    new = fdl.Config(make_pair, fdl.Config(basic_fn, 1, 2, 3, 4),
                     fdl.Partial(SimpleClass, z=[12, 13]))
    alignment = diff.DiffAlignment(old, new)
    alignment.align(old, new)  # Same type, same __fn_or_cls__.
    alignment.align(old.first, new.first)  # Different __fn_or_cls__.
    alignment.align(old.first.z, new.second.z)  # Aligned lists.

    self.assertIs(alignment.new_from_old(old), new)
    self.assertIs(alignment.old_from_new(new), old)
    self.assertIs(alignment.new_from_old(old.first), new.first)
    self.assertIs(alignment.old_from_new(new.first), old.first)
    self.assertIs(alignment.new_from_old(old.first.z), new.second.z)
    self.assertIs(alignment.old_from_new(new.second.z), old.first.z)

    with self.subTest('aligned_value_ids'):
      aligned_value_ids = alignment.aligned_value_ids()
      expected_aligned_value_ids = [
          diff.AlignedValueIds(id(old), id(new)),
          diff.AlignedValueIds(id(old.first), id(new.first)),
          diff.AlignedValueIds(id(old.first.z), id(new.second.z)),
      ]
      self.assertCountEqual(aligned_value_ids, expected_aligned_value_ids)

    with self.subTest('aligned_values'):
      aligned_values = alignment.aligned_values()
      expected_aligned_values = [
          diff.AlignedValues(old, new),
          diff.AlignedValues(old.first, new.first),
          diff.AlignedValues(old.first.z, new.second.z),
      ]
      aligned_values.sort(key=lambda p: id(p.old_value))
      expected_aligned_values.sort(key=lambda p: id(p.old_value))
      self.assertEqual(aligned_values, expected_aligned_values)

    with self.subTest('__repr__'):
      self.assertEqual(
          repr(alignment),
          "<DiffAlignment from 'old' to 'new': 3 object(s) aligned>")

    with self.subTest('__str__'):
      self.assertEqual(
          str(alignment), '\n'.join([
              'DiffAlignment:',
              '    old -> new',
              '    old.first -> new.first',
              '    old.first.z -> new.second.z',
          ]))

  def test_alignment_errors(self):
    old = fdl.Config(make_pair, fdl.Config(SimpleClass, [1], [2], [3]),
                     fdl.Config(basic_fn, 4, 5, 6))
    new = fdl.Config(make_pair, fdl.Config(basic_fn, [1], [2], 3, 4),
                     fdl.Partial(SimpleClass, z=[12, 13]))

    alignment = diff.DiffAlignment(old, new)
    alignment.align(old.first.x, new.first.arg1)

    with self.subTest('type(old_value) != type(new_value)'):
      with self.assertRaisesRegex(diff.AlignmentError, '.* different types .*'):
        alignment.align(old.second, new.second)

    with self.subTest('old_value already aligned'):
      with self.assertRaisesRegex(
          diff.AlignmentError,
          'An alignment has already been added for old value .*'):
        alignment.align(old.first.x, new.first.arg2)

    with self.subTest('new_value already aligned'):
      with self.assertRaisesRegex(
          diff.AlignmentError,
          'An alignment has already been added for new value .*'):
        alignment.align(old.first.y, new.first.arg1)

    with self.subTest('len(old_value) != len(new_value)'):
      with self.assertRaisesRegex(diff.AlignmentError,
                                  '.* different lengths .*'):
        alignment.align(old.first.z, new.second.z)

    with self.subTest('non-memoizable old_value'):
      with self.assertRaisesRegex(
          diff.AlignmentError,
          'old_value=4 may not be aligned because it is not '
          'memoizable'):
        alignment.align(old.second.arg1, new.second.z)

    with self.subTest('non-memoizable new_value'):
      with self.assertRaisesRegex(
          diff.AlignmentError,
          'new_value=3 may not be aligned because it is not '
          'memoizable'):
        alignment.align(old.first.z, new.first.kwarg1)

  def test_align_by_id(self):
    old = fdl.Config(make_pair, fdl.Config(SimpleClass, 1, 2, [3, 4]),
                     fdl.Config(basic_fn, 5, 6, 7))
    new = fdl.Config(make_pair, old.first,
                     fdl.Partial(SimpleClass, z=old.first.z))
    alignment = diff.align_by_id(old, new)
    self.assertCountEqual(alignment.aligned_values(), [
        diff.AlignedValues(old.first.z, new.second.z),
        diff.AlignedValues(old.first, new.first),
    ])

  def test_align_heuristically(self):
    c = fdl.Config(SimpleClass)  # Shared object (same id) in `old` and `new`
    d = fdl.Config(SimpleClass, x='bop')
    old = fdl.Config(
        make_triple,
        first=fdl.Config(SimpleClass, x=1, y=2, z=[3, 4]),
        second=fdl.Config(basic_fn, arg1=[5], arg2=5, kwarg1=c),
        third=[[1], 2])
    new = fdl.Config(
        make_triple,
        first=fdl.Config(basic_fn, arg1=1, arg2=c, kwarg1=3, kwarg2=4),
        second=fdl.Partial(basic_fn, arg1=[8], arg2=[3, 4], kwarg1=d),
        third=[[1, 2], 2, [3, 4]])
    alignment = diff.align_heuristically(old, new)
    self.assertCountEqual(
        alignment.aligned_values(),
        [
            # Values aligned by id:
            diff.AlignedValues(old.second.kwarg1, new.first.arg2),
            # Values aligned by path:
            diff.AlignedValues(old, new),
            diff.AlignedValues(old.first, new.first),
            diff.AlignedValues(old.second.arg1, new.second.arg1),
            # Values aligned by equality:
            diff.AlignedValues(old.first.z, new.second.arg2),
        ])


class ReferenceTest(absltest.TestCase):

  def test_repr(self):
    reference = diff.Reference(
        'old', (daglish.Attr('foo'), daglish.Index(1), daglish.Key('bar')))
    self.assertEqual(repr(reference), "<Reference: old.foo[1]['bar']>")


class DiffTest(absltest.TestCase):

  def test_str(self):
    cfg_diff = diff.Diff(
        changes={
            parse_path('.foo[1]'):
                diff.ModifyValue(2),
            parse_path('.foo[2]'):
                diff.SetValue(parse_reference('old.bar')),
            parse_path('.bar.x'):
                diff.DeleteValue(),
            parse_path('.bar.y'):
                diff.ModifyValue(parse_reference('new_shared_value[0]')),
            parse_path('.bar.z'):
                diff.SetValue({'a': parse_reference('new_shared_value[0]')}),
        },
        new_shared_values=([1, 2, parse_reference('old.bar')],))
    expected_str = (
        'Diff(changes=[\n'
        '          .foo[1]: ModifyValue(new_value=2)\n'
        '          .foo[2]: SetValue(new_value=<Reference: old.bar>)\n'
        '          .bar.x: DeleteValue()\n'
        '          .bar.y: ModifyValue(new_value='
        '<Reference: '
        'new_shared_value[0]>)\n'
        '          .bar.z: SetValue(new_value='
        "{'a': <Reference: new_shared_value[0]>})\n"
        '      ],\n'
        '      new_shared_values=[\n'
        '          [1, 2, <Reference: old.bar>]\n'
        '      ])')
    self.assertEqual(str(cfg_diff), expected_str)


class DiffFromAlignmentBuilderTest(absltest.TestCase):

  def check_diff(self,
                 old,
                 new,
                 expected_changes,
                 expected_new_shared_values=()):
    """Checks that building a Diff generates the expected values.

    Builds a diff using a heuristic alignment between `old` and `new`, and
    then checks that `diff.changes` and `diff.new_shared_values` have the
    indicated values.

    Args:
      old: The `old` value for the diff.
      new: The `new` value for the diff.
      expected_changes: Dictionary mapping string path representations to
        DiffOperations.  The keys are parsed using `parse_path`.
      expected_new_shared_values: Tuple of value
    """
    alignment = diff.align_heuristically(old, new)
    cfg_diff = diff.build_diff_from_alignment(alignment)
    self.assertEqual(
        cfg_diff.changes,
        dict([(parse_path(p), c) for (p, c) in expected_changes.items()]))
    self.assertEqual(cfg_diff.new_shared_values, expected_new_shared_values)

  def make_test_diff_builder(self):
    """Returns a DiffBuilder that can be used for testing."""
    c = fdl.Config(SimpleClass)  # Shared object (same id)
    old = fdl.Config(make_pair, fdl.Config(SimpleClass, 1, 2, [3, 4]),
                     fdl.Config(basic_fn, [5], [6, 7], c))
    new = fdl.Config(make_pair, fdl.Config(basic_fn, 1, c, 3, 4.0),
                     fdl.Partial(basic_fn, [8], 9, [3, 4]))
    aligned_values = [
        diff.AlignedValues(old, new),
        diff.AlignedValues(old.first, new.first),
        diff.AlignedValues(old.second.arg1, new.second.arg1),
        diff.AlignedValues(old.second.kwarg1, new.first.arg2),
        diff.AlignedValues(old.first.z, new.second.kwarg1),
    ]
    alignment = diff.DiffAlignment(old, new)
    for aligned_value in aligned_values:
      alignment.align(aligned_value.old_value, aligned_value.new_value)
    return diff._DiffFromAlignmentBuilder(alignment)

  def test_modify_buildable_callable(self):
    old = fdl.Config(AnotherClass, fdl.Config(SimpleClass, 1, 2), 3)
    new = copy.deepcopy(old)
    fdl.update_callable(new, SimpleClass)
    fdl.update_callable(new.x, AnotherClass)
    expected_changes = {
        '.__fn_or_cls__': diff.ModifyValue(SimpleClass),
        '.x.__fn_or_cls__': diff.ModifyValue(AnotherClass)
    }
    self.check_diff(old, new, expected_changes)

  def test_modify_buildable_argument(self):
    old = fdl.Config(SimpleClass, 1, fdl.Config(AnotherClass, 2, 3))
    new = copy.deepcopy(old)
    new.x = 11
    new.y.x = 22
    expected_changes = {
        '.x': diff.ModifyValue(11),
        '.y.x': diff.ModifyValue(22)
    }
    self.check_diff(old, new, expected_changes)

  def test_modify_sequence_element(self):
    old = fdl.Config(SimpleClass, [1, 2, [3]])
    new = copy.deepcopy(old)
    new.x[0] = 11
    new.x[2][0] = 33
    expected_changes = {
        '.x[0]': diff.ModifyValue(11),
        '.x[2][0]': diff.ModifyValue(33)
    }
    self.check_diff(old, new, expected_changes)

  def test_modify_dict_item(self):
    old = fdl.Config(SimpleClass, {'a': 2, 'b': 4, 'c': {'d': 7}})
    new = copy.deepcopy(old)
    new.x['a'] = 11
    new.x['c']['d'] = 33
    expected_changes = {
        ".x['a']": diff.ModifyValue(11),
        ".x['c']['d']": diff.ModifyValue(33)
    }
    self.check_diff(old, new, expected_changes)

  def test_set_buildable_argument(self):
    old = fdl.Config(SimpleClass, 1, fdl.Config(AnotherClass, 2, 3))
    new = copy.deepcopy(old)
    new.z = 11
    new.y.a = 22
    expected_changes = {'.z': diff.SetValue(11), '.y.a': diff.SetValue(22)}
    self.check_diff(old, new, expected_changes)

  def test_set_dict_item(self):
    old = fdl.Config(SimpleClass, {'a': 2, 'b': 4, 'c': {'d': 7}})
    new = copy.deepcopy(old)
    new.x['foo'] = 11
    new.x['c']['bar'] = 33
    expected_changes = {
        ".x['foo']": diff.SetValue(11),
        ".x['c']['bar']": diff.SetValue(33)
    }
    self.check_diff(old, new, expected_changes)

  def test_delete_buildable_argument(self):
    old = fdl.Config(SimpleClass, 1, fdl.Config(AnotherClass, 2, 3),
                     fdl.Config(SimpleClass, 4))
    new = copy.deepcopy(old)
    del new.x
    del new.y.x
    del new.z
    expected_changes = {
        '.x': diff.DeleteValue(),
        '.y.x': diff.DeleteValue(),
        '.z': diff.DeleteValue()
    }
    self.check_diff(old, new, expected_changes)

  def test_delete_dict_item(self):
    old = fdl.Config(SimpleClass, {'a': 2, 'b': {}, 'c': {'d': 7}})
    new = copy.deepcopy(old)
    del new.x['a']
    del new.x['b']
    del new.x['c']['d']
    expected_changes = {
        ".x['a']": diff.DeleteValue(),
        ".x['b']": diff.DeleteValue(),
        ".x['c']['d']": diff.DeleteValue()
    }
    self.check_diff(old, new, expected_changes)

  def test_add_shared_new_objects(self):
    old = fdl.Config(
        SimpleClass,
        x=1,
        y=fdl.Config(SimpleClass, x=2, y=3, z=[12]),
        z=fdl.Config(SimpleClass, x=4))
    new = copy.deepcopy(old)
    new.x = [1, 2, [3, 4], new.y.z]
    new.y.x = new.x
    new.y.y = [99]
    new.z.y = fdl.Config(SimpleClass, new.x[2], new.y.y)
    expected_new_shared_values = (
        [3, 4],
        [
            1, 2,
            parse_reference('new_shared_value[0]'),
            parse_reference('old.y.z')
        ],
        [99],
    )
    expected_changes = {
        '.x':
            diff.ModifyValue(parse_reference('new_shared_value[1]')),
        '.y.x':
            diff.ModifyValue(parse_reference('new_shared_value[1]')),
        '.y.y':
            diff.ModifyValue(parse_reference('new_shared_value[2]')),
        '.z.y':
            diff.SetValue(
                fdl.Config(SimpleClass, parse_reference('new_shared_value[0]'),
                           parse_reference('new_shared_value[2]'))),
    }
    self.check_diff(old, new, expected_changes, expected_new_shared_values)

  def test_multiple_modifications(self):
    cfg_diff = self.make_test_diff_builder().build_diff()
    expected_changes = {
        '.first.__fn_or_cls__': diff.ModifyValue(basic_fn),
        '.first.x': diff.DeleteValue(),
        '.first.y': diff.DeleteValue(),
        '.first.z': diff.DeleteValue(),
        '.first.arg1': diff.SetValue(1),
        '.first.arg2': diff.SetValue(parse_reference('old.second.kwarg1')),
        '.first.kwarg1': diff.SetValue(3),
        '.first.kwarg2': diff.SetValue(4.0),
        '.second': diff.ModifyValue(
            fdl.Partial(basic_fn, parse_reference('old.second.arg1'),
                        9, parse_reference('old.first.z'))),
        '.second.arg1[0]': diff.ModifyValue(8)
    }  # pyformat: disable
    self.assertEqual(
        cfg_diff.changes,
        dict([(parse_path(p), c) for (p, c) in expected_changes.items()]))
    self.assertEqual(cfg_diff.new_shared_values, ())

  def test_replace_object_with_equal_value(self):
    c = SimpleClass(1, 2, 3)

    with self.subTest('with sharing'):
      old = fdl.Config(SimpleClass, x=c, y=[4, c, 5])
      new = copy.deepcopy(old)
      new.y[1] = SimpleClass(1, 2, 3)
      self.assertEqual(new.x, new.y[1])
      self.assertIsNot(new.x, new.y[1])
      # new.y[1] can't be aligned with old.y[1], since old.y[1] is the
      # same object as old.x, and new.x is not new.y[1].  So the diff generates
      # a new value.
      expected_changes = {'.y[1]': diff.ModifyValue(SimpleClass(1, 2, 3))}
      self.check_diff(old, new, expected_changes)

    with self.subTest('without sharing'):
      # But in this example, we change x=c to x=9, so now new.y[1] can be
      # aligned with old.y[1], and the diff contains no changes.
      old = fdl.Config(SimpleClass, x=9, y=[4, c, 5])
      new = copy.deepcopy(old)
      new.y[1] = SimpleClass(1, 2, 3)
      self.check_diff(old, new, {})

  def test_diff_from_alignment_builder_can_only_build_once(self):
    diff_builder = self.make_test_diff_builder()
    diff_builder.build_diff()
    with self.assertRaisesRegex(ValueError,
                                'build_diff should be called at most once'):
      diff_builder.build_diff()

  def test_aligned_or_equal(self):
    diff_builder = self.make_test_diff_builder()
    old = diff_builder.alignment.old
    new = diff_builder.alignment.new

    self.assertTrue(diff_builder.aligned_or_equal(old, new))
    self.assertTrue(diff_builder.aligned_or_equal(old.first, new.first))
    self.assertTrue(diff_builder.aligned_or_equal(old.first.x, new.first.arg1))
    self.assertTrue(
        diff_builder.aligned_or_equal(old.second.kwarg1, new.first.arg2))

    self.assertFalse(diff_builder.aligned_or_equal(old.second, new.second))
    self.assertFalse(diff_builder.aligned_or_equal(old.first.x, new.first.arg2))
    self.assertFalse(diff_builder.aligned_or_equal(old.second, new.second))
    self.assertFalse(
        diff_builder.aligned_or_equal(old.first.z[1], new.first.kwarg2))


if __name__ == '__main__':
  absltest.main()