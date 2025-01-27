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

"""Tests for ir_printer."""

import textwrap

from typing import Any, Optional

from absl.testing import absltest
from fiddle.codegen.auto_config import code_ir
from fiddle.codegen.auto_config import ir_printer
from fiddle.codegen.auto_config import test_fixtures


class A:

  def __str__(self):
    return "A_str"

  def __repr__(self):
    return "A_repr"


class IrPrinterTest(absltest.TestCase):

  def test_format_expr_primitives(self):
    self.assertEqual(ir_printer.format_expr(1), "1")
    self.assertEqual(ir_printer.format_expr(None), "None")
    self.assertEqual(ir_printer.format_expr(0.123), "0.123")
    self.assertEqual(ir_printer.format_expr(A()), "<<<custom:A_repr>>>")
    self.assertEqual(ir_printer.format_expr(int), "int")
    self.assertEqual(ir_printer.format_expr(Any), "typing.Any")
    self.assertIn(
        ir_printer.format_expr(Optional[str]),
        # This differs based on the Python verison.
        {"typing.Union[str, NoneType]", "typing.Optional[str]"},
    )

  def test_format_containers(self):
    foo = {"a": int, "b": str, "c": Any}
    self.assertEqual(
        ir_printer.format_expr(foo), '{"a": int, "b": str, "c": typing.Any}'
    )
    example_list = [3, 2.5, str]
    self.assertEqual(ir_printer.format_expr(example_list), "[3, 2.5, str]")
    example_tuple = (3, 2.5, str)
    self.assertEqual(ir_printer.format_expr(example_tuple), "(3, 2.5, str)")
    example_tuple = ()
    self.assertEqual(ir_printer.format_expr(example_tuple), "()")
    example_tuple = (3,)
    self.assertEqual(ir_printer.format_expr(example_tuple), "(3,)")

  def test_format_call(self):
    call = code_ir.Call(
        name=code_ir.Name("foo_fixture"),
        arg_expressions={code_ir.Name("bar"): 777},
    )
    self.assertEqual(ir_printer.format_expr(call), "foo_fixture(bar=777)")

  def test_format_simple_ir(self):
    task = test_fixtures.simple_ir()
    code = "\n".join(ir_printer.format_fn(task.top_level_call.fn))
    self.assertEqual(
        code,
        textwrap.dedent(
            """
    def simple_ir_fixture():
      return fdl.Config(fiddle.codegen.auto_config.test_fixtures.foo, x=4)
    """
        ).strip(),
    )

  def test_format_simple_shared_variable_ir(self):
    task = test_fixtures.simple_shared_variable_ir()
    code = "\n".join(ir_printer.format_fn(task.top_level_call.fn))
    self.assertEqual(
        code,
        textwrap.dedent(
            """
    def simple_shared_variable_ir_fixture():
      shared = {"a": 7}
      return [shared, shared]
    """
        ).strip(),
    )


if __name__ == "__main__":
  absltest.main()
