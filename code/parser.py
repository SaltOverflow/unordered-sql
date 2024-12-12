"""Parse the text into an AST

Copyright (C) 2024 Alvin Zhang

This module is part of unordered-sql and is released under
the MIT License: https://github.com/SaltOverflow/unordered-sql/blob/main/LICENSE
"""

from tokenizer import Tokenizer
import my_ast as ast
import my_token as tok


class Parser:
    """Given a string, produces an AST"""

    def __init__(self, text: str, start_position: int = 0):
        self.tokenizer: Tokenizer = Tokenizer(text, start_position)

    def parse_all(self) -> list[ast.Statement]:
        """Parse the entire text"""
        ret: list[ast.Statement] = []
        while True:
            token = self.consume_newline_semicolons()
            if (
                isinstance(token, tok.SpecialToken)
                and token.type == tok.SpecialTokenType.END_OF_STRING
            ):
                break
            ret.append(self.parse_statement())
        return ret

    class UnknownTokenException(Exception):
        """Signals an unknown token

        This is helpful so we can handle unknown tokens in one place
        """

        pass

    def consume_newline_semicolons(self):
        """Consume \\n and ; in order to get to the start of a statement

        Does not consume the returned token
        """
        token = self.tokenizer.peek()
        while isinstance(token, tok.PunctuationToken) and (
            token.type == tok.PunctuationTokenType.NEWLINE
            or token.type == tok.PunctuationTokenType.SEMICOLON
        ):
            self.tokenizer.consume()
            token = self.tokenizer.peek()
        return token

    def get_next_standard_token(self, parent_statement: ast.Statement) -> tok.Token:
        """Handles comments and the single newlines

        ie. if \\n is returned, caller knows that \\n\\n is ahead
        Does not consume the returned token
        """
        token = self.tokenizer.peek()
        while True:
            if (
                isinstance(token, tok.PunctuationToken)
                and token.type == tok.PunctuationTokenType.NEWLINE
            ):
                token2 = self.tokenizer.peek(2)
                if (
                    isinstance(token2, tok.PunctuationToken)
                    and token2.type == tok.PunctuationTokenType.NEWLINE
                ):
                    break
                else:
                    self.tokenizer.consume()
                    token = token2
            if isinstance(token, tok.SpecialToken) and (
                token.type == tok.SpecialTokenType.SINGLE_LINE_COMMENT
                or token.type == tok.SpecialTokenType.MULTI_LINE_COMMENT
            ):
                self.tokenizer.consume()
                parent_statement.comments.append(token)
                token = self.tokenizer.peek()
            else:
                break
        return token

    def parse_statement(self) -> ast.Statement:
        """Parse a statement, eg. `from table1 select a`

        self.tokenizer should be at the start of a statement
        """
        token = self.tokenizer.peek()
        ret = ast.Statement(start=token.start, length=token.length)
        prev_token_is_known = True
        while True:
            token = self.get_next_standard_token(ret)
            # Could put a self.tokenizer.consume() here to avoid infinite loops
            # This would consume SELECT/FROM/WHERE, which is a bit weird though
            token_is_known = True
            try:
                if isinstance(token, tok.NameToken):
                    if token.type == tok.NameTokenType.SELECT:
                        ret.selects.append(self.parse_select(ret))
                    elif token.type == tok.NameTokenType.FROM:
                        ret.froms.append(self.parse_from(ret))
                    elif token.type == tok.NameTokenType.WHERE:
                        ret.wheres.append(self.parse_where(ret))
                    else:
                        raise self.UnknownTokenException()
                elif isinstance(token, tok.PunctuationToken):
                    if token.type == tok.PunctuationTokenType.SEMICOLON:
                        ret.length = (
                            self.tokenizer.end_idx_of_last_consumed_token - ret.start
                        )
                        self.tokenizer.consume()
                        break
                    elif token.type == tok.PunctuationTokenType.NEWLINE:
                        # If we see newline here, we know there are actually
                        # at least two newlines waiting to be consumed
                        ret.length = (
                            self.tokenizer.end_idx_of_last_consumed_token - ret.start
                        )
                        self.tokenizer.consume()
                        self.tokenizer.consume()
                        break
                    else:
                        raise self.UnknownTokenException()
                elif isinstance(token, tok.SpecialToken):
                    if token.type == tok.SpecialTokenType.END_OF_STRING:
                        ret.length = (
                            self.tokenizer.end_idx_of_last_consumed_token - ret.start
                        )
                        break
                    else:
                        raise self.UnknownTokenException()
                else:
                    raise self.UnknownTokenException
            except self.UnknownTokenException:
                self.tokenizer.consume()
                token_is_known = False
                if prev_token_is_known:
                    ret.unknowns.append(
                        ast.UnknownSequence(token.start, token.length, token)
                    )
                else:
                    ret.unknowns[-1].length = (
                        token.start + token.length - ret.unknowns[-1].start
                    )
            prev_token_is_known = token_is_known
        return ret

    def parse_select(self, parent_statement: ast.Statement) -> ast.SelectClause:
        """Parse select clause, eg. `select t.a, b, c > 5 as is_cool`"""
        # See more syntax options at
        # https://learn.microsoft.com/en-us/sql/t-sql/queries/select-clause-transact-sql?view=sql-server-ver16
        # Consume SELECT token
        self.tokenizer.consume()
        ret = ast.SelectClause()
        while True:
            # We don't allow commas here
            expression = self.parse_expression(
                parent_statement, tok.comma_precedence - 1
            )
            token = self.get_next_standard_token(parent_statement)
            if isinstance(token, tok.NameToken) and token.type == tok.NameTokenType.AS:
                # Note that this does not throw error on `select a as, b`
                self.tokenizer.consume()
                token = self.get_next_standard_token(parent_statement)
            # Would be good to return diagnostic if 'tablename' used here

            if (
                isinstance(token, tok.NameToken)
                and token.type == tok.NameTokenType.NON_KEYWORD
                or isinstance(token, tok.SpecialToken)
                and token.type == tok.SpecialTokenType.DOUBLE_QUOTE_STRING
            ):
                self.tokenizer.consume()
                ret.fields.append(ast.SelectField(expression, token))
                token = self.get_next_standard_token(parent_statement)
            else:
                ret.fields.append(ast.SelectField(expression))
            # Consume a comma or break out of the loop
            if (
                isinstance(token, tok.PunctuationToken)
                and token.type == tok.PunctuationTokenType.COMMA
            ):
                self.tokenizer.consume()
            else:
                break
        # We always return something, even if it's the placeholder expression
        return ret

    def parse_from(self, parent_statement: ast.Statement) -> ast.FromClause:
        """Parse from clause, eg. `from table`"""
        # See more syntax options at
        # https://learn.microsoft.com/en-us/sql/t-sql/queries/from-transact-sql?view=sql-server-ver16
        # Consume FROM token
        self.tokenizer.consume()
        ret = ast.FromClause()
        while True:
            # Only allow dot-separated here
            # This allows stuff like `(4 + 5)."hello"` but wtv
            expression = self.parse_expression(
                parent_statement,
                tok.operator_to_precedence[tok.PunctuationTokenType.DOT],
            )
            # This part is pretty much identical to parse_select(), except it
            # uses FromField. They may diverge in the future, so leave for now
            token = self.get_next_standard_token(parent_statement)
            if isinstance(token, tok.NameToken) and token.type == tok.NameTokenType.AS:
                # Note that this does not throw error on `from s.t1 as, t2`
                self.tokenizer.consume()
                token = self.get_next_standard_token(parent_statement)
            if (
                isinstance(token, tok.NameToken)
                and token.type == tok.NameTokenType.NON_KEYWORD
                or isinstance(token, tok.SpecialToken)
                and token.type == tok.SpecialTokenType.DOUBLE_QUOTE_STRING
            ):
                self.tokenizer.consume()
                ret.fields.append(ast.FromField(expression, token))
                token = self.get_next_standard_token(parent_statement)
            else:
                ret.fields.append(ast.FromField(expression))
            # Consume a comma or break out of the loop
            if (
                isinstance(token, tok.PunctuationToken)
                and token.type == tok.PunctuationTokenType.COMMA
            ):
                self.tokenizer.consume()
            else:
                break
        return ret

    def parse_where(self, parent_statement: ast.Statement) -> ast.WhereClause:
        """Parse where clause, eg. `where t.a < 4 AND t.b = 'hi'`"""
        # Consume WHERE token
        self.tokenizer.consume()
        # We don't allow commas here
        expression = self.parse_expression(parent_statement, tok.comma_precedence - 1)
        return ast.WhereClause(expression)

    def parse_expression(
        self, parent_statement: ast.Statement, expression_precedence: int
    ) -> ast.Expression:
        """Parse expression, staying within the specified precedence bounds

        parent_statement is for storing comments we come across.
        If a binary operator exceeds expression_precedence or has none,
        we stop parsing the expression.
        """
        expression = self.parse_non_binary_expression(parent_statement)
        if isinstance(expression, ast.PlaceholderExpression):
            return expression

        while True:
            binop = self.get_next_standard_token(parent_statement)
            if not (
                isinstance(binop, tok.NameToken)
                or isinstance(binop, tok.PunctuationToken)
            ):
                return expression
            binop_precedence = tok.operator_to_precedence.get(
                binop.type, tok.comma_precedence + 1
            )
            if binop_precedence > expression_precedence:
                return expression
            self.tokenizer.consume()

            next_expression = self.parse_expression(
                parent_statement, binop_precedence - 1
            )
            expression = ast.BinaryExpression(expression, binop, next_expression)
            if isinstance(next_expression, ast.PlaceholderExpression):
                return expression

    def parse_non_binary_expression(
        self, parent_statement: ast.Statement
    ) -> ast.Expression:
        """Parse a non-binary expression"""
        # We can extend to support prefix operators pretty easily
        # Also function support
        # None of this is type-aware though
        # Is there a way to add `*` for select clause without affecting where?
        # Also note that \n\n will delimit a statement, even if we are nested,
        # which I'm going to say is fine
        # Can't use SQL keywords as unquoted names, fine for now
        token = self.get_next_standard_token(parent_statement)
        try:
            # loop construct is used to handle comments
            while True:
                if isinstance(token, tok.NameToken):
                    if token.type == tok.NameTokenType.NON_KEYWORD:
                        self.tokenizer.consume()
                        ret = ast.ValueExpression(token)
                    else:
                        raise self.UnknownTokenException()
                elif isinstance(token, tok.NumberToken):
                    self.tokenizer.consume()
                    ret = ast.ValueExpression(token)
                elif isinstance(token, tok.PunctuationToken):
                    if token.type == tok.PunctuationTokenType.LEFT_PAREN:
                        self.tokenizer.consume()
                        # We allow commas here
                        ret = self.parse_expression(
                            parent_statement, tok.comma_precedence
                        )
                        token2 = self.get_next_standard_token(parent_statement)
                        if (
                            isinstance(token2, tok.PunctuationToken)
                            and token2.type == tok.PunctuationTokenType.RIGHT_PAREN
                        ):
                            self.tokenizer.consume()
                            ret = ast.ParenExpression(token, ret, token2)
                        else:
                            ret = ast.ParenExpression(token, ret, None)
                    else:
                        raise self.UnknownTokenException()
                elif isinstance(token, tok.SpecialToken):
                    if token.type == tok.SpecialTokenType.SINGLE_QUOTE_STRING:
                        self.tokenizer.consume()
                        ret = ast.ValueExpression(token)
                    elif token.type == tok.SpecialTokenType.DOUBLE_QUOTE_STRING:
                        self.tokenizer.consume()
                        ret = ast.ValueExpression(token)
                    elif token.type == tok.SpecialTokenType.SINGLE_LINE_COMMENT:
                        self.tokenizer.consume()
                        parent_statement.comments.append(token)
                        continue
                    elif token.type == tok.SpecialTokenType.MULTI_LINE_COMMENT:
                        self.tokenizer.consume()
                        parent_statement.comments.append(token)
                        continue
                    else:
                        raise self.UnknownTokenException()
                else:
                    # Doesn't get hit, but just to be complete
                    raise self.UnknownTokenException()
                break
        except self.UnknownTokenException:
            return ast.PlaceholderExpression("1")
        return ret


if __name__ == "__main__":
    from pprint import pprint

    # Limitations:
    # `b as`
    # `3.4.2`
    # `==` is invalid but no diagnostic
    # `in`
    text = """\
    select a
    where t or t2.a
    """
    print(repr(text[0:12]))
    parser = Parser(text, 12)
    statements = parser.parse_all()
    pprint(statements)
