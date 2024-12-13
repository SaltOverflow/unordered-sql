"""First attempt at setting up unordered SQL

Copyright (C) 2024 Alvin Zhang

This module is part of unordered-sql and is released under
the MIT License: https://github.com/SaltOverflow/unordered-sql/blob/main/LICENSE

Does not semantically parse each command past a simple SELECT + following text,
which is important for any autocomplete capabilities. As such, we're redoing it
with proper tokenizing and parsing.
"""

from dataclasses import dataclass, field
from enum import StrEnum, auto
import re
import textwrap

###########################################
# Approach 1: Do multiple regex searches on the text before parsing
# A quick-and-dirty way to show proof-of-concept, but not great for extending
# because it does multiple passes through the text, which doesn't scale in
# performance or maintainability for more complex tasks like expression parsing

# Initially I thought it would be easier to set it up this way, but it ended up
# being quite complicated to keep track of indexes, even with the language
# being very simple

# Let's not bother parsing inside the clauses
text = """
select * from table where i < 3;  # comment
from table2 select a  # here's another select comment

from table3 where a < b select a  # from here to there
# This is not a break;
select b,
       c

FROM table4
WHERE a < 4
WHERE i = 2
SELECT a, b, c
from table5
where a = x
select y
"""

keyword_ranges = tuple(
    (m.start(), m.end()) for m in re.finditer(r"\b(select|from|where)\b", text, re.I)
)

statement_separator_ranges = tuple(
    (m.start(), m.end()) for m in re.finditer(r"\n\n|;", text)
) + ((len(text), len(text)),)

comment_ranges = tuple((m.start(), m.end()) for m in re.finditer(r"#.*", text))


def escape_comments(ranges: tuple[tuple[int, int]]) -> tuple[tuple[int, int]]:
    return tuple(
        x
        for x in ranges
        if not any(low <= x[0] < high for (low, high) in comment_ranges)
    )


keyword_ranges = escape_comments(keyword_ranges)
statement_separator_ranges = escape_comments(statement_separator_ranges)


class ClauseType(StrEnum):
    SELECT = auto()
    FROM = auto()
    WHERE = auto()


@dataclass
class Clause:
    """The key indexes of a clause

    Example:
    "select  a, b, c  # comment\nfrom ..."
        clause_type = SELECT
        clause_start_idx = index of 's'
        content_start_idx = index of first space
        clause_end_idx = index of 'f'
    """

    clause_type: ClauseType
    clause_start_idx: int
    content_start_idx: int
    clause_end_idx: int


statements: list[list[Clause]] = []
keyword_idx = 0  # iterating over keyword_ranges
comment_idx = 0  # iterating over comment_ranges
for separator_idx in range(len(statement_separator_ranges)):
    separator_position = statement_separator_ranges[separator_idx][0]
    statement = []
    while keyword_idx < len(keyword_ranges):
        keyword_start, keyword_end = keyword_ranges[keyword_idx]
        if separator_position < keyword_start:
            break
        first_char = text[keyword_start].lower()
        if first_char == "s":
            clause_type = ClauseType.SELECT
        elif first_char == "f":
            clause_type = ClauseType.FROM
        elif first_char == "w":
            clause_type = ClauseType.WHERE
        else:
            raise Exception(
                "unknown clause: %s at %d" % text[keyword_start : keyword_start + 10],
                keyword_start,
            )
        clause_start_idx = keyword_start
        content_start_idx = keyword_end
        clause_end_idx = separator_position
        if keyword_idx + 1 < len(keyword_ranges):
            clause_end_idx = min(clause_end_idx, keyword_ranges[keyword_idx + 1][0])
        statement.append(
            Clause(clause_type, clause_start_idx, content_start_idx, clause_end_idx)
        )
        keyword_idx += 1
    if statement:
        statements.append(statement)


print(repr(text))
for idx, statement in enumerate(statements):
    print(f"STATEMENT {idx}:")
    for clause in statement:
        print(repr(clause))
        print(repr(text[clause.clause_start_idx : clause.clause_end_idx]))
    print("\n")


