"""AST representation for the parser to output

Copyright (C) 2024 Alvin Zhang

This module is part of unordered-sql and is released under
the MIT License: https://github.com/SaltOverflow/unordered-sql/blob/main/LICENSE
"""

from dataclasses import dataclass, field
import my_token as tok


# Pull out into utility file at some point
# Also I'm starting to think that start-end is better than start-length
@dataclass
class StartAndLength:
    """References a string slice in the original text without copying"""

    start: int  # the index in the text
    length: int  # length of the string slice in the text


# At the moment we only support a limited subset of allowed expressions
# Another interesting pattern for expressions is the "array format":
# `t.a::int < 4 OR t.b = 'hi'` becomes
# <expr> = [t, a, int, 4, OR, <expr2>], [., ::, <, OR]
# <expr2> = [t, b, 'hi'], [., =]
@dataclass
class Expression:
    """eg. `t.a::int < 4 OR t.b = 'hi'`

    You should be creating instances of the derived classes instead of using
    this directly.
    """

    pass


@dataclass
class ValueExpression(Expression):
    """eg. `4`"""

    token: tok.Token  # only non-keywords, strings, numbers allowed


@dataclass
class ParenExpression(Expression):
    """eg. `(4 + 5)`"""

    left_paren: tok.Token  # only LEFT_PAREN
    expr: Expression
    right_paren: tok.Token | None  # only RIGHT_PAREN, or was unclosed


@dataclass
class BinaryExpression(Expression):
    """eg. `4 + 5`"""

    left: Expression
    operator: tok.Token  # operator tokens and keywords that are operators allowed
    right: Expression


@dataclass
class PlaceholderExpression(Expression):
    """For finishing an expression if we come across an unexpected token

    eg. `table1. + 5` (user's cursor is right after the .)
    """

    placeholder_text: str


@dataclass
class SelectField:
    """The `a` in `select a`"""

    expression: Expression
    alias_name: tok.Token | None = None


@dataclass
class SelectClause:
    """eg. `select a, b, c`"""

    fields: list[SelectField] = field(default_factory=list)


@dataclass
class FromField:
    """The `table1` in `from table1`"""

    table_name: Expression  # We only support dot-separated names right now
    alias_name: tok.Token | None = None


@dataclass
class FromClause:
    """eg. `from table1, table2"""

    fields: list[FromField] = field(default_factory=list)


@dataclass
class WhereClause:
    """eg. `where a < 4`"""

    expression: Expression


@dataclass
class UnknownSequence(StartAndLength):
    """A sequence of tokens that the parser doesn't know what to do with

    When parsing each clause, if the parser hits an unexpected token that it
    cannot recover from, all tokens afterwards (not including comments) will
    be put into these objects.
    When formatting, these sequences are wrapped in comments and moved to
    the start of the statement.
    """

    first_token: tok.Token  # The token that couldn't be parsed properly


@dataclass
class Statement(StartAndLength):
    """A file is made up of a list of these statements"""

    selects: list[SelectClause] = field(default_factory=list)
    froms: list[FromClause] = field(default_factory=list)
    wheres: list[WhereClause] = field(default_factory=list)
    # Note: tok.SpecialToken, but only the comment part
    # Limitation: comment location in statement is lost when formatting
    comments: list[tok.SpecialToken] = field(default_factory=list)
    unknowns: list[UnknownSequence] = field(default_factory=list)
