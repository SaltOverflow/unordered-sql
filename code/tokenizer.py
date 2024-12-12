"""Provides the tokenizer, so the parser handles tokens instead of raw text

Copyright (C) 2024 Alvin Zhang

This module is part of unordered-sql and is released under
the MIT License: https://github.com/SaltOverflow/unordered-sql/blob/main/LICENSE
"""

import my_token as tok
import re


class Tokenizer:
    """Given a string, starts spitting out tokens

    <start_position> is the point in the string <text> we are at.
    Normally we call consume() to get the next token, however we sometimes
    need to peek ahead, in which case we call peek(k).
    If there are no more tokens to
    """

    def __init__(self, text: str, start_position: int = 0):
        self.text = text
        self.start_position = start_position
        self.peek_queue: list[tok.Token] = []
        # To figure out where the end of a statement is
        self.end_idx_of_last_consumed_token: int = -1

    def consume(self) -> tok.Token:
        """Return the next token

        Calling multiple times yields the tokens afterwards.
        If no more tokens to return, returns EOS token"""
        if self.peek_queue:
            ret = self.peek_queue[0]
            self.peek_queue = self.peek_queue[1:]
            self.start_position = ret.start + ret.length
        else:
            ret, self.start_position = self._search_next(self.start_position)
        self.end_idx_of_last_consumed_token = ret.start + ret.length
        return ret

    def peek(self, k: int = 1) -> tok.Token:
        """Return the tokens ahead of the current position

        Calling peek(1) returns the same token as consume().
        Calling multiple times does not change the current position.
        If no more tokens to return, returns EOS token"""
        assert k > 0
        position = (
            self.peek_queue[-1].start + self.peek_queue[-1].length
            if self.peek_queue
            else self.start_position
        )
        while len(self.peek_queue) < k:
            token, position = self._search_next(position)
            self.peek_queue.append(token)
        return self.peek_queue[k - 1]

    def _search_next(self, position: int) -> tuple[tok.Token, int]:
        """Return the next token and the new position in the text

        This function does not edit any class fields and only reads
        from self.text .
        """
        # See documentation of token.py for details of tokenizer limitations
        # Ignore all whitespace except \n
        while (
            position < len(self.text)
            and self.text[position].isspace()
            and self.text[position] != "\n"
        ):
            position += 1
        if position >= len(self.text):
            return (
                tok.SpecialToken(position, 0, tok.SpecialTokenType.END_OF_STRING, True),
                position,
            )
        start = position

        # NameToken
        if self.text[position].isalpha():
            position += 1
            while position < len(self.text) and (
                self.text[position].isalnum() or self.text[position] == "_"
            ):
                position += 1
            name_token_type = tok.text_to_name_token.get(
                self.text[start:position].lower(), tok.NameTokenType.NON_KEYWORD
            )
            return tok.NameToken(start, position - start, name_token_type), position

        # NumberToken
        if "0" <= self.text[position] <= "9":
            position += 1
            while position < len(self.text) and (
                "0" <= self.text[position] <= "9" or self.text[position] == "."
            ):
                position += 1
            return tok.NumberToken(start, position - start), position

        # Here onwards is PunctuationToken or SpecialToken
        # Strings
        if self.text[position] == '"':
            position += 1
            # Adapted from sqlparse. Only support backslash for now.
            # Note this allows multiline strings. Not sure if it's a good idea
            double_quoted_string = re.compile(r'(\\"|[^"])*"')
            m = double_quoted_string.match(self.text, position)
            if m is None:
                return tok.SpecialToken(
                    start,
                    len(self.text) - start,
                    tok.SpecialTokenType.DOUBLE_QUOTE_STRING,
                    False,
                ), len(self.text)
            else:
                return (
                    tok.SpecialToken(
                        start,
                        m.end() - start,
                        tok.SpecialTokenType.DOUBLE_QUOTE_STRING,
                    ),
                    m.end(),
                )
        elif self.text[position] == "'":
            position += 1
            single_quoted_string = re.compile(r"(\\'|[^'])*'")
            m = single_quoted_string.match(self.text, position)
            if m is None:
                return tok.SpecialToken(
                    start,
                    len(self.text) - start,
                    tok.SpecialTokenType.SINGLE_QUOTE_STRING,
                    False,
                ), len(self.text)
            else:
                return (
                    tok.SpecialToken(
                        start,
                        m.end() - start,
                        tok.SpecialTokenType.SINGLE_QUOTE_STRING,
                    ),
                    m.end(),
                )

        # Comments
        if position + 1 < len(self.text):
            if self.text[position : position + 2] == "--":
                position += 2
                newline = re.compile(r"\n")
                m = newline.search(self.text, position)
                if m is None:
                    return tok.SpecialToken(
                        start,
                        len(self.text) - start,
                        tok.SpecialTokenType.SINGLE_LINE_COMMENT,
                    ), len(self.text)
                else:
                    # The single line comment does not include the newline
                    return (
                        tok.SpecialToken(
                            start,
                            m.start() - start,
                            tok.SpecialTokenType.SINGLE_LINE_COMMENT,
                        ),
                        m.start(),
                    )
            elif self.text[position : position + 2] == "/*":
                position += 2
                # [\s\S] is like . but it includes \n
                multiline_comment = re.compile(r"[\s\S]*?\*/")
                m = multiline_comment.match(self.text, position)
                if m is None:
                    return tok.SpecialToken(
                        start,
                        len(self.text) - start,
                        tok.SpecialTokenType.MULTI_LINE_COMMENT,
                        False,
                    ), len(self.text)
                else:
                    return (
                        tok.SpecialToken(
                            start,
                            m.end() - start,
                            tok.SpecialTokenType.MULTI_LINE_COMMENT,
                        ),
                        m.end(),
                    )

        # Non-operator punctuation tokens
        non_operator_token_type = tok.text_to_non_operators.get(
            self.text[position], None
        )
        if non_operator_token_type is not None:
            position += 1
            return (
                tok.PunctuationToken(start, position - start, non_operator_token_type),
                position,
            )

        # Operator punctuation tokens
        operator = re.compile(r"[!@#^&*-+=|<>/%.:]+")
        m = operator.match(self.text, position)
        position += 1
        if m is None:
            return (
                tok.PunctuationToken(
                    start, position - start, tok.PunctuationTokenType.UNKNOWN_OPERATOR
                ),
                position,
            )
        else:
            operator_token_type = tok.text_to_punctuation_token.get(
                self.text[start : m.end()], tok.PunctuationTokenType.UNKNOWN_OPERATOR
            )
            return (
                tok.PunctuationToken(start, m.end() - start, operator_token_type),
                m.end(),
            )


if __name__ == "__main__":
    text = """\
    select a
    select b as, c as C
    select d, e E
    from schema.table  -- this is table!
    where i < 3.4.2 and b == 'hello';

    from "table2" select "in" ;
    from table2 select in   -- comment is not a select statement

    -- now this goes on a new line
    /* also this */

    from table2 as "t2" select a
    where i > /*3*/ 4
    from table t
    where t.a < 5 or t2.a < 5
    select b
    where b < 3
    """
    print(repr(text[0:12]))
    tokenizer = Tokenizer(text, 12)
    for i in range(100):
        token = tokenizer.consume()
        print(token)

        # print(i)
        # print(tokenizer.consume())
        # for j in range(1, 5):
        #     print(tokenizer.peek(j))
