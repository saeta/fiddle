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

"""Tests for shared_to_variables."""

from absl.testing import absltest
from fiddle.codegen.auto_config import code_ir
from fiddle.codegen.auto_config import init_task
from fiddle.codegen.auto_config import ir_printer
from fiddle.codegen.auto_config import make_symbolic_references
from fiddle.codegen.auto_config import shared_to_variables
from fiddle.codegen.auto_config import test_fixtures
from fiddle.testing.example import fake_encoder_decoder


class SharedToVariablesTest(absltest.TestCase):

  def test_works_on_toy_example(self):
    task = test_fixtures.unprocessed_shared_config()
    make_symbolic_references.import_symbols(task)
    shared_to_variables.move_shared_nodes_to_variables(task)
    make_symbolic_references.replace_callables_and_configs_with_symbols(task)
    self.assertLen(task.top_level_call.fn.variables, 1)

  def test_fails_on_unnameable_example(self):
    shared = {"a": 7}
    config = [shared, shared]
    task = init_task.init_task(config)
    with self.assertRaisesRegex(
        ValueError, r"Could not generate any candidate names for \{'a': 7\}"
    ):
      shared_to_variables.move_shared_nodes_to_variables(task)

  def test_works_on_toy_example_two_vars(self):
    task = test_fixtures.unprocessed_two_shared_config()
    shared_to_variables.move_shared_nodes_to_variables(task)
    self.assertLen(task.top_level_call.fn.variables, 2)

    intermediate_code = ir_printer.format_task(task)
    self.assertIn("foo = ", intermediate_code)
    self.assertIn("shared_type = ", intermediate_code)
    self.assertIn("return [shared_type, shared_type, foo]", intermediate_code)

  def test_fake_encoder_decoder(self):
    task = init_task.init_task(fake_encoder_decoder.fixture.as_buildable())
    shared_to_variables.move_shared_nodes_to_variables(task)
    self.assertLen(task.top_level_call.fn.variables, 1)

  def test_avoids_name_collisions(self):
    task = test_fixtures.unprocessed_shared_config()

    # Note: This doesn't strictly respect the API, the key should be a Call.
    # If this is ever required by another part of the code, then make up a
    # fake Call to use as a key.
    task.top_level_call.children[None] = code_ir.CallInstance(
        fn=code_ir.FixtureFunction(
            code_ir.Name("shared_type"),
            [],
            [],
            None,
        ),
        parent=None,
        children={},
        parameter_values={},
        output_value=None,
    )
    shared_to_variables.move_shared_nodes_to_variables(task)
    intermediate_code = ir_printer.format_task(task)
    self.assertNotIn("shared_type =", intermediate_code)


if __name__ == "__main__":
  absltest.main()
