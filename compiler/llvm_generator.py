from sys import implementation, stderr
import sys
from .primitives import Node, nodes, TT, Token, NEWLINE, Config, id_counter, safe, INTRINSICS_TYPES, Type, Ptr, INT, BOOL, STR, VOID, PTR, find_fun_by_name, StructType

__INTRINSICS_IMPLEMENTATION:'dict[str,str]' = {
	'exit':"declare void @exit(i32)\n"
}

INTRINSICS_IMPLEMENTATION:'dict[int,tuple[str,str]]' = {
	INTRINSICS_TYPES[name][2]:(name,__INTRINSICS_IMPLEMENTATION[name]) for name in __INTRINSICS_IMPLEMENTATION
}
class GenerateAssembly:
	__slots__ = ('text','ast','config')
	def __init__(self, ast:nodes.Tops, config:Config) -> None:
		self.config: Config     = config
		self.ast   : nodes.Tops = ast
		self.text  : str        = ''
		self.generate_assembly()
	def debug(self,string:str,elses:str = '') -> str:
		return string if self.config.debug else elses
	def visit_fun(self, node:nodes.Fun) -> str:
		#assert self.variables == [], f"visit_fun called with {[str(var) for var in self.variables]} (vars should be on the stack) at {node}"
		#assert self.data_stack ==[], f"visit_fun called with {[str(typ) for typ in self.data_stack]} (nothing should be on the data stack) at {node}"
	
		ot = node.output_type
		self.text += f"""
define {ot.llvm} @fun_{node.identifier}\
({', '.join(f'{arg.typ.llvm} %{arg.identifier}' for arg in node.arg_types)}) {{
{f'	%retvar = alloca {ot.llvm}, align 4{NEWLINE}' if ot != VOID else ''}"""


		self.visit(node.code)


		self.text += f"""{self.debug(NEWLINE)}\
return:
{f'	%retval = load {ot.llvm}, {ot.llvm}* %retvar, align 4{NEWLINE}' if ot != VOID else ''}\
	ret {ot.llvm} {f'%retval' if ot != VOID else ''}
}}
"""
		#self.variables = []
		return '!!!NOTHING!!!'
	def visit_code(self, node:nodes.Code) -> str:
		assert False, 'visit_code is not implemented yet'
	def visit_function_call(self, node:nodes.FunctionCall) -> str:
		assert False, 'visit_function_call is not implemented yet'
	def visit_token(self, token:Token) -> str:
		assert False, 'visit_token is not implemented yet'
	def visit_bin_exp(self, node:nodes.BinaryExpression) -> str:
		assert False, 'visit_bin_exp is not implemented yet'
	def visit_expr_state(self, node:nodes.ExprStatement) -> str:
		assert False, 'visit_expr_state is not implemented yet'
	def visit_assignment(self, node:nodes.Assignment) -> str:
		assert False, 'visit_assignment is not implemented yet'
	def visit_refer(self, node:nodes.ReferTo) -> str:
		assert False, 'visit_refer is not implemented yet'
	def visit_defining(self, node:nodes.Defining) -> str:
		assert False, 'visit_defining is not implemented yet'
	def visit_reassignment(self, node:nodes.ReAssignment) -> str:
		assert False, 'visit_reassignment is not implemented yet'
	def visit_if(self, node:nodes.If) -> str:
		assert False, 'visit_if is not implemented yet'
	def visit_while(self, node:nodes.While) -> str:
		assert False, 'visit_while is not implemented yet'
	def visit_intr_constant(self, node:nodes.IntrinsicConstant) -> str:
		assert False, 'visit_intr_constant is not implemented yet'
	def visit_unary_exp(self, node:nodes.UnaryExpression) -> str:
		assert False, 'visit_unary_exp is not implemented yet'
	def visit_var(self, node:nodes.Var) -> str:
		assert False, 'visit_var is not implemented yet'
	def visit_memo(self, node:nodes.Memo) -> str:
		assert False, 'visit_memo is not implemented yet'
	def visit_const(self, node:nodes.Const) -> str:
		assert False, 'visit_const is not implemented yet'
	def visit_struct(self, node:nodes.Struct) -> str:
		assert False, 'visit_struct is not implemented yet'
	def visit_return(self, node:nodes.Return) -> str:
		assert False, 'visit_return is not implemented yet'
	def visit_dot(self, node:nodes.Dot) -> str:
		assert False, 'visit_dot is not implemented yet'
	def visit_cast(self, node:nodes.Cast) -> str:
		assert False, 'visit_cast is not implemented yet'
	def visit(self, node:'Node|Token') -> str:
		if   type(node) == nodes.Fun              : return self.visit_fun          (node)
		elif type(node) == nodes.Var              : return self.visit_var          (node)
		elif type(node) == nodes.Memo             : return self.visit_memo         (node)
		elif type(node) == nodes.Const            : return self.visit_const        (node)
		elif type(node) == nodes.Struct           : return self.visit_struct       (node)
		elif type(node) == nodes.Code             : return self.visit_code         (node)
		elif type(node) == nodes.FunctionCall     : return self.visit_function_call(node)
		elif type(node) == nodes.BinaryExpression : return self.visit_bin_exp      (node)
		elif type(node) == nodes.UnaryExpression  : return self.visit_unary_exp    (node)
		elif type(node) == nodes.ExprStatement    : return self.visit_expr_state   (node)
		elif type(node) == nodes.Assignment       : return self.visit_assignment   (node)
		elif type(node) == nodes.ReferTo          : return self.visit_refer        (node)
		elif type(node) == nodes.Defining         : return self.visit_defining     (node)
		elif type(node) == nodes.ReAssignment     : return self.visit_reassignment (node)
		elif type(node) == nodes.If               : return self.visit_if           (node)
		elif type(node) == nodes.While            : return self.visit_while        (node)
		elif type(node) == nodes.Return           : return self.visit_return       (node)
		elif type(node) == nodes.IntrinsicConstant: return self.visit_intr_constant(node)
		elif type(node) == nodes.Dot              : return self.visit_dot          (node)
		elif type(node) == nodes.Cast             : return self.visit_cast         (node)
		elif type(node) == Token                  : return self.visit_token        (node)
		else:
			assert False, f'Unreachable, unknown {type(node)=} '
	def generate_assembly(self) -> None:
		d = self.debug
		self.text+="""\
; Assembly generated by lang compiler github.com/izumrudik/compile
; ---------------------------
"""
		for top in self.ast.tops:
			self.visit(top)
		
		for (name,implementation) in INTRINSICS_IMPLEMENTATION.values():
			self.text += implementation
		for top in self.ast.tops:
			if isinstance(top, nodes.Fun):
				if top.name.operand == 'main':break
		else:assert False, "Type checker is not responding"
		main_top = top
		self.text += f"""
define i32 @main(){{{d('; entry point')}
	call void @fun_{main_top.identifier}(){d(f'; call user-generated main function at {main_top.name.loc}')}
	ret i32 0{d('; exit with 0 code')}
}}
"""
		self.text+=f"""
; ---------------------------
; DEBUG:
; there was {len(self.ast.tops)} tops
; constant values:
{''.join(f';	{const.name} = {const.value}{NEWLINE}' for const in self.ast.tops if isinstance(const, nodes.Const))
}; state of id counter: {id_counter}
"""
		with open(self.config.output_file + '.ll', 'wt', encoding='UTF-8') as file:
			file.write(self.text)