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

list of keywords:
1. fun
### parsing
every programm gets splited into several tops.
for now the only top is function declaration.
`fun <name> <code>`
code is a list of statements inclosed in '{}', separated by ';'
statement can be:
1. expression
1. assignment(WIP)

expression is 
"*/+-" in mathematical order,
'//' for dividing without remainder,
 '%' for remainder.

any term is:
1. expression surrounded in parenthesis
1. function call
1. variable lookup(WIP)
1. digit
1. string
### notes
execution starts from **main** function	

there is a built-in intrinsics, that are basicly functions:
1. print:prints the string

I am planing to add:
[ ] assigning variables
[ ] variables lookup
[ ] binary_expression assebly generator
[ ] lookups validity check
[ ] function parameters
[ ] type checker
[ ] if statement
[ ] constants declaration with !
[ ] more intrinsics
[ ] come up with fun name for this language
[ ] testing system
[ ] write tests
[ ] make memory defenition (which is just a *pointer)
[ ] make CTR !include
[ ] while  statement
[ ] struct top (offset/reset aproach) 
[ ] make operations for structs
[ ] introduce custom operator functions for structs
## assembly conventions
---
everything is pushed on the data stack, and operations are performed from there

parameters for functions are passed via datastack in reversed order

functions are called via ret_stack

variables(WIP) are pushing values to the ret_stack

variable(WIP) lookup is just copying values from ret_stack to datastack

variables(WIP) are removed at the end of the corresponding functions
## type checker
---
... is not implemented yet