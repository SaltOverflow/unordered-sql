"""All of the different types of tokens that can be returned from tokenizer.py

Copyright (C) 2024 Alvin Zhang

This module is part of unordered-sql and is released under
the MIT License: https://github.com/SaltOverflow/unordered-sql/blob/main/LICENSE

When tokenizing, we can fit into 4 broad categories:
* NameToken (starts with alphabet)
* NumberToken (starts with number)
* PunctuationToken (entirely nonalphanumeric)
* SpecialToken (starts with nonalphanumeric but isn't necessarily entirely so)
* (whitespace that isn't a newline isn't a token)

NameToken can represent SQL keywords or not (parser uses context to determine)
NumberToken represent integers or floats
PunctuationToken can represent "punctuation" like `\\n` or `;` , but also
  includes operators like `>=` and `%`
SpecialToken represent special sequences like `-- comment` and `'string'`
  (also includes the special END_OF_STRING character if nothing left to parse)

Some limitations that are deliberately ignored for now:
* `.1` is not treated like 0.1 to avoid scenarios like `a.1`
* `"tablename"` and `tablename` are separate token types, because the parser
  needs to treat `"from"` and `from` differently
* Leading underscores are not parsed right now, so `_column_name` is invalid
* Numbers are what's captured with the regex pattern `[0-9][0-9.]*` ,
  so `3e4` is invalid and `5.3.2` is valid right now
* \\r is ignored, and formatting will not only use \\n , not \\r\\n or the like
* Operators are treated as the longest sequence of "operator-like" characters.
  In other words, what is captured with the regex pattern `[!@#^&*-+=|<>/%.:]+`
  with special logic to avoid treating things like `--` as an operator.
  This means that `4++4` needs to be rewritten as `4+ +4` or `4 + +4` to work.
  Also, right now `<--` will also be treated as an operator.
  This is partly to simplify parsing (which is important because I want to
  extend the parser to handle multiple dialects of SQL), and partly to impose
  my idea of what my language should allow.
  In other words, if it can't be easily parsed, it's probably hard to read.
"""

from dataclasses import dataclass
from enum import StrEnum, auto


class NameTokenType(StrEnum):
    """Starts with alphabetic character"""

    # SELECT clauses
    SELECT = auto()
    FROM = auto()
    WHERE = auto()
    GROUP = auto()
    ORDER = auto()
    BY = auto()

    # INSERT clauses
    INSERT = auto()
    INTO = auto()
    VALUES = auto()

    # DELETE clauses
    DELETE = auto()

    # other keywords
    CASE = auto()
    USING = auto()
    AS = auto()
    DISTINCT = auto()

    NULL = auto()
    ASC = auto()
    DESC = auto()
    NULLS = auto()
    FIRST = auto()
    LAST = auto()
    EXISTS = auto()

    LEFT = auto()
    RIGHT = auto()
    FULL = auto()
    INNER = auto()
    OUTER = auto()
    STRAIGHT = auto()
    CROSS = auto()
    NATURAL = auto()
    JOIN = auto()
    ON = auto()

    UNION = auto()
    EXCEPT = auto()
    INTERSECT = auto()

    # operators
    IS = auto()
    NOT = auto()
    AND = auto()
    ALL_ = "all"
    ANY_ = "any"
    BETWEEN = auto()
    IN = auto()
    LIKE = auto()
    OR = auto()
    SOME = auto()

    # special (space to avoid matching as a keyword)
    NON_KEYWORD = " name"


class PunctuationTokenType(StrEnum):
    """Entirely nonalphanumeric"""

    # operators (by precedence)
    # precedence order adapted from
    # https://learn.microsoft.com/en-us/sql/t-sql/language-elements/operator-precedence-transact-sql?view=sql-server-ver16
    DOT = "."

    DOUBLE_COLON = "::"

    BIT_NOT = "~"

    LEFT_SHIFT = "<<"
    RIGHT_SHIFT = ">>"

    MULTIPLY = "*"
    DIVIDE = "/"
    MOD = "%"

    PLUS = "+"
    MINUS = "-"
    BIT_AND = "&"
    BIT_OR = "|"
    BIT_XOR = "^"

    EQUAL = "="
    LESS_THAN = "<"
    GREATER_THAN = ">"
    LESS_THAN_OR_EQUAL = "<="  # also !>
    GREATER_THAN_OR_EQUAL = ">="  # also !<
    NOT_EQUAL = "!="  # also <>

    # non-operators (does not follow maximal rule)
    SEMICOLON = ";"
    LEFT_PAREN = "("
    RIGHT_PAREN = ")"
    LEFT_BRACKET = "["
    RIGHT_BRACKET = "]"
    COMMA = ","
    NEWLINE = "\n"  # we'll do this form for now

    # special (space to avoid matching as a keyword)
    UNKNOWN_OPERATOR = " unknown"


