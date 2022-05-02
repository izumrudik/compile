# Jararaca
It's just a compiler for jararaca language that compiles .ja into native executable
for example:
```
fun main {
	puts("Hello world!\n")
}
```
## Usage
python jararaca.py --help
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
also, you can make any character by code with '\\x' and 2-digit hex code (like '\\x0A' -> '\n')

numbers can be made by concatenating digits.
integers in base 10 by default.
shorts can be made with suffix `s`.
char can be made with suffix `c` on number or 1 character string.
by prefixing `0x`, `0b` or `0o` number will be read as one in hex, binary or octal respectively.

a word starts with 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_'
and continues with 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_0123456789' .

if a word is in a list of keywords, it is a keyword
list of keywords:
1. fun
1. use
1. const
1. import
1. struct
1. var
1. mix
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
1. Null
1. Argv
1. Argc

symbols are '}{)(;+%:,.$=-!><][@'
symbol combinations are:
1. `//`
1. `==`
1. `!=`
1. `>=`
1. `<=`
1. `>>`
1. `<<`
1. `->`
1. `<-`

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
1. `fun <word>(name) [<typedvariable>]* [-> <type>]? <code>`
1. `var <word>(name) <type>`
1. `const <word>(name) <CTE>(value)`
1. `struct <word>(name) {[\n|;]*[<typedvariable>[\n|;]]*}`
1. `import <module_path>`
1. `from <module_path> import <word>[,<word>]*`
1. `mix <word>(name) {[\n|;]*[<word>[\n|;]]*[<word>]?}`
1. `use <word>(name)(<type>[,<type>]*[,]?)[-><type>]?`

CTE is compile-time-evaluation, so in it is only digits/constants and operands. Note, that operands are parsed without order: (((2+2)*2)//14)

string is just a string token

typed variable is `<word>(name):<type>`

module_path is `<word>[.<word>]*`

code is `{[\n|;]*[<statement>[\n|;]]*[<statement>]?}`

statement can be:
1. expression
1. assignment
1. definition
1. reassignment
1. save
1. if
1. while
1. return

- definition: `<typedvariable>`
- reassignment: `<word>(name) = <expression>`
- assignment: `<typedvariable> = <expression>`
- save: `<expression>(space) <- <expression>(value)`
- if: `if <expression> <code> [elif <expression> <code>]* [else <code>]?`
- while: `while <expression> <code>`
- return: `return <expression>`

expression is `<exp0>`
1. `<exp0>` is `[<exp1> [or|xor|and] ]*<exp1>`
2. `<exp1>` is `[<exp2> [<|>|==|!=|<=|>=] ]*<exp2>`
3. `<exp2>` is `[<exp3> [+|-] ]* <exp3>`
4. `<exp3>` is `[<exp4> [*] ]* <exp4>`
5. `<exp4>` is `[<exp5> [**|//|>>|<<|%] ]* <exp5>`
0. `<exp5>` is `[<exp6>|[!|@]<exp5>]`
6. `<exp6>` is `[<term>|<exp6>.<term>[([<expression>,]*[<expression>]?)]?|<exp6>\[<term>\] ]`

any term is:
1. `(<expression>)`
1. `<word>([<expression>,]*[<expression>]?)` - function call
1. `<word>` - name lookup (constant, variable, etc.)
1. `$<type>(<expression>)` - cast
1. `$(<expression>, <expression>[,]?)` - string cast
1. `<keyword>` - `False|True|Null` - constants
1. `<digit>` - digit
1. `<string>` - string
## Notes
execution starts from **main** function

std.ja defines many useful functions, constants, and structures

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
- [x] add array type
- [x] remove memo
- [x] add auto for assignment
- [x] add numbers in hex, binary, octal, 1_000_000
- [x] add mix top
- [x] make functions for structs
- [x] remove opaque pointers
- [x] remove intrinsics
- [x] come up with fun name for this language - jararaca
- [x] implement `import`, delete include
- [ ] make extension for vscode
## Type checker
---
checks everything.
note, that in any code block, there should be return statement.
There is scoping: variables only from inner scope will not be saved.

existing types are:
1. `void`                            - void (0 bits)
1. `int`                             - integer (64 bits)
1. `char`                            - byte or character (8 bits)
1. `short`                           - half of integer (32 bits)
1. `bool`                            - boolean (1 bit)
1. `str`                             - string
1. `<word>(name of imported module)` - module
1. `ptr(<type>)`                     - pointer to something
1. `<word>(name of the structure)`   - structure type
1. `\[[<CTE>(size)]?\]<type>`        - array type

also if array size is not present, then it is assumed to be 0
## Modules
modules_path starts with a name of the packet that will be searched for at `JARARACA_PATH/packets/<name>.link` if file is present, it will follow to the location present in the file and work from there.
for example `JARARACA_PATH/packets/std.link` contains `JARARACA_PATH/std`
after first name, goes a dot and then the name to follow into. `compiler.primitives.core` is translated to to `.../compiler/primitives/core`.
lastly, if a directory at this place is present, `.../__init__.ja` will be imported.
if not, `.ja` is added and loaded.
so `compiler.primitives.core` is translated to `.../compiler/primitives/core.ja`
