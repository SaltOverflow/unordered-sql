# December 12, 2024 Commentary on the codebase

These are my thoughts and rationale on the codebase as it stands on Dec 12, 2024.

This was originally written for the course project for my CS 842 course at UWaterloo. Hence the programming project proposal in the same folder. Note that what was envisioned in the proposal is different from what was ultimately written, given the limitations of time. You can also read the README for an overview of what Unordered SQL as a specification represents, such as its strengths and weaknesses.

The idea came about when working at my previous jobs. Namely, the scenarios demonstrated in the README were scenarios that I actually ran up against when writing SQL queries. It was originally about swapping the SELECT and FROM clauses, which would solve the nagging problem of autocomplete. After a few iterations of "can we do EVEN MORE?" it eventually evolved into this format. One could argue that this format is too flexible, and they might be right. At this stage in development however, it is all about prototyping and seeing how it would work / not work.

To try and formalize what Unordered SQL is, suppose that, in EBNF syntax, a SQL SELECT statement has the form:

```
select statement = "SELECT", select fields,
                   ["FROM", from fields],
                   ["WHERE", where fields], ";" ;
```

In Unordered SQL, this would have the form:

```
select statement = {"SELECT", select fields |
                    "FROM", from fields |
                    "WHERE", where fields}, (";" | "\n\n") ;
```

... as long as there is at least one SELECT clause or at least one FROM clause. If there is no SELECT clause, `SELECT *` is assumed. 

Evidently, SQL statements are more complex than this, but 1. This is a proof-of-concept; 2. The benefits of Unordered SQL over SQL diminish as the queries get bigger and more complex - at that point, writing too many out-of-order clauses will only make things more confusing. In fact, you could argue a similar case for regular SQL: As a SQL script gets more complex, it starts to feel more natural to work with a general-purpose programming language instead.

The code can be run by entering `python code/formatter.py` (or whatever file you want to run) into the command line. This code was developed using Python 3.12 .

## Tokenizer and token spec

At first, I wrote a simple parser (`initial_parser.py`) to get an idea of how to work with such a system. Python was chosen as the language of choice because performance is not a concern at this point, and features like dynamic typing and a REPL are invaluable for rapid development. As a project like this matures, performance and maintainability become more important, but when one is not sure of what the end product should even look like, it isn't worth worrying about reducing possibilities for bugs.

`initial_parser.py` parses by regex searching for clauses, comments and statement separators (";" or "\n\n"). It does not, however, look inside the strings between clauses. At this point, one course of action could be to take the output and attach it to some database client such as DBeaver to get the autocomplete features. This would arguably be closer to the original project proposal than what was done here.

Note that this was my first time working on a project of this magnitude by myself. As such, I was a bit apprehensive of using other projects in my implementation. Even a couple of changes may require a few days of analysis, and seemingly simple updates to features may require significant restructuring. At my level of experience, that's a level of uncertainty I wasn't willing to take on for a course project. Additionally, since my research area is in programming languages, I wanted to learn the concepts and theory behind different systems by coding them from scratch.

I eventually decided to use a recursive-descent parser + operator precedence parser combination, similar to how the GCC parser is set up. Such a system has a number of benefits, namely that it is very flexible in terms of what it can parse. More details in the next section.

To support such a parser, a tokenizer with some ability to "peek" ahead would help simplify development. The tokenizer's interface is fairly straightforward: `consume()` to return the next token and move the pointer in the text to the next token, and `peek(int)` to look ahead without consuming any tokens (see `tokenizer.py`). The tokens are broken into 4 general categories - more details in `my_token.py` . One key feature I wanted to have was "zero copy" - the tokens only hold indexes to the input text, so no strings needed to be copied. I considered this to be important because I needed to reference where the cursor was in relation to the tokens, and I wanted to try programming using more performant programming patterns, which would make it easier to transform this code into a faster programming language at some point.

## Parser and AST spec

The parser code is in `parser.py` and the Abstract Syntax Tree (AST) specification is in `my_ast.py` . To use the parser, run `parse_all()` to return a list of statements in the text.

A recursive-descent parser + operator precedence parser combination has a couple of benefits over a standard Context-Free Grammar (CFG) specification. Namely, because it doesn't follow a rigid specification, one can extend it with a number of special functionalities that are not easy to represent with a CFG. Consider comments for example. When transforming Unordered SQL to regular SQL, it would be better to keep the comments intact. This means that the parser has to handle the possibility of comments at any point in the text, which would obfuscate the CFG specification. With a recursive-descent parser, I can simply pull that complexity into the function `get_next_standard_token()` .

