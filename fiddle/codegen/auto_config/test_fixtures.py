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

"""Some manually-generated code intermediate representations for testing."""

import dataclasses
import functools

import fiddle as fdl
from fiddle import arg_factory
from fiddle.codegen.auto_config import code_ir
from fiddle.codegen.auto_config import init_task
from fiddle.experimental import auto_config


def foo(x):
  return x


@dataclasses.dataclass
class SharedType:
  x: int
  z: float


global_counter = {"count": 0}


def count(increment: int):
  global_counter["count"] += increment
  return global_counter["count"]


@auto_config.auto_config
def auto_config_arg_factory_fn():
  return arg_factory.partial(
      functools.partial(
          SharedType,
          z=4.7,
      ),
      x=functools.partial(count, increment=3),
  )


def simple_ir() -> code_ir.CodegenTask:
  """Returns a single fixture bound to a config.

  Code:

  def simple_ir_fixture():
    return fdl.Config(foo, x=4)
  """
  config = fdl.Config(foo, x=4)
  fn = code_ir.FixtureFunction(
      name=code_ir.Name("simple_ir_fixture", is_generated=False),
      parameters=[],
      variables=[],
      output_value=config,
  )
  call_instance = code_ir.CallInstance(
      fn, parent=None, children={}, parameter_values={}, output_value=config
  )
  return code_ir.CodegenTask(config, top_level_call=call_instance)


def simple_shared_variable_ir() -> code_ir.CodegenTask:
  """Returns a single fixture bound to a config.

  Code:

  def simple_shared_variable_ir_fixture():
    shared = {"a": 7}
    return [shared, shared]
  """
  shared = {"a": 7}
  config = [shared, shared]

  shared_name = code_ir.Name("shared")
  fn = code_ir.FixtureFunction(
      name=code_ir.Name("simple_shared_variable_ir_fixture"),
      parameters=[],
      variables=[code_ir.VariableDeclaration(shared_name, shared)],
      output_value=[
          code_ir.VariableReference(shared_name),
          code_ir.VariableReference(shared_name),
      ],
  )
  call_instance = code_ir.CallInstance(
      fn, parent=None, children={}, parameter_values={}, output_value=config
  )
  return code_ir.CodegenTask(config, top_level_call=call_instance)


def unprocessed_shared_config() -> code_ir.CodegenTask:
  """Returns a single fixture bound to a config.

  There's no exact code representation of this, before we extract shared
  variables.

  def unprocessed_shared_config_fixture():
    # *actually* a shared value.
    return [SharedType(foo(3), 7.0), SharedType(foo(3), 7.0)]
  """
  foo_call = fdl.Config(foo, 3)
  shared = fdl.Config(SharedType, foo_call, 7.0)
  config = [shared, shared]
  return init_task.init_task(
      config, top_level_fixture_name="unprocessed_shared_config_fixture"
  )


def unprocessed_two_shared_config() -> code_ir.CodegenTask:
  """Returns a single fixture bound to a config.

  There's no exact code representation of this, before we extract shared
  variables.

  def unprocessed_two_shared_fixture():
    # *actually* shared values.
    return [SharedType(foo(3), 7.0), SharedType(foo(3), 7.0), foo(3)]
  """
  foo_call = fdl.Config(foo, 3)
  shared = fdl.Config(SharedType, foo_call, 7.0)
  config = [shared, shared, foo_call]
  return init_task.init_task(
      config, top_level_fixture_name="unprocessed_two_shared_fixture"
  )


def parameters_for_testcases():
  """Returns parameters for absl's parameterized test cases."""
  return [
      {
          "testcase_name": "simple_ir",
          "task": simple_ir(),
      },
      {
          "testcase_name": "simple_shared_variable_ir",
          "task": simple_shared_variable_ir(),
      },
  ]
