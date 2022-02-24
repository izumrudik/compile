# Compiler
It's just a compiler that compiles .lang into native executable
for example: 
```
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
1. digits
1. strings
1. symbols(like '{', ';', '*', etc.)
1. new lines

any character (not in string) immediately after '\\' will be ignored.
Comments can be made by putting '#', anything after it till the end of the line will be ignored.
Strings can be made either with ", or '.
In strings, with '\\' character you can make special characters (like \\n, \\\\, \\" ).
if special character is not recognized, it will just ignore '\\'.

list of keywords:
1. fun
1. memo
1. const
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
### Parsing
every program gets splitted into several tops.
tops: 
1. `fun <name> <args> <code>`
1. `memory <name> <CTE>(length)`
1. `const <name> <CTE>(value)`

CTE is compile-time-evaluation, so in it is only digits/constants and operands. Note, that operands are parsed without order: (((2+2)*2)//14)

code is a list of statements inclosed in '{}', separated by ';' or '\\n'

statement can be:
1. expression
1. assignment
1. definition
1. reassignment
1. if
1. while
1. return

- definition: `name: <type>`
- reassignment: `name = <expression>`
- assignment: `name: <type> = <expression>`
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
1. name lookup (memory, constant, variable)
1. digit
1. string
### Notes
execution starts from **main** function	

there is intrinsics, that are basically  built-in functions:
1. print: prints the string to stdout                                  (str      -> void)
1. exit: exits with provided code                                      (int      -> void)
1. len: get length of a string                                         (str      -> int )
1. ptr: get pointer to the first char in string                        (str      -> ptr )
1. str: combines length and pointer to the first char to make a string (int, ptr -> str )
1. ptr_to_int: converts pointer to the number                          (ptr      -> int )
1. int_to_ptr: converts number to pointer                              (int      -> ptr )
1. save_int:saves the int to the 8 bytes, provided by pointer          (ptr, int -> void)
1. load_int:loads 8 bytes, provided by pointer                         (ptr      -> int )
1. save_byte:saves the int to the byte, provided by pointer            (ptr, int -> void)
1. load_byte:loads byte, provided by pointer                           (ptr      -> int )

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
- [x] write the docs
- [x] add something to compile-time-evaluation, so it is not completely useless
- [x] make `include`
- [ ] make function that depend on types
- [ ] make extension for vscode
- [ ] implement `serious fun` (inline assembly) 
- [ ] move intrinsics to std, remove original intrinsics
- [ ] testing system
- [ ] write tests
- [ ] come up with a way to use `**` operator, (other than power)
- [ ] implement console snake, to see features
- [ ] implement `import`, delete include
- [ ] come up with fun name for this language
- [ ] struct top (offset/reset approach) 
- [ ] make operations for structs
- [ ] introduce custom operator functions for structs
## Assembly conventions
---
there is 2 stacks: data_stack and var_stack

data_stack is stored in rsp
var_stack is stored in r15

variables are pushing values to the var_stack.
arguments for functions are just variables.

operands are pushed on the data stack, and operations are performed from there.

parameters for functions are passed via data stack in reversed order.
function returns single value.

variable lookup is just copying values from var_stack to data stack.
variables are removed at the end of the corresponding code block.
## Type checker
---
checks everything.
note, that in any code block, there should be return statement.
There is scoping: variables only from inner scope will not be saved.

existing types are:
1. void
1. int
1. ptr
1. bool
1. str