A more underlying problem with using a CFG specification is that this is essentially an IDE, where the user's input is often not valid syntax. As such, there needs to be a way to detect at what point the user's input stopped making sense, and do so reliably. With a recursive descent parser, a function returns when it doesn't know how to parse the next token, and the top level function (`parse_statement()`) can then wrap those values into a `UnknownSequence` object.

I'll take this time to try and argue an opinion I developed while thinking about what type of parser to implement: The difficulty of parsing a language is correlated with the difficulty for a human to understand, and a parser should parse in a similar manner as a human. Note that this is in the context of programming languages (human languages are a whole different ball game). Yes, LR(1) parsers can be used to parse any deterministic CFG language, but humans don't read code like an LR(1) parser. If anything, humans read code like an LL(k) parser. Hence why the tokenizer I'm using has lookahead and the parser is recursive-descent. The one place where it deviates from recursive-descent is when parsing expressions, which is somewhat acceptable because 1. it is used everywhere and people are familiar with it; 2. everything is an expression node, which makes it fairly easy to understand and parse. In this case, an operator precedence parser can be used, which is fairly compact (see `parse_expression()`) - just like how it's not too hard for a human to read an expression.

## Formatter and autocomplete

The formatter and autocomplete are more about showcasing that the parser works, and I didn't have much time to write it. As such, the implementation is somewhat sloppy. However, I tried to add sufficient documentation to the testing code to make it understandable to the reader what the code is doing. Look at `formatter.py` and `autocomplete.py` for more details. If you want to play around and see what the parser can do, editing the test cases in `formatter.py` is your best bet.

## Implementation issues / stuff to change

Using `(start_index, length)` instead of `(start_index, end_index)` to implement the "zero copy" for tokens was a mistake. I had originally thought that using `length` would be easier to work with than `end_index`, but I always ended up converting to `end_index` .

The parser throws away a lot of information about where the start and end of an AST node is. This isn't much of a problem for the formatter, since it is generating a new SQL statement anyways. However, for the autocomplete, it meant that the entire AST needed to be searched in order to find where the cursor was within the AST. There are also a number of scenarios where the AST should be more cognizant of the fact it's parsing something that's being actively edited. Consider `select in` , where the cursor is about to write the word `inside` . Unfortunately, `in` is a keyword, so it gets thrown out of the AST and the user loses autocomplete briefly (the syntax highlighting may also abruptly change, if I had that implemented).

I have to say, I misjudged how difficult it would be to write a SQL parser. Even my simple specification, which lacks prefix operators or function calls, took a significant amount of time to set up. A true SQL parser will also have to handle other statements like CREATE TABLE and DELETE , which may or may not cause problems when trying to implement in Unordered SQL. At the bottom of some of the Python files I've written a set of test examples, which also have comments highlighting some of the limitations of the implementation. To make things worse, SQL isn't one language - there are a ton of variants for each database engine vendor, some of which may do something that isn't compatible with Unordered SQL.

One idea I had when writing the parser is to use an "array representation" for expressions, which would likely be more efficient than the tree format that I'm using right now. See line 23 of `my_ast.py` for details.

One big part that isn't addressed right now is the ability to handle edits. As it currently stands, the entire text would be reparsed on every edit. A smarter parser would be able to selectively reparse parts of the AST. This can get a bit tricky though, and does require some thought.

It's worth noting that there is no type-checking being done here. This might actually be fine, since people use autocomplete to save keystrokes and catch spelling mistakes, rather than as a type-checker. That being said, if building out a full IDE was the goal, it would require stuff like type-checking, an actual text editor environment and a connection to a database. This is far too much complexity for a course project, but might be an interesting direction to pursue

## Closing thoughts

The project proposal set up parsing the Unordered SQL language as a relatively simple task. Indeed, if I wrote it like `initial_parser.py` or found a suitable parser, it would not be as complex as it ended up being. With the way I ended up doing it, it was a whole lot more work and changed the milestones entirely (it was more about learning how to write a parser than hacking a prototype together). I don't really regret it though, as I learned about a lot of the complexities of building a language from scratch that I otherwise wouldn't have considered if I had simply used a pre-built solution.

From an engineering perspective, it's a bit of a disappointment, since most of the functionality could be gotten by simply extending `initial_parser.py` or `tokenizer.py` a bit more. The only feature that the parser offers that actually requires parsing an AST is the ability to denote unknown sequences, which could probably be done by leveraging another library. However, I feel like this misses the "research and understanding" portion of the project. From a scientific perspective, I think I learned a lot about the intricacies of developing a programming language and spent time developing my own opinions on programming languages, which will be particularily useful when making decisions in the future.

For the next step, I want to try forking a database client that has autocomplete, and see if I can modify it to work for Unordered SQL. I think it'd be particularily useful to compare my implementation with the way a database client like DBeaver is implemented, especially now that I have a deeper understanding of what needs to be done in order to create such a product.