# EOS would probably need to be broken out
# Also comments, for AST purposes
class SpecialTokenType(StrEnum):
    """Starts with nonalphanumeric but isn't necessarily entirely so

    Also includes the special END_OF_STRING token
    """

    SINGLE_QUOTE_STRING = " 'string'"
    DOUBLE_QUOTE_STRING = ' "string"'

    # comment
    SINGLE_LINE_COMMENT = " -- comment\n"
    MULTI_LINE_COMMENT = " /* comment */"

    # special
    END_OF_STRING = " EOS"


# Used to determine type of NameToken
text_to_name_token: dict[str, NameTokenType] = {
    x.value.lower(): x for x in NameTokenType
}


# Used to determine type of PunctuationToken
text_to_punctuation_token: dict[str, PunctuationTokenType] = {
    x.value.lower(): x for x in PunctuationTokenType
}


# These PunctuationTokens don't follow the "maximal regex rule" for operators
# (really, PunctuationToken should be broken into 2 types at this point)
text_to_non_operators: dict[str, PunctuationTokenType] = {
    ";": PunctuationTokenType.SEMICOLON,
    "(": PunctuationTokenType.LEFT_PAREN,
    ")": PunctuationTokenType.RIGHT_PAREN,
    "[": PunctuationTokenType.LEFT_BRACKET,
    "]": PunctuationTokenType.RIGHT_BRACKET,
    ",": PunctuationTokenType.COMMA,
    "\n": PunctuationTokenType.NEWLINE,
}


# For parsing, this is the order of precedence
# Due to time constraints we're only supporting binary operators
# Should dot be treated differently than the other operators?
# Consider `t.| + 2` where | is the cursor. The + would be treated like a prefix
# Precedences must be > 0 and the precedence of comma must be the highest
operator_to_precedence: dict[PunctuationTokenType | NameTokenType, int] = {
    PunctuationTokenType.DOT: 1,
    PunctuationTokenType.DOUBLE_COLON: 2,
    # PunctuationTokenType.BIT_NOT: 3,  # only supporting binary operators right now
    PunctuationTokenType.LEFT_SHIFT: 4,
    PunctuationTokenType.RIGHT_SHIFT: 4,
    PunctuationTokenType.MULTIPLY: 5,
    PunctuationTokenType.DIVIDE: 5,
    PunctuationTokenType.MOD: 5,
    PunctuationTokenType.PLUS: 6,
    PunctuationTokenType.MINUS: 6,
    PunctuationTokenType.BIT_AND: 6,
    PunctuationTokenType.BIT_OR: 6,
    PunctuationTokenType.BIT_XOR: 6,
    PunctuationTokenType.EQUAL: 7,
    PunctuationTokenType.LESS_THAN: 7,
    PunctuationTokenType.GREATER_THAN: 7,
    PunctuationTokenType.LESS_THAN_OR_EQUAL: 7,
    PunctuationTokenType.GREATER_THAN_OR_EQUAL: 7,
    PunctuationTokenType.NOT_EQUAL: 7,
    NameTokenType.IS: 7,
    NameTokenType.IN: 7,
    NameTokenType.LIKE: 7,
    # NameTokenType.NOT: 8,
    NameTokenType.AND: 9,
    NameTokenType.OR: 10,
    PunctuationTokenType.COMMA: 100,  # comma must have max precedence
}
# The highest operator precedence
comma_precedence = operator_to_precedence[PunctuationTokenType.COMMA]


# Using inheritance here might be a bit overkill - could use composition and
# type unions instead.
# However, not having to deal with nested lookups is nice, so leave for now
@dataclass
class Token:
    """Base class, used for semantic grouping

    You should be creating instances of the derived classes instead of using
    this directly.
    """

    start: int  # the index in the text
    length: int  # length of the token in the text


@dataclass
class NameToken(Token):
    """Starts with alphabetic character"""

    type: NameTokenType


@dataclass
class NumberToken(Token):
    """Starts with number character"""

    pass


@dataclass
class PunctuationToken(Token):
    """Entirely nonalphanumeric"""

    type: PunctuationTokenType


@dataclass
class SpecialToken(Token):
    """Starts with nonalphanumeric but isn't necessarily entirely so

    Also includes the special END_OF_STRING token
    """

    type: SpecialTokenType
    # Only applies to strings and multiline comments
    # (single line comments do not include the newline character)
    # Set to False if improperly terminated, like `"hello`
    has_end_sequence: bool = True
