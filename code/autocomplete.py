"""Provide autocomplete suggestions

Copyright (C) 2024 Alvin Zhang

This module is part of unordered-sql and is released under
the MIT License: https://github.com/SaltOverflow/unordered-sql/blob/main/LICENSE

Due to time constraints, we're doing a very limited set of suggestions,
specifically targeting column autocomplete. This is to highlight the
benefits of allowing FROM before SELECT
"""
import my_ast as ast
import my_token as tok

class Autocomplete:
    def __init__(self, table_to_column: dict[str, list[str]]) -> None:
        self.table_to_column = table_to_column
    
    def suggest(self, text: str, statements: list[ast.Statement], cursor: int) -> list[str] | None:
        """Suggest autocomplete options at the point of the cursor"""
        for statement in statements:
            if not(statement.start <= cursor <= statement.start + statement.length):
                continue
            tables_in_play = self.get_tables_and_aliases(text, statement)
            # print(f"{tables_in_play=}")
            for select in statement.selects:
                for field in select.fields:
                    suggestion = self.suggest_in_expression(text, cursor, field.expression, tables_in_play)
                    if suggestion is not None:
                        return suggestion
            for from_ in statement.froms:
                for field in from_.fields:
                    suggestion = self.suggest_in_from(text, cursor, field.table_name)
                    if suggestion is not None:
                        return suggestion
            for where in statement.wheres:
                suggestion = self.suggest_in_expression(text, cursor, where.expression, tables_in_play)
                if suggestion is not None:
                    return suggestion
        return None

    def extract_name_from_token(self, text: str, token: tok.Token, cursor: int | None = None) -> str | None:
        """Helper to extract name from token
        
        if cursor is None, we parse like normal
        if cursor is not None, only return what is before the cursor
        (if the cursor is not inside the token, return None)
        """
        start, end = token.start, token.start + token.length
        if cursor is not None:
            if not (start <= cursor <= end):
                return None
            end = cursor
        if isinstance(token, tok.NameToken) and token.type == tok.NameTokenType.NON_KEYWORD:
            name = text[start:end]
        elif isinstance(token, tok.SpecialToken) and token.type == tok.SpecialTokenType.DOUBLE_QUOTE_STRING:
            name = text[start+1:end]
            if name and name[-1] == '"':
                name = name[:-1]
        else:
            return None
        return name

    def get_tables_and_aliases(self, text: str, statement: ast.Statement) -> list[tuple[str, str | None]]:
        """Get list of tables and table aliases for the current statement"""
        ret: list[tuple[str, str | None]] = []
        for from_ in statement.froms:
            for field in from_.fields:
                if not isinstance(field.table_name, ast.ValueExpression):
                    continue
                name = self.extract_name_from_token(text, field.table_name.token)
                if name is None:
                    continue
                if field.alias_name is not None:
                    alias = self.extract_name_from_token(text, field.alias_name)
                else:
                    alias = None
                ret.append((name, alias))
        return ret

    def suggest_in_expression(self, text: str, cursor: int, expression: ast.Expression, tables_in_play: list[tuple[str, str | None]], predot_name: str | None = None) -> list[str] | None:
        """Make suggestions for names in an expression
        
        Note that we don't actually know if the cursor is in this expression,
        so we have to parse the entire expression. This can be refactored later
        text is to access the underlying strings (ast only holds text indexes)
        cursor is the text index where we want to provide autocomplete
        expression is the node of the ast that we're currently searching
        predot_name is `t2` while parsing the `c` in `t2.c`, otherwise None
        (note that the code assumes no multiple dot operator structure
        like `schema.t2.c` exists)
        """
        if isinstance(expression, ast.ValueExpression):
            name = self.extract_name_from_token(text, expression.token, cursor)
            if name is None:
                return None
            # This is the part of the function that actually does suggestions
            # print(f"Doing suggestion: {name=}")
            ret: list[str] = []
            if predot_name is not None:
                # eg. `t2.c` , predot_name = `t2` , name = `c`
                for table_name, table_alias in tables_in_play:
                    if predot_name != table_name and predot_name != table_alias:
                        continue
                    columns = self.table_to_column.get(table_name, [])
                    for column in columns:
                        if column.startswith(name):
                            ret.append(column)
            else:
                # Grabbing table aliases like this is slightly off because
                # we removed the double-quotes, but wtv
                for _, table_alias in tables_in_play:
                    if table_alias is not None and table_alias.startswith(name):
                        ret.append(table_alias)
                columns: list[str] = []
                for table_name, _ in tables_in_play:
                    columns.extend(self.table_to_column.get(table_name, []))
                for column in columns:
                    if column.startswith(name):
                        ret.append(column)
            return ret
        elif isinstance(expression, ast.ParenExpression):
            return self.suggest_in_expression(text, cursor, expression.expr, tables_in_play)
        elif isinstance(expression, ast.BinaryExpression):
            left = self.suggest_in_expression(text, cursor, expression.left, tables_in_play)
            if left is not None:
                return left
            op = expression.operator
            predot_name: str | None = None
            if isinstance(op, tok.PunctuationToken) and op.type == tok.PunctuationTokenType.DOT:
                if isinstance(expression.left, ast.ValueExpression):
                    predot_name = self.extract_name_from_token(text, expression.left.token)
            return self.suggest_in_expression(text, cursor, expression.right, tables_in_play, predot_name)
        return None

    def suggest_in_from(self, text: str, cursor: int, table_name: ast.Expression) -> list[str] | None:
        """Make suggestions for a table name in the FROM clause"""
        # This is relatively simple because we don't have schema scope
        # (see how table_to_column isn't like schema -> table -> column)
        # Due to the way PlaceholdeExpression is set up, you only have
        # autocomplete after you type the first character...
        if isinstance(table_name, ast.ValueExpression):
            name = self.extract_name_from_token(text, table_name.token, cursor)
            if name is None:
                return None
            # print(f"Table suggestion: {name=}")
            ret: list[str] = []
            for table in self.table_to_column:
                if table.startswith(name):
                    ret.append(table)
            return ret
        return None