new_text = ""
cursor = 0
for statement in statements:
    start_idx = statement[0].clause_start_idx
    end_idx = statement[-1].clause_end_idx
    selects: list[Clause] = []
    froms: list[Clause] = []
    wheres: list[Clause] = []
    for clause in statement:
        if clause.clause_type == ClauseType.SELECT:
            selects.append(clause)
        elif clause.clause_type == ClauseType.FROM:
            froms.append(clause)
        elif clause.clause_type == ClauseType.WHERE:
            wheres.append(clause)
    new_statement_text = ""
    if selects:
        for idx, select in enumerate(selects):
            if idx == 0:
                new_statement_text += "select "
            else:
                new_statement_text += ", "
            clause_content = text[select.content_start_idx : select.clause_end_idx]
            new_statement_text += clause_content
            if "#" in clause_content and clause_content[-1] != "\n":
                new_statement_text += "\n"
            elif not clause_content[-1].isspace():
                new_statement_text += " "
    else:
        new_statement_text += "select * "
    for idx, from_ in enumerate(froms):
        if idx == 0:
            new_statement_text += "from "
        else:
            new_statement_text += ", "
        clause_content = text[from_.content_start_idx : from_.clause_end_idx]
        new_statement_text += clause_content
        if "#" in clause_content and clause_content[-1] != "\n":
            new_statement_text += "\n"
        elif not clause_content[-1].isspace():
            new_statement_text += " "
    for idx, where in enumerate(wheres):
        if idx == 0:
            new_statement_text += "where "
        else:
            new_statement_text += "and "
        new_statement_text += "("
        clause_content = text[where.content_start_idx : where.clause_end_idx]
        new_statement_text += clause_content
        if "#" in clause_content and clause[-1] != "\n":
            new_statement_text += "\n"
        new_statement_text += ") "
    new_text += text[cursor:start_idx]
    new_text += new_statement_text
    cursor = end_idx

print(new_text)
print()
print()
print("Approach 2:")

#################################
# Approach 2: Build the AST while iterating through the text
# This is a bit more workable and standard practice, though if I wanted to set
# up autocomplete at some point, I'd need to parse the expressions themselves.
# So taking the learnings of a rudimentary prototyping session, let's actually
# set up a proper tokenizer and parser. Similar to gcc, I'm opting for a
# recursive-descent parser + operator precedence parser combination rather than
# LALR parser generator. This is because I want fine-grained control over
# memory management (indexes instead of string copies) and the ability to
# easily extend the parser to handle multiple dialects (which would change
# the grammar completely and require a recompilation)

# An alternative is to adapt an existing SQL parser to handle this language
# (and I do intend to try out that approach at some point), but at this
# prototyping stage I'd like to try hand-rolling the code myself and understand
# the principles at the base-level


@dataclass
class StartAndLength:
    start_idx: int = -1
    length: int = -1


@dataclass
class Statement(StartAndLength):
    # These flags are used when formatting
    is_semicolon_terminated: bool = False
    is_multiline: bool = False
    # Holds the contents of each clause
    selects: list[StartAndLength] = field(default_factory=list)
    froms: list[StartAndLength] = field(default_factory=list)
    wheres: list[StartAndLength] = field(default_factory=list)


text = """\
select a
select b
select c
from table

where i < 3 and b == 'hello';

from table2 select a ;
from table2 select a

from table2 select a
where i > 4
select b
where b < 3
"""

cursor = 0
statements: list[Statement] = []
non_whitespace = re.compile(r"\S")
clause_or_eos = re.compile(r"\b(select|from|where)\b|\n\n|;", re.IGNORECASE)
newline = re.compile(r"\n")
while cursor < len(text):
    # Move to start of statement
    statement = Statement()
    m = non_whitespace.search(text, cursor)
    if m is None:
        break
    cursor = m.start()
    statement.start_idx = cursor
    # Parse clauses
    prev_clause_type = "0"
    prev_clause_start_idx = -1
    while True:
        m = clause_or_eos.search(text, cursor)
        if m is None:
            m_start, m_end = len(text), len(text)
            while text[m_start - 1].isspace():
                m_start -= 1
            clause_type = "\n"
        else:
            m_start, m_end = m.start(), m.end()
            clause_type = text[m_start].lower()
        clause_start_idx = m_end
        while clause_start_idx < len(text) and text[clause_start_idx].isspace():
            clause_start_idx += 1
        cursor = m_end
        # We insert the previous clause
        if prev_clause_type != "0":
            prev_clause_end_idx = m_start - 1
            while text[prev_clause_end_idx].isspace():
                prev_clause_end_idx -= 1
            prev_clause = StartAndLength(
                prev_clause_start_idx, prev_clause_end_idx - prev_clause_start_idx + 1
            )
            if prev_clause_type == "s":
                statement.selects.append(prev_clause)
            elif prev_clause_type == "f":
                statement.froms.append(prev_clause)
            elif prev_clause_type == "w":
                statement.wheres.append(prev_clause)
            else:
                print("This shouldn't happen. Continue")
        if clause_type == ";" or clause_type == "\n":
            statement.is_semicolon_terminated = clause_type == ";"
            statement.length = m_start - statement.start_idx
            break
        prev_clause_type = clause_type
        prev_clause_start_idx = clause_start_idx
    # Check if statement is multiline
    m = newline.search(
        text, statement.start_idx, statement.start_idx + statement.length
    )
    statement.is_multiline = m is not None
    statements.append(statement)

print(*statements, sep="\n\n")
