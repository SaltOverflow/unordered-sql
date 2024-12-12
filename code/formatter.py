"""Produce the formatted statement (in SQL form)

Copyright (C) 2024 Alvin Zhang

This module is part of unordered-sql and is released under
the MIT License: https://github.com/SaltOverflow/unordered-sql/blob/main/LICENSE

Due to time constraints, this is very limited, but it's sufficient
to demonstrate the functionality of the system
"""

import my_ast as ast
import my_token as tok

class Formatter:
    def format_statement(self, text: str, statement: ast.Statement) -> str:
        """Returns a string representing the formatted statement"""
        ret = ''
        for comment in statement.comments:
            start, end = comment.start, comment.start + comment.length
            ret += text[start:end]
            if not comment.has_end_sequence:
                ret += ' */'
            ret += '\n'
        for unknown in statement.unknowns:
            start, end = unknown.start, unknown.start + unknown.length
            ret += '-- UNKNOWN SEQUENCE: `'
            ret += text[start:end]
            ret += '`\n'
        if not statement.selects:
            if statement.froms:
                ret += 'SELECT *\n'
        else:
            ret += 'SELECT\n'
        for idx, select in enumerate(statement.selects):
            ret += '    '
            fields = []
            for field in select.fields:
                field_string = self.format_expression(text, field.expression)
                if field.alias_name is not None:
                    field_string += ' AS '
                    start, end = field.alias_name.start, field.alias_name.start + field.alias_name.length
                    field_string += text[start:end]
                    # Filling in missing end pieces. Should move somewhere else
                    # Not going to bother for the others rn, low on time
                    token = field.alias_name
                    if isinstance(token, tok.SpecialToken) and token.type == tok.SpecialTokenType.DOUBLE_QUOTE_STRING and token.has_end_sequence == False:
                        field_string += '"'
                fields.append(field_string)
            ret += ', '.join(fields)
            if idx < len(statement.selects) - 1:
                ret += ','
            ret += '\n'
        if statement.froms:
            ret += 'FROM\n'
        # Sloppy hack to showcase reducing duplicate table reductions
        # Doesn't really work the way I want it to, but will do for a demo
        # (to do it properly with alias handling may require name rewriting,
        #  which leads to potential name clashing, which is really complex)
        seen_tables: set[tuple[str, str | None]] = set()
        for idx, from_ in enumerate(statement.froms):
            ret += '    '
            fields = []
            for field in from_.fields:
                # Idea: Have better string representations
                if isinstance(field.table_name, ast.ValueExpression) and isinstance(field.table_name.token, tok.NameToken):
                    token = field.table_name.token
                    start, end = token.start, token.start + token.length
                    if text[start:end] in seen_tables:
                        continue
                    seen_tables.add(text[start:end])
                field_string = self.format_expression(text, field.table_name)
                if field.alias_name is not None:
                    field_string += ' AS '
                    start, end = field.alias_name.start, field.alias_name.start + field.alias_name.length
                    field_string += text[start:end]
                fields.append(field_string)
            ret += ', '.join(fields)
            if idx < len(statement.froms) - 1:
                ret += ','
            ret += '\n'
        # Related to seen_tables hack
        last_char = -1
        while ret[last_char].isspace() or ret[last_char] == ',':
            last_char -= 1
        ret = ret[:last_char+1] + '\n'
        for idx, where in enumerate(statement.wheres):
            if idx == 0:
                ret += 'WHERE '
            else:
                ret += 'AND '
            if isinstance(where.expression, ast.BinaryExpression) and tok.operator_to_precedence[where.expression.operator.type] > tok.operator_to_precedence[tok.NameTokenType.AND]:
                ret += '('
                ret += self.format_expression(text, where.expression)
                ret += ')'
            else:
                ret += self.format_expression(text, where.expression)
            ret += '\n'
        return ret

    def format_expression(self, text: str, expression: ast.Expression) -> str:
        """Returns a string representing a formatted expression"""
        # It's more efficient to pass in a string and append to it,
        # but that's a simple change (also this is easier to prototype)
        if isinstance(expression, ast.ValueExpression):
            start, end = expression.token.start, expression.token.start + expression.token.length
            return text[start:end]
        elif isinstance(expression, ast.ParenExpression):
            return '(' + self.format_expression(text, expression.expr) + ')'
        elif isinstance(expression, ast.BinaryExpression):
            left = self.format_expression(text, expression.left)
            right = self.format_expression(text, expression.right)
            op_start, op_end = expression.operator.start, expression.operator.start + expression.operator.length
            operator = text[op_start:op_end]
            if tok.operator_to_precedence[expression.operator.type] <= 2:
                return left + operator + right
            else:
                return left + ' ' + operator + ' ' + right
        elif isinstance(expression, ast.PlaceholderExpression):
            return expression.placeholder_text

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
    where t.a < 5 or t2.a < 5
    select b
    where b < 3

    -- Automatic insertion of SELECT *
    from table

    -- Example in the README
    FROM table t SELECT t.a, t.b WHERE t.a > 3

    FROM table2 t2 SELECT t2.x, t2.y

    FROM table t SELECT t.a, t.b WHERE t.a > 3
    WHERE t.b = t2.y
    FROM table2 t2 SELECT t2.x, t2.y

    -- Duplicate table removal
    from table select a
    from table select b as "hello"""
    statements = Parser(text).parse_all()
    for statement in statements:
        print(Formatter().format_statement(text, statement))
        print()
