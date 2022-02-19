# compiler
---
It's just my first compiler I will create to learn .asm.
Do not expect anything, anything could change
## usage
---
python lang.py --help
## syntax
---
### lexing
every program consists of tokens:
1. words
1. keywords
1. digits
1. strings
1. symbols(like '{', ';', '*', etc.)
1. new lines

any character (not in string) immediately after '\' will be ignored.
comments can be made by putting '#', anything after it till the end of the line will be ignored.
strings can be made either with ", or '.
In strings, with '\' character you can make special characters (like \n, \\, \" ).
if special character is not recognized, it will just ignore '\'.
'$' char is now used for something, that is not implemented, so do not use it.

list of keywords:
1. fun
1. if
### parsing
every program gets splitted into several tops.
for now the only top is function declaration: 
`fun <name> <args> <code>`

code is a list of statements inclosed in '{}', separated by ';' or '\n'

statement can be:
1. expression
1. assignment
1. definition
1. reassignment
1. if 

- definition: `name: <type>`
- reassignment: `name = <expression>`
- assignment: `name: <type> = <expr>`
- if: `if <expression> <code>`

expression is 
1. "*+-" in mathematical order,
1. '//' for dividing without remainder,
1. '%' for remainder.
1. '< == > <= >=' for conditions.

any term is:
1. expression surrounded in parenthesis
1. function call
1. variable lookup
1. digit
1. string
### notes
execution starts from **main** function	

there is intrinsics, that are basically  built-in functions:
1. print: prints the string to stdout                                  (str     -> void)
1. exit: exits with provided code                                      (int     -> void)
1. len: get length of a string                                         (str     -> int )
1. ptr: get pointer to the first char in string                        (str     -> ptr )
1. str: combines length and pointer to the first char to make a string (int,ptr -> str )
1. ptr_to_int: converts pointer to the number                          (ptr     -> int )
1. int_to_ptr: converts number to pointer                              (int     -> ptr )
1. save_int:saves the int to the 8 bytes, provided by pointer          (ptr,int -> void)
1. load_int:loads 8 bytes, provided by pointer                         (ptr     -> int )
1. save_byte:saves the int to the byte, provided by pointer            (ptr,int -> void)
1. load_byte:loads byte, provided by pointer                           (ptr     -> int )


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
- [ ] constants declaration with `$const`
- [ ] return for `fun`'s
- [ ] while  statement
- [ ] write the docs
- [ ] add something to compile-time-evaluation, so it is not completely useless
- [ ] union for types with `|`
- [ ] make CTR `$include`
- [ ] implement `serious fun` (inline assembly) 
- [ ] move intrinsics to std, remove original intrinsics
- [ ] come up with a way to use `**` operator, (other than power)
- [ ] implement console snake, to see features
- [ ] come up with fun name for this language
- [ ] testing system
- [ ] write tests
- [ ] struct top (offset/reset approach) 
- [ ] make operations for structs
- [ ] introduce custom operator functions for structs
## assembly conventions
---
everything is pushed on the data stack, and operations are performed from there

parameters for functions are passed via data stack in reversed order.
function returns single value

functions are called via ret_stack, which is stored in r15

variables are pushing values to the ret_stack

variable lookup is just copying values from ret_stack to data stack

variables are removed at the end of the corresponding scope
## type checker
---
exists and checks operators and functions.

existing types are:
1. int
1. ptr
1. bool
1. str
