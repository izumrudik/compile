from sys import stderr
import sys
from .primitives import Node, nodes, TT, Token, NEWLINE, Config, get_id, id_counter, safe, INTRINSICS, Type, find_fun_by_name



class GenerateAssembly:
	__slots__ = ('strings_to_push', 'intrinsics_to_add', 'data_stack', 'variables', 'memos', 'consts', 'config', 'ast', 'file')
	def __init__(self, ast:nodes.Tops, config:Config) -> None:
		self.strings_to_push   : list[Token]             = []
		self.intrinsics_to_add : set[str]                = set()
		self.data_stack        : list[Type]              = []
		self.variables         : list[nodes.TypedVariable] = []
		self.memos             : list[nodes.Memo]          = []
		self.consts            : list[nodes.Const]         = []
		self.config            : Config                  = config
		self.ast               : nodes.Tops                = ast
		self.generate_assembly()
	def visit_fun(self, node:nodes.Fun) -> None:
		assert self.variables == [], f"visit_fun called with {[str(var) for var in self.variables]} (vars should be on the stack)"
		self.file.write(f"""
fun_{node.identifier}:; {node.name.operand}
	pop QWORD [r15-8]; save ret pointer
	sub r15, 8; make space for ret pointer
""")
		for arg in reversed(node.arg_types):
			self.variables.append(arg)
			self.file.write(f"""
	sub r15, {8*int(arg.typ)} ; make space for arg '{arg.name}' at {arg.name.loc}""")
			for idx in range(int(arg.typ)-1, -1, -1):
				self.file.write(f"""
	pop QWORD [r15+{8*idx}]; save arg""")
			self.file.write('\n')
		self.file.write('\n')
		self.visit(node.code)

		for arg in node.arg_types:
			self.file.write(f"""
	add r15, {8*int(arg.typ)}; remove arg '{arg.name}' at {arg.name.loc}""")
		self.variables = []
		self.file.write("""
	add r15, 8; pop ret addr
	push QWORD [r15-8]; push back ret addr
	ret""")
	def visit_code(self, node:nodes.Code) -> None:
		var_before = self.variables.copy()
		for statemnet in node.statements:
			self.visit(statemnet)
		for var in self.variables[len(var_before):]:
			self.file.write(f"""
	add r15, {8*int(var.typ)}; remove var '{var.name}' at {var.name.loc}""")
		self.file.write('\n')
		self.variables = var_before
	def visit_function_call(self, node:nodes.FunctionCall) -> None:
		for arg in node.args:
			self.visit(arg)
		intrinsic = INTRINSICS.get(node.name.operand)
		if intrinsic is not None:
			self.intrinsics_to_add.add(node.name.operand)
			for _ in intrinsic[1]:
				self.data_stack.pop()
			self.data_stack.append(intrinsic[2])
			identifier = f"intrinsic_{intrinsic[3]}"
		else:
			top = find_fun_by_name(self.ast, node.name)
			for _ in top.arg_types:
				self.data_stack.pop()
			self.data_stack.append(top.output_type)
			identifier = f"fun_{top.identifier}"
		self.file.write(f"""
	call {identifier}; call {node.name.operand} at {node.name.loc}
""")
	def visit_token(self, token:Token) -> None:
		if token.typ == TT.DIGIT:
			self.file.write(f"""
    push {token.operand} ; push number {token.loc}
""")
			self.data_stack.append(Type.INT)
		elif token.typ == TT.STRING:
			self.file.write(f"""
	push str_len_{token.identifier} ; push len of string {token.loc}
	push str_{token.identifier} ; push string
""")
			self.strings_to_push.append(token)
			self.data_stack.append(Type.STR)
		else:
			assert False, f"Unreachable: {token.typ=}"
	def visit_bin_exp(self, node:nodes.BinaryExpression) -> None:
		self.visit(node.left)
		self.visit(node.right)
		operations = {
TT.PERCENT_SIGN:"""
	xor rdx, rdx
	div rbx
	push rdx
""",
TT.PLUS:"""
	add rax, rbx
	push rax
""",
TT.MINUS:"""
	sub rax, rbx
	push rax
""",
TT.ASTERISK:"""
	mul rbx
	push rax
""",
TT.DOUBLE_SLASH:"""
	xor rdx, rdx
	div rbx
	push rax
""",

TT.GREATER_SIGN:"""
	xor rdx, rdx
	mov rcx, 1
	cmp rax, rbx
	cmovg rdx, rcx
	push rdx
""",
TT.LESS_SIGN:"""
	xor rdx, rdx
	mov rcx, 1
	cmp rax, rbx
	cmovl rdx, rcx
	push rdx
""",
TT.DOUBLE_EQUALS_SIGN:"""
	xor rdx, rdx
	mov rcx, 1
	cmp rax, rbx
	cmove rdx, rcx
	push rdx
""",
TT.NOT_EQUALS_SIGN:"""
	xor rdx, rdx
	mov rcx, 1
	cmp rax, rbx
	cmovne rdx, rcx
	push rdx
""",
TT.GREATER_OR_EQUAL_SIGN:"""
	xor rdx, rdx
	mov rcx, 1
	cmp rax, rbx
	cmovge rdx, rcx
	push rdx
""",
TT.LESS_OR_EQUAL_SIGN:"""
	xor rdx, rdx
	mov rcx, 1
	cmp rax, rbx
	cmovle rdx, rcx
	push rdx
""",
'and':"""
	and rax, rbx
	push rax
""",
'or':"""
	or rax, rbx
	push rax
""",
'xor':"""
	xor rax, rbx
	push rax
""",
		}
		if node.operation.typ != TT.KEYWORD:
			operation = operations.get(node.operation.typ)
		else:
			operation = operations.get(node.operation.operand)
		assert operation is not None, f"op '{node.operation}' is not implemented yet"
		self.file.write(f"""
	pop rbx; operation '{node.operation}' at {node.operation.loc}
	pop rax{operation}""")
		self.data_stack.pop()#type_check, I count on you
		self.data_stack.pop()
		self.data_stack.append(node.typ)
	def visit_expr_state(self, node:nodes.ExprStatement) -> None:
		self.visit(node.value)
		self.file.write(f"""
	sub rsp, {8*int(self.data_stack.pop())} ; pop expr result
""")
	def visit_assignment(self, node:nodes.Assignment) -> None:
		self.visit(node.value) # get a value to store
		typ = self.data_stack.pop()
		self.variables.append(node.var)
		self.file.write(f"""
	sub r15, {8*int(typ)} ; make space for '{node.var.name}' at {node.var.name.loc}""")
		for idx in range(int(typ)-1, -1, -1):
			self.file.write(f"""
	pop QWORD [r15+{8*idx}] ; save value to the place""")
		self.file.write('\n')
	def get_variable_offset(self, name:Token) -> 'tuple[int, Type]':
		idx = len(self.variables)-1
		offset = 0
		typ = None
		while idx>=0:
			var = self.variables[idx]
			if var.name == name:
				typ = var.typ
				break
			offset+=int(var.typ)
			idx-=1
		else:
			print(f"ERROR: {name.loc}: did not find variable '{name}'", file=stderr)
			sys.exit(1)
		return offset, typ
	def visit_refer(self, node:nodes.ReferTo) -> None:
		def refer_to_memo(memo:nodes.Memo) -> None:
			self.file.write(f"""
	push memo_{memo.identifier}; push PTR to memo at {node.name.loc}
			""")
			self.data_stack.append(Type.PTR)
			return
		def refer_to_const(const:nodes.Const) -> None:
			self.file.write(f"""
	push {const.value}; push const value at {node.name.loc}
			""")
			self.data_stack.append(Type.INT)
			return

		def refer_to_variable() -> None:
			offset, typ = self.get_variable_offset(node.name)
			for i in range(int(typ)):
				self.file.write(f'''
	push QWORD [r15+{(offset+i)*8}] ; reference '{node.name}' at {node.name.loc}''')
			self.file.write('\n')
			self.data_stack.append(typ)

		for memo in self.memos:
			if node.name == memo.name:
				return refer_to_memo(memo)
		for const in self.consts:
			if node.name == const.name:
				return refer_to_const(const)
		return refer_to_variable()
	def visit_defining(self, node:nodes.Defining) -> None:
		self.variables.append(node.var)
		self.file.write(f"""
	sub r15, {8*int(node.var.typ)} ; defing '{node.var}' at {node.var.name.loc}
""")
	def visit_reassignment(self, node:nodes.ReAssignment) -> None:
		offset, typ = self.get_variable_offset(node.name)
		self.visit(node.value)
		for i in range(int(typ)-1, -1, -1):
			self.file.write(f'''
	pop QWORD [r15+{(offset+i)*8}]; reassign '{node.name}' at {node.name.loc}''')
		self.file.write('\n')
	def visit_if(self, node:nodes.If) -> None:
		self.visit(node.condition)
		self.file.write(f"""
	pop rax; get condition result of if at {node.loc}
	test rax, rax; test; if true jmp
	jnz if_{node.identifier}; else follow to the else block
""")
		if node.else_code is not None:
			self.visit(node.else_code)
		self.file.write(f"""
	jmp endif_{node.identifier} ; skip if block
if_{node.identifier}:""")
		self.visit(node.code)
		self.file.write(f"""
endif_{node.identifier}:""")
	def visit_intr_constant(self, node:nodes.IntrinsicConstant) -> None:
		constants = {
			'False':'push 0',
			'True' :'push 1',
		}
		implementation = constants.get(node.name.operand)
		assert implementation is not None, f"Constant {node.name} is not implemented yet"
		self.file.write(f"""
	{implementation}; push constant {node.name}
""")
		self.data_stack.append(node.typ)
	def visit_unary_exp(self, node:nodes.UnaryExpression) -> None:
		self.visit(node.right)
		operations = {
			TT.NOT:'xor rax, 1'
		}
		implementation = operations.get(node.operation.typ)
		assert implementation is not None, f"Unreachable, {node.operation=}"
		self.file.write(f"""
	pop rax
	{implementation}; perform unary operation '{node.operation}'
	push rax
""")
		self.data_stack.pop()#type_check hello
		self.data_stack.append(node.typ)
	def visit_memo(self, node:nodes.Memo) -> None:
		self.memos.append(node)
	def visit_const(self, node:nodes.Const) -> None:
		self.consts.append(node)
	def visit(self, node:'Node|Token') -> None:
		if   type(node) == nodes.Fun              : self.visit_fun          (node)
		elif type(node) == nodes.Memo             : self.visit_memo         (node)
		elif type(node) == nodes.Const            : self.visit_const         (node)
		elif type(node) == nodes.Code             : self.visit_code         (node)
		elif type(node) == nodes.FunctionCall     : self.visit_function_call(node)
		elif type(node) == nodes.BinaryExpression : self.visit_bin_exp      (node)
		elif type(node) == nodes.UnaryExpression  : self.visit_unary_exp    (node)
		elif type(node) == nodes.ExprStatement    : self.visit_expr_state   (node)
		elif type(node) == nodes.Assignment       : self.visit_assignment   (node)
		elif type(node) == nodes.ReferTo          : self.visit_refer        (node)
		elif type(node) == nodes.Defining         : self.visit_defining     (node)
		elif type(node) == nodes.ReAssignment     : self.visit_reassignment (node)
		elif type(node) == nodes.If               : self.visit_if           (node)
		elif type(node) == nodes.IntrinsicConstant: self.visit_intr_constant(node)
		elif type(node) == Token                : self.visit_token        (node)
		else:
			assert False, f'Unreachable, unknown {type(node)=} '
	def generate_assembly(self) -> None:
		with open(self.config.output_file + '.asm', 'wt', encoding='UTF-8') as file:
			self.file = file
			file.write(
f"""; Assembly generated by lang compiler github.com/izumrudik/compile
; ---------------------------
segment .text""")
			for top in self.ast.tops:
				self.visit(top)
			for intrinsic in self.intrinsics_to_add:
				file.write(f"""
intrinsic_{INTRINSICS[intrinsic][3]}: ; {intrinsic}
{INTRINSICS[intrinsic][0]}
""")
			for top in self.ast.tops:
				if isinstance(top, nodes.Fun):
					if top.name.operand == 'main':
						break
			else:
				print("ERROR: did not find entry point (function 'main')", file=stderr)
				sys.exit(2)
			file.write(f"""
global _start
_start:
	mov [args_ptr], rsp
	mov r15, rsp ; starting fun
	mov rsp, var_stack_end
	call fun_{top.identifier} ; call main fun
	mov rax, 60
	mov rdi, 0
	syscall
segment .bss
	args_ptr: resq 1
	var_stack: resb 65536
	var_stack_end:""")
			for memo in self.memos:
				file.write(f"""
	memo_{memo.identifier}: resb {memo.size}; memo {memo.name} at {memo.name.loc}""")
			file.write("""
segment .data
""")
			for  string in self.strings_to_push:
				if string.operand:
					to_write = ''
					in_quotes = False
					for char in string.operand:
						if safe(char):#ascii
							if in_quotes:
								to_write += char
							else:
								to_write += f'"{char}'
								in_quotes = True
						elif in_quotes:
							to_write += f'", {ord(char)}, '
							in_quotes = False
						else:
							to_write += f'{ord(char)}, '
					if in_quotes:
						to_write += '"'
					else:
						to_write = to_write[:-2]
					length = f'equ $-str_{string.identifier}'
				else:
					to_write = '0'
					length = 'equ 0'
				file.write(f"""
str_{string.identifier}: db {to_write} ; {string.loc}
str_len_{string.identifier}: {length}
""")
			self.file.write(f"""
; ---------------------------
; DEBUG:
; there was {len(self.ast.tops)} tops
; constant values:
{''.join(f';	{const.name} = {const.value}{NEWLINE}' for const in self.ast.tops if isinstance(const, nodes.Const))
}; state of id counter: {id_counter}
""")
