# jararaca
a compiler for jararaca language that compiles .ja into native executable
for example:
```
fun main(){
	put`Hello world!`
}
```
## usage
`python3.10 jararaca.py --help`
## syntax
### lexing
every program consists of tokens:
1. words
1. keywords
1. literals (int|char|short|str)
1. symbols (like `{`, `!`, `*`, etc.)
1. symbol combinations (like `->`, `!=`, `<=`, etc.)
1. new lines
1. template strings (head,middle,tail,no_middle) (like `` `Hello, {someone}!` ``)

any character (not in string) immediately after `\\` will be ignored.

comments can be made by putting `#`, anything after it till the end of the line will be ignored.

strings can be made either with ", or '.
in strings, with `\\` character you can make special characters (like \\n, \\\\, \\" ).
if special character is not recognized, it will just skip character `\\z` -> ``.
also, you can make any character by code with `\\x` and 2-digit hex code (like `\\x0A` -> `\n`)

numbers can be made by concatenating digits.
they are in base 10 by default.
shorts can be made with suffix `s`.
char can be made with suffix `c` on number or 1 character string.
by prefixing `0x`, `0b` or `0o` number will be read as one in hex, binary or octal respectively.

a word starts with `abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_`
and continues with `abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_0123456789` .

if a word is in the list of keywords, it becomes a keyword
list of keywords:

1. fun
1. use
1. from
1. const
1. import
1. struct
1. mix
1. if
1. else
1. elif
1. while
1. return
1. set
1. or
1. xor
1. and
1. True
1. False
1. Null
1. Argv
1. Argc
1. Void

symbols are `][}{();+%:,.$@*~<>=!-`
symbol combinations are:
1. `//`
1. `==`
1. `!=`
1. `>=`
1. `<=`
1. `>>`
1. `<<`
1. `->`

list of escape characters (char, ascii code, actual character if possible):
1. `a`,7
1. `b`,8
1. `t`,9
1. `n`,10
1. `v`,11
1. `f`,12
1. `r`,13
1. ` `,32
1. `"`,34,`"`
1. `'`,39,`'`
1. `\`,92,`\\`
### parsing
every program gets splitted into several tops.
tops:
1. `fun <word>[~[%<word>,]*[%<word>]?~]?(name)([<typedvariable>,]*[<typedvariable>]?)[-><type>]? <code>`
1. `const <word>(name) <CTE>(value)`
1. `struct <word>[~[%<word>,]*[%<word>]?~]?(name) {[\n|;]*[<typedvariable>[\n|;]]*}`
1. `import <module_path>`
1. `from <module_path> import <word>[,<word>]*`
1. `mix <word>(name) {[\n|;]*[<word>[\n|;]]*[<word>]?}`
1. `use <word>(name)([<type>,]*[<type>]?)[-><type>]?`

CTE is compile-time-evaluation, so it only uses integers, constants and operands. note, that operands are parsed without order: (((2+2)*2)//14)


typed variable is `<word>(name):<type>`

module_path is `<word>[.<word>]*`

code is `{[\n|;]*[<statement>[\n|;]+]*[<statement>]?}`

statement can be:
1. expression
1. declaration
1. save
1. if
1. while
1. return

- declaration: `[\[<expression>\]]?<typedvariable>`
- save: `<expression>(space) = <expression>(value)`
- assignment: `<typedvariable> = <expression>`
- set: `set <name> = <expression>`
- if: `if <expression> <code> [elif <expression> <code>]* [else <code>]?`
- while: `while <expression> <code>`
- return: `return <expression>`

expression is `<exp0>`
1. `<exp0>` is `[<exp1> [or|xor|and] ]*<exp1>`
1. `<exp1>` is `[<exp2> [<|>|==|!=|<=|>=] ]*<exp2>`
1. `<exp2>` is `[<exp3> [+|-] ]* <exp3>`
1. `<exp3>` is `[<exp4> [*|//] ]* <exp4>`
1. `<exp4>` is `[<exp5> [>>|<<|%] ]* <exp5>`
1. `<exp5>` is `[<exp6>|[!|@]<exp5>]`
1. `<exp6>` is `[<term>|<exp6>.<term>|<exp6>\[<expression>\]|<exp6>([<expression>,]*[<expression>]?]|<exp6><template_string> `

template_string is `[<template_head><expression>[<template_middle><expression>]*<template_tail>]|<template_no_middle>`

any term is:
1. `(<expression>)`
1. `<word>[~[<type>,]*[<type>]?~]?` - name lookup (function, variable, etc.)
1. `$<type>(<expression>)` - cast
1. `$(<expression>, <expression>[,]?)` - string cast
1. `<keyword>` - `False|True|Null|Argv|Argc|Void` - constants
1. `<int>|<char>|<short>|<str>` - literals
1. `<template_string>` - template string (uses default formatter)
## notes
execution starts from **main** function

std.ja defines many useful functions, constants, and structures

I am planing to add:
- [x] function parameters
- [x] type checker
- [x] if statement
- [x] True, False, !=, or, and, !
- [x] if else statement
- [x] elif support
- [x] memory definition (which is just a *pointer)
- [x] constants declaration with `const`
- [x] return for `fun`'s
- [x] while  statement
- [x] make `include`
- [x] struct top
- [x] an example console snake, to see features
- [x] ptr(int), ptr(str), etc.
- [x] structs as types
- [x] cross platform with llvm
- [x] the docs
- [x] arrays (static)
- [x] remove memo
- [x] auto for assignment
- [x] numbers in hex, binary, octal, 1_000_000
- [x] mix top
- [x] remove opaque pointers
- [x] `use`, remove intrinsics
- [x] fun name for this language - jararaca
- [x] `import`, delete include
- [x] dynamic memory allocation
- [x] functions for structs
- [x] dynamic-size memory allocation
- [x] remove var top
- [x] set statement (set x = very.long\[operand\]\(chain\))
- [x] renamed ptr(int) to *int
- [x] generic types for `Array\~T\~`
- [x] magic methods `__init__` and `__subscript__`
- [x] template strings `` `Hello {someone}` ``
- [ ] add +=,|> and other syntactic sugar
- [ ] remove unsaveable types with special nodes, like VariableSave and Save
- [ ] extension for vscode
## type checker
---
checks everything.
there is scoping: variables from inner scope are not accessible from outer scope

existing types are:
1. `void`                            - void, 1 value (usually optimized out)
1. `int`                             - integer (64 bits)
1. `char`                            - byte or character (8 bits)
1. `short`                           - half of integer (32 bits)
1. `bool`                            - boolean (1 bit)
1. `str`                             - string
1. `*<type>`                         - pointer to something (usually 64 bits)
1. `<word>(name of the structure)`   - structure type
1. `\[[<CTE>(size)]?\]<type>`        - array type
1. `([<type>,]*[<type>]?)[-><type>]?`   - function type
1. `%<word>`                         - generic type

also if array size is not present, then it is assumed to be 0
## modules
modules_path starts with a name of the packet that will be searched for at `JARARACA_PATH/packets/<name>.link` if file is present, it will follow to the location present in the file and work from there.
for example `JARARACA_PATH/packets/std.link` contains `JARARACA_PATH/std`
after first name, goes a dot and then the name to follow into. `compiler.primitives.core` is translated to to `.../compiler/primitives/core`.
lastly, if a directory at this place is present, `.../__init__.ja` will be imported.
if not, `.ja` is added and imported.
so `compiler.primitives.core` is translated to `.../compiler/primitives/core.ja`
and `compiler.primitives` is translated to `.../compiler/primitives/__init__.ja`

every module (except std.builtin) has a hidden `from std.builtin import exit,short,int,len,ptr,...`

`JARARACA_PATH/packets/std.link` set to contain `JARARACA_PATH/std` every run
