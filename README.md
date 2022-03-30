# Compiler
It's just a compiler that compiles .lang into native executable
for example:
```
include "std.lang"
fun main {
	print("Hello world!\n")
}
```
## Usage
python lang.py --help
## Syntax
### Lexing
every program consists of tokens:
1. words
1. keywords
1. numbers
1. strings
1. symbols (like '{', '!', '*', etc.)
1. symbol combinations (like '->', '!=', '<=', etc.)
1. new lines

any character (not in string) immediately after '\\' will be ignored.

Comments can be made by putting '#', anything after it till the end of the line will be ignored.

Strings can be made either with ", or '.
In strings, with '\\' character you can make special characters (like \\n, \\\\, \\" ).
if special character is not recognized, it will just skip character '\\z' -> ''.

numbers can be made by concatenating digits (0-9).

a word starts with 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_'
and continues with 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_0123456789' .

if a word is in a list of keywords, it is a keyword
list of keywords:
1. fun
1. memo
1. const
1. include
1. struct
1. var
1. if
1. else
1. elif
1. while
1. return
1. or
1. xor
1. and
1. True
1. False

symbols are '}{)(;+%:,.$=-!><]['
symbol combinations are:
1. //
1. ==
1. !=
1. >=
1. <=
1. >>
1. <<
1. ->

list of escape characters (char, ascii number generated, actual character if possible):
1. `a`,7
1. `b`,8
1. `t`,9
1. `n`,10
1. `v`,11
1. `f`,12
1. `r`,13
1. ` `,32
1. `"`,34,"
1. `'`,39,'
1. `\`,92,\\
### Parsing
every program gets splitted into several tops.
tops:
1. `fun <string>(name) [<typedvariable>]* [-> <type>]? <code>`
1. `memo <string>(name) <CTE>(length)`
1. `var <string>(name) <type>`
1. `const <string>(name) <CTE>(value)`
1. `include <string>(filepath)`
1. `struct <string>(name) {[<typedvariable>]*}`

CTE is compile-time-evaluation, so in it is only digits/constants and operands. Note, that operands are parsed without order: (((2+2)*2)//14)

string is just a string token

typed variable is `<string>(name):<type>`

code is a list of statements inclosed in '{}', separated by ';' or '\\n'

statement can be:
1. expression
1. assignment
1. definition
1. reassignment
1. if
1. while
1. return

- definition: `<typedvariable>`
- reassignment: `<string>(name) = <expression>`
- assignment: `<typedvariable> = <expression>`
- if: `if <expression> <code> [elif <expression> <code>]* [else <code>]?`
- while: `while <expression> <code>`
- return: `return <expression>`

expression is
1. "*+-" in mathematical order,
1. '//' for dividing without remainder,
1. '%' for remainder.
1. '< == > <= >=' for conditions.

any term is:
1. expression surrounded in parenthesis
1. function call
1. name lookup (memory, constant, variable, etc.)
1. digit
1. string
### Notes
execution starts from **main** function

there is intrinsics, that are basically  built-in functions:

1. len: get length of a string                                         (str            -> int )
1. ptr: get pointer to the first char in string                        (str            -> ptr )
1. str: combines length and pointer to the first char to make a string (int, ptr       -> str )
1. save_int: saves the int to the 8 bytes, provided by pointer         (ptr(int), int  -> void)
1. load_int: loads 8 bytes, provided by pointer                        (ptr(int)       -> int )
1. save_byte: saves the int to the byte, provided by pointer           (ptr, int       -> void)
1. load_byte: loads byte, provided by pointer                          (ptr            -> int )
1. exit: exits with provided code                                      (int            -> void)
1. write: write string to specified file descriptor                    (int,str        -> int )
1. read: read from the file descriptor to buffer ptr and it's length   (int,ptr,int    -> int )
1. nanosleep: sleep ptr(Timespec) time, remaining put to 2nd ptr       (ptr,ptr        -> int )
1. fcntl: manipulate file descriptor with cmd and arg                  (int,int,int    -> int )
1. tcsetattr: set file descriptor's termios to ptr in mode             (int,int,ptr    -> int )
1. tcgetattr: get file descriptor's termios and save it to ptr         (int,ptr        -> int )

std.lang defines many useful functions, constants, and structures

I am planing to add:
- [x] assigning variables
- [x] variables lookup
- [x] binary_expression assembly generator
- [x] lookups validity check
- [x] function parameters
- [x] type checker
- [x] if statement
- [x] True, False, !=, or, and, !
- [x] if else statement
- [x] elif support
- [x] optimize assembly instructions
- [x] make memory definition (which is just a *pointer)
- [x] constants declaration with `const`
- [x] return for `fun`'s
- [x] while  statement
- [x] add something to compile-time-evaluation, so it is not completely useless
- [x] make `include`
- [x] move intrinsics to std, simplify original intrinsics
- [x] struct top
- [x] implement console snake, to see features
- [x] implement ptr[int], ptr[str], etc.
- [x] implement structs as types
- [x] achieve cross platform with llvm
- [x] write the docs
- [ ] add array type
- [ ] remove memo
- [ ] add auto for assignment
- [ ] add combine top
- [ ] come up with a way to use `**` operator, (other than power)
- [ ] implement `import`, delete include
- [ ] come up with fun name for this language
- [ ] make extension for vscode
- [ ] make functions as address
- [ ] make functions for structs
- [ ] introduce custom operator functions for structs
## Type checker
---
checks everything.
note, that in any code block, there should be return statement.
There is scoping: variables only from inner scope will not be saved.

existing types are:
1. `void`
1. `int`
1. `bool`
1. `str`
1. `ptr`
1. `ptr(<type>)`
1. `<word>(name of the structure)`