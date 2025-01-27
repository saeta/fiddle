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

"""Intermediate representation APIs for auto_config code generation.

In this approach we model something close to the output code, and make passes
over it to refine its structure.
"""

from __future__ import annotations

import copy
import dataclasses
from typing import Any, Dict, List, Optional, Type

from fiddle import arg_factory
from fiddle import daglish
from fiddle.codegen import import_manager as import_manager_lib
from fiddle.codegen import namespace as namespace_lib
from fiddle.experimental import auto_config


@dataclasses.dataclass
class Name:
  """Represents the name of a variable/value/etc.

  Attributes:
    value: The string value of the name.
    is_generated: Whether the name is auto-generated.
    previous: Previous name, in case this name has been changed by a pass.
  """

  value: str
  is_generated: bool = True
  previous: Optional[Name] = None

  def __hash__(self):
    return id(self)

  def replace(self, new_name: str) -> None:
    """Mutable replacement method."""
    old_self = copy.copy(self)
    self.previous = old_self
    self.value = new_name

  def __str__(self):
    return self.value


@dataclasses.dataclass
class CodegenNode:
  """Base class for codegen nodes."""

  def __flatten__(self):
    names = [field.name for field in dataclasses.fields(self)]
    values = tuple(getattr(self, name) for name in names)
    return values, (names, type(self))

  def __path_elements__(self):
    names = [field.name for field in dataclasses.fields(self)]
    return tuple(daglish.Attr(name) for name in names)

  @classmethod
  def __unflatten__(cls, values, metadata):
    keys, typ = metadata
    return typ(**dict(zip(keys, values)))

  def __init_subclass__(cls):
    daglish.register_node_traverser(
        cls,
        flatten_fn=lambda x: x.__flatten__(),
        unflatten_fn=cls.__unflatten__,
        path_elements_fn=lambda x: x.__path_elements__(),
    )


@dataclasses.dataclass
class Parameter(CodegenNode):
  name: Name
  value_type: Type[Any]


@dataclasses.dataclass
class VariableReference(CodegenNode):
  """Reference to a variable or parameter."""

  name: Name


@dataclasses.dataclass
class SymbolReference(CodegenNode):
  """Reference to a library symbol, like MyEncoderLayer."""

  expression: str


@dataclasses.dataclass
class Call(CodegenNode):
  name: Name
  arg_expressions: Dict[Name, Any]  # Value that can involve VariableReference's


@dataclasses.dataclass
class SymbolCall(CodegenNode):
  """Reference to a call of a library symbol, like MyEncoderLayer()."""

  symbol_expression: str
  # Values for args can involve VariableReference's, Calls, etc.
  positional_arg_expressions: List[Any]
  arg_expressions: Dict[str, Any]


@dataclasses.dataclass
class FunctoolsPartialCall(SymbolCall):
  pass


@dataclasses.dataclass
class VariableDeclaration(CodegenNode):
  name: Name
  expression: Any  # Value that can involve VariableReference's


@dataclasses.dataclass
class FixtureFunction(CodegenNode):
  """Basic declaration of a function.

  Each auto_config function will have a name, and list of parameters. Its body
  will then be a list of variable declarations, followed by an output value
  in a `return` statement.
  """

  name: Name
  parameters: List[Parameter]
  variables: List[VariableDeclaration]
  output_value: Any  # Value that can involve VariableReference's

  def __hash__(self):
    return id(self)

  def replace_with(self, other: FixtureFunction) -> None:
    self.name = other.name
    self.parameters = other.parameters
    self.variables = other.variables
    self.output_value = other.output_value


@dataclasses.dataclass
class CallInstance:
  """Represents a concrete function call.

  This is more of a dataflow node than an expression of calling a function, i.e.
  it represents a call to a function at a particular point in the auto_config
  fixture's execution.
  """

  fn: FixtureFunction
  parent: Optional[CallInstance]
  children: Dict[Call, CallInstance]
  parameter_values: Dict[Name, Any]
  output_value: Any

  def __hash__(self) -> int:
    return id(self)

  def to_stack(self) -> List[CallInstance]:
    current = self
    result = [self]
    while current.parent is not None:
      current = current.parent
      result.append(current)
    return list(reversed(result))

  @arg_factory.supply_defaults
  def all_fixture_functions(
      self, seen=arg_factory.default_factory(set)
  ) -> List[FixtureFunction]:
    result = [] if self.fn in seen else [self.fn]
    for child in self.children.values():
      result.extend(child.all_fixture_functions(seen))
    return result


def _init_import_manager() -> import_manager_lib.ImportManager:
  return import_manager_lib.ImportManager(namespace=namespace_lib.Namespace())


@dataclasses.dataclass
class CodegenTask:
  """Encapsulates an entire task of code generation.

  Useful for combining dataflow and generated code.
  """

  original_config: Any
  top_level_call: CallInstance
  import_manager: import_manager_lib.ImportManager = dataclasses.field(
      default_factory=_init_import_manager
  )
  auto_config_fn: Any = auto_config.auto_config

  @property
  def global_namespace(self) -> namespace_lib.Namespace:
    return self.import_manager.namespace
