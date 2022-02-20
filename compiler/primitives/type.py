from enum import Enum, auto
import sys
from sys import stderr

from . import nodes 
from .token import Token
from .core import get_id


class Type(Enum):
	INT  = auto()
	BOOL = auto()
	STR  = auto()
	VOID = auto()
	PTR  = auto()
	def __int__(self) -> int:
		table:dict[Type, int] = {
			Type.VOID: 0,
			Type.INT : 1,
			Type.BOOL: 1,
			Type.PTR : 1,
			Type.STR : 2,
		}
		assert len(table)==len(Type)
		return table[self]
	def __str__(self) -> str:
		return self.name.lower()

INTRINSICS:'dict[str, tuple[str, list[Type], Type, int]]' = {
	'print':(
"""
	pop rbx; get ret_addr
	
	pop rsi; put ptr to the correct place
	pop rdx; put len to the correct place
	mov rdi, 1; fd
	mov rax, 1; syscall num
	syscall; print syscall

	push rbx; return ret_addr
	ret
""", [Type.STR, ], Type.VOID, get_id()),
	'exit':(
"""
	pop rbx; get ret addr
	pop rdi; get return_code
	mov rax, 60; syscall number
	syscall; exit syscall
	push rbx; even though it should already exit, return
	ret
""", [Type.INT, ], Type.VOID, get_id()),

	'len':(
"""
	pop rax; get ret addr
	pop rbx; remove str pointer, leaving length
	push rax; push ret addr back
	ret
""", [Type.STR, ], Type.INT, get_id()),

	'ptr':(
"""
	pop rcx

	pop rax; get ptr
	pop rbx; dump length
	push rax; push ptr

	push rcx
	ret
""", [Type.STR, ], Type.PTR, get_id()),
	'str':(
"""
	ret
""", [Type.INT, Type.PTR], Type.STR, get_id()),
	'ptr_to_int':(
"""
	ret
""", [Type.PTR, ], Type.INT, get_id()),
	'int_to_ptr':(
"""
	ret
""", [Type.INT, ], Type.PTR, get_id()),
	'save_int':(
"""
	pop rcx; get ret addr

	pop rbx; get value
	pop rax; get pointer
	mov [rax], rbx; save value to the *ptr

	push rcx; ret addr
	ret
""", [Type.PTR, Type.INT], Type.VOID, get_id()),
	'load_int':(
"""
	pop rbx; get ret addr

	pop rax; get pointer
	push QWORD [rax]

	push rbx; ret addr
	ret
""", [Type.PTR, ], Type.INT, get_id()),
	'save_byte':(
"""
	pop rcx; get ret addr

    pop rbx; get value
    pop rax; get pointer
    mov [rax], bl

	push rcx; ret addr
	ret
""", [Type.PTR, Type.INT], Type.VOID, get_id()),
	'load_byte':(
"""
	pop rcx; get ret addr

	pop rax; get pointer
	xor rbx, rbx; blank space for value
	mov bl, [rax]; read 1 byte and put it into space
	push rbx; push whole number

	push rcx; ret addr
	ret
""", [Type.PTR, ], Type.INT, get_id()),

}
def find_fun_by_name(ast:'nodes.NodeTops', name:Token) -> 'nodes.NodeFun':
	for top in ast.tops:
		if isinstance(top, nodes.Fun):
			if top.name == name:
				return top

	print(f"ERROR: {name.loc}: did not find function '{name}'", file=stderr)
	sys.exit(35)
