from .type import Type
from .core import get_id
__all__ = [
	'INTRINSICS'
]


__intrinsics:'list[tuple[list[Type], Type, str, str]]' = [
	([Type.STR, ], Type.VOID, 'print',
"""
	pop rbx; get ret_addr
	
	pop rsi; put ptr to the correct place
	pop rdx; put len to the correct place
	mov rdi, 1; fd
	mov rax, 1; syscall num
	syscall; print syscall

	push rbx; return ret_addr
	ret
"""),
	([Type.INT, ], Type.VOID, 'exit',
"""
	pop rbx; get ret addr
	pop rdi; get return_code
	mov rax, 60; syscall number
	syscall; exit syscall
	push rbx; even though it should already exit, return
	ret 
"""),
	([Type.STR, ], Type.INT, 'len',
"""
	pop rax; get ret addr
	pop rbx; remove str pointer, leaving length
	push rax; push ret addr back
	ret
"""),
	([Type.STR, ], Type.PTR, 'ptr',
"""
	pop rcx

	pop rax; get ptr
	pop rbx; dump length
	push rax; push ptr

	push rcx
	ret
"""),
	([Type.INT, Type.PTR], Type.STR, 'str',
"""
	ret
"""),
	([Type.PTR, ], Type.INT, 'ptr_to_int',
"""
	ret
"""),
	([Type.INT, ], Type.PTR, 'int_to_ptr',
"""
	ret
"""),
	([Type.PTR, Type.INT], Type.VOID, 'save_int',
"""
	ret
"""),
	([Type.PTR, Type.INT], Type.VOID, 'save_byte',
"""
	pop rcx; get ret addr

    pop rbx; get value
    pop rax; get pointer
    mov [rax], bl

	push rcx; ret addr
	ret
"""),
	([Type.PTR, ], Type.INT, 'load_byte',
"""
	pop rcx; get ret addr

	pop rax; get pointer
	xor rbx, rbx; blank space for value
	mov bl, [rax]; read 1 byte and put it into space
	push rbx; push whole number

	push rcx; ret addr
	ret
"""),
]


INTRINSICS:'dict[str, tuple[str, list[Type], Type, int]]' = {
	name:(
		code,input_types,return_type,get_id()
	) for (input_types,return_type,name,code) in __intrinsics
}
