# Unordered SQL

Answers the question "What if SQL, but the clauses can be in any order?" (also have multiple clauses of the same type in the same statement)

Unordered SQL seeks to address some problems with modularity and autocomplete, while still retaining the conciseness of regular SQL. In other words, all regular SQL should be Unordered SQL, but Unordered SQL offers more flexibility.

One key point is that Unordered SQL is fairly trivial to transform into equivalent regular SQL. Indeed, combining clauses is a matter of appending fields and `AND`-ing conditions, with a slight bit of complexity when it comes to removing duplicate tables (consider `FROM table FROM table ...`). This is important because Unordered SQL is meant to be used as a "drafting language" - you query the database and experiment using it, but before using in production you convert to regular SQL for better readability.

The last sentence is worth emphasizing, because while Unordered SQL is easier to write, it can end up being much harder to read. As such, it's best to follow a specific format like `FROM-SELECT-WHERE` and convert to regular SQL when the statement gets larger. Unordered SQL is at its best when you use its features sparingly, such as "I want to run the same query, but also peek at a few more columns" .

### File structure

`code/` holds the source code of the project

`commentary/` adds some historical context to the thought process behind some of the decisions made in the code.

### Modularity and autocomplete

To showcase modularity, consider the following SQL statement:

```
SELECT a, b
--     c
FROM table
WHERE condition
-- AND condition2
```

To add `c` to the SELECT clause, we would also have to add a comma to the first line. And if you wanted to use `condition2` instead of `condition` , you would need to replace the `AND` keyword with `WHERE` . With Unordered SQL, you can have them be a second SELECT and WHERE clause, respectively.

Here is an example of Unordered SQL in action:

```
FROM table t SELECT t.a, t.b WHERE t.a > 3
WHERE t.b = t2.y
FROM table2 t2 SELECT t2.x, t2.y
```

Here the second line was added last, which means that the first and third line used to be separate statements which were developed separately. Then they were "joined" with the clause `WHERE t.b = t2.y` (Unordered SQL uses \n\n or ; to separate statements).

The benefits of autocomplete over regular SQL is relatively straightforward: Allowing the `FROM` clauses to be before `SELECT` clauses allows you to have autocomplete when typing select fields.