if __name__ == '__main__':
    from parser import Parser
    # Partially handling unclosed strings and whatnot
    # If you have 2 identical froms, do you remove them? I assume you should,
    # but if you want to also handle aliasing you'd have to do type-checking
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
    from toodles foo
    where t.a < 5 or t2.a < 5
    select toodles.moo = foo.meow
    select b
    where b < 3

    from table

    from table select a
    from table select b as "hello"""
    statements = Parser(text).parse_all()
    table_to_column = {
        'table': ['art', 'arm', 'ack', 'd', 'e', 'integer'],
        'table2': ['integer', 'idea', 'insight'],
        'toodles': ['meow', 'moo', 'artful'],
        'sandwich': [],
        'inspiration': ['another'],
    }
    autocomplete = Autocomplete(table_to_column)
    # Below I've labeled some of my commentary on the tests with (limitation)
    # and (stylistic choice). It is worth noting that when I say "limitation",
    # it is a limitation of my code, not the specification of Unordered SQL.
    # Indeed, autocomplete is more of a showcase, and a proof that the parser
    # is working (ie. it is possible to write a parser for Unordered SQL).

    # 52:  unfortunately we don't handle schema namespaces right now, so this
    #      statement doesn't have autocomplete (limitation)
    # 145: we're at the very start of the table name (crucially, the system
    #      knows it's expecting a table name because the parser annotated that
    #      region [limitation]), so all tables are valid
    # 150: table and table2 are valid because `table` is fed into autocomplete
    #      (the `2` is to the right of the cursor and isn't considered)
    # 163: integer and insight is valid because table2 is in scope. However,
    #      the table inspiration is not
    # 192: in is parsed as a keyword, then thrown out of the statement, so it
    #      isn't considered performing autocomplete (limitation)
    # 220: comments and areas outside statements don't use autocomplete
    # 296: due to time constraints (it's also not the main feature of Unordered
    #      SQL), keywords don't have autocomplete (limitation)
    # 321: columns from table and toodles are valid here
    # 393: t2 and t are valid. I made a stylistic choice to not include the
    #      full table names. I could be convinced otherwise, but feels natural
    #      to only autocomplete with table aliases (stylistic choice)
    # 395: standard column lookup
    # 407: there is no column in table2 that starts with a
    # 432: standard column lookup with the full table name...
    # 445: which behaves the same as column lookup with the alias name
    for i in [52, 145, 150, 163, 192, 220, 296, 321, 393, 395, 407, 432, 445]:
        print(i)
        print(repr(text[i-50:i]))
        print(autocomplete.suggest(text, statements, i))
        print()
