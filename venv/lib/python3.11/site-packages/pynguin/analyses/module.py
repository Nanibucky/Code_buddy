#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provides analyses for the subject module, based on the module and its AST."""
# from __future__ import annotations

# import ast
# import importlib
# import inspect
# import logging
# import sys
# from dataclasses import dataclass
# from types import ModuleType
# from typing import NamedTuple

# from pynguin.analyses.syntaxtree import FunctionDescription, get_function_descriptions
# from pynguin.utils.generic.genericaccessibleobject import (
#     GenericAccessibleObject,
#     GenericFunction,
# )
# from pynguin.utils.type_utils import function_in_module

# LOGGER = logging.getLogger(__name__)


# class _ParseResult(NamedTuple):
#     """A small data wrapper for the parsed result."""

# module: ModuleType
# syntax_tree: ast.AST | None


# @dataclass
# class ModuleElement:
#     """Contains all necessary information about an element of a module.

# An element of a module can be any callable, i.e., a class, method, or function.
# """

# name: str
# accessible: GenericAccessibleObject
# qualified_name: str | None
# description: FunctionDescription | None


# def parse_module(module_name: str) -> _ParseResult:
#     """Parses a module and extracts its module-type and AST.

# If the source code is not available it is not possible to build an AST.  In that
# case the respective field of the resulting tuple will contain the value ``None``.
# This is the case, for example, for modules written in native code, e.g., C.

# Args:
#     module_name: The fully-qualified name of the module

# Returns:
#     A tuple of the imported module type and its optional AST
# """
# module = importlib.import_module(module_name)
# try:
#     syntax_tree = ast.parse(
#         inspect.getsource(module),
#         filename=module_name.split(".")[-1] + ".py",
#         type_comments=True,
#         feature_version=sys.version_info[:2],
#     )
# except OSError as error:
#     LOGGER.warning(
#         f"Could not retrieve source code for module {module_name} ({error})"
#     )
#     syntax_tree = None
# result = _ParseResult(module=module, syntax_tree=syntax_tree)
# return result


# def extract_module_elements(module_name: str) -> list[ModuleElement]:
#     """

# Args:
#     module_name:

# Returns:

# """
# parse_result = parse_module(module_name)
# module_elements: list[ModuleElement] = []
# for func_name, func in inspect.getmembers(
#     parse_result.module, function_in_module(module_name)
# ):
#     generic_function = GenericFunction(func, None, func_name)
#     function_descriptions = get_function_descriptions(parse_result.syntax_tree)
#     element = ModuleElement(
#         name=func_name,
#         accessible=generic_function,
#         qualified_name=f"{module_name}.{func_name}",
#         description=function_descriptions[0],
#     )
#     module_elements.append(element)
# return module_elements
