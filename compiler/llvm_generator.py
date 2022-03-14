from sys import stderr
import sys
from .primitives import Node, nodes, TT, Token, NEWLINE, Config, id_counter, safe, INTRINSICS_TYPES, Type, Ptr, INT, BOOL, STR, VOID, PTR, find_fun_by_name, StructType

class GenerateAssembly:
	__slots__ = ('text','ast','config')
	def __init__(self, ast:nodes.Tops, config:Config) -> None:
		self.config: Config     = config
		self.ast   : nodes.Tops = ast
		self.generate_assembly()
	def debug(self,string:str,elses:str = '') -> str:
		return string if self.config.debug else elses
	def visit_fun(self, node:nodes.Fun) -> None:
		assert False, 'visit_fun is not implemented yet'
	def visit_code(self, node:nodes.Code) -> None:
		assert False, 'visit_code is not implemented yet'
	def visit_function_call(self, node:nodes.FunctionCall) -> None:
		assert False, 'visit_function_call is not implemented yet'
	def visit_token(self, token:Token) -> None:
		assert False, 'visit_token is not implemented yet'
	def visit_bin_exp(self, node:nodes.BinaryExpression) -> None:
		assert False, 'visit_bin_exp is not implemented yet'
	def visit_expr_state(self, node:nodes.ExprStatement) -> None:
		assert False, 'visit_expr_state is not implemented yet'
	def visit_assignment(self, node:nodes.Assignment) -> None:
		assert False, 'visit_assignment is not implemented yet'
	def visit_refer(self, node:nodes.ReferTo) -> None:
		assert False, 'visit_refer is not implemented yet'
	def visit_defining(self, node:nodes.Defining) -> None:
		assert False, 'visit_defining is not implemented yet'
	def visit_reassignment(self, node:nodes.ReAssignment) -> None:
		assert False, 'visit_reassignment is not implemented yet'
	def visit_if(self, node:nodes.If) -> None:
		assert False, 'visit_if is not implemented yet'
	def visit_while(self, node:nodes.While) -> None:
		assert False, 'visit_while is not implemented yet'
	def visit_intr_constant(self, node:nodes.IntrinsicConstant) -> None:
		assert False, 'visit_intr_constant is not implemented yet'
	def visit_unary_exp(self, node:nodes.UnaryExpression) -> None:
		assert False, 'visit_unary_exp is not implemented yet'
	def visit_var(self, node:nodes.Var) -> None:
		assert False, 'visit_var is not implemented yet'
	def visit_memo(self, node:nodes.Memo) -> None:
		assert False, 'visit_memo is not implemented yet'
	def visit_const(self, node:nodes.Const) -> None:
		assert False, 'visit_const is not implemented yet'
	def visit_struct(self, node:nodes.Struct) -> None:
		assert False, 'visit_struct is not implemented yet'
	def visit_return(self, node:nodes.Return) -> None:
		assert False, 'visit_return is not implemented yet'
	def visit_dot(self, node:nodes.Dot) -> None:
		assert False, 'visit_dot is not implemented yet'
	def visit_cast(self, node:nodes.Cast) -> None:
		assert False, 'visit_cast is not implemented yet'
	def visit(self, node:'Node|Token') -> None:
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
		assert False, 'generate_assembly is not implemented yet'