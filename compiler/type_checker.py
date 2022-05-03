import sys
from sys import stderr
from typing import Callable

from .primitives import nodes, Node, Token, TT, Config, Type, types

class TypeCheck:
	__slots__ = ('config', 'module', 'modules', 'variables', 'expected_return_type')
	def __init__(self, module:nodes.Module, config:Config) -> None:
		self.module = module
		self.config = config
		self.variables:dict[str, Type] = {}
		self.modules:dict[int, TypeCheck] = {}
		self.expected_return_type:Type = types.VOID
		for top in module.tops:
			if isinstance(top,nodes.Import):
				self.variables[top.name] = types.Module(top.module)
				self.modules[top.module.uid] = TypeCheck(top.module, self.config)
			elif isinstance(top,nodes.FromImport):
				tc = TypeCheck(top.module, self.config)
				self.modules[top.module.uid] = tc
				for name in top.imported_names:
					typ = tc.variables.get(name.operand)
					if typ is not None:
						self.variables[name.operand] = tc.variables[name.operand]
						continue
			elif isinstance(top,nodes.Var):
				self.variables[top.name.operand] = types.Ptr(top.typ)
			elif isinstance(top,nodes.Const):
				self.variables[top.name.operand] = types.INT
			elif isinstance(top, nodes.Mix):
				self.variables[top.name.operand] = types.Mix([self.check(fun_ref) for fun_ref in top.funs],top.name.operand)
			elif isinstance(top,nodes.Use):
				self.variables[top.name.operand] = types.Fun(top.arg_types,top.return_type)
			elif isinstance(top,nodes.Fun):
				self.variables[top.name.operand] = types.Fun([arg.typ for arg in top.arg_types], top.return_type)
				if top.name.operand == 'main':
					if top.return_type != types.VOID:
						print(f"ERROR: {top.name.loc}: entry point (function 'main') has to return nothing, found '{top.return_type}'", file=stderr)
						sys.exit(43)
					if len(top.arg_types) != 0:
						print(f"ERROR: {top.name.loc}: entry point (function 'main') has to take no arguments", file=stderr)
						sys.exit(44)

		for top in module.tops:
			self.check(top)
	def check_import(self, node:nodes.Import) -> Type:
		return types.VOID
	def check_from_import(self, node:nodes.FromImport) -> Type:
		return types.VOID
	def check_fun(self, node:nodes.Fun) -> Type:
		vars_before = self.variables.copy()
		self.variables.update({arg.name.operand:arg.typ for arg in node.arg_types})
		self.expected_return_type = node.return_type
		ret_typ = self.check(node.code)
		if node.return_type != ret_typ:
			print(f"ERROR: {node.name.loc}: specified return type ({node.return_type}) does not match actual return type ({ret_typ})", file=stderr)
			sys.exit(45)
		self.variables = vars_before
		self.expected_return_type = types.VOID
		return types.VOID
	def check_code(self, node:nodes.Code) -> Type:
		vars_before = self.variables.copy()
		ret = None
		for statement in node.statements:
			if isinstance(statement,nodes.Return):
				if ret is None:
					ret = self.check(statement)
			self.check(statement)
		self.variables = vars_before #this is scoping
		if ret is None:
			return types.VOID
		return self.expected_return_type
	def check_call(self, node:nodes.Call) -> Type:
		actual_types = [self.check(arg) for arg in node.args]
		def get_fun_out_of_called(called:Type) -> types.Fun:
			if isinstance(called, types.Fun):
				return called
			if isinstance(called, types.Mix):
				for ref in called.funs:
					fun = get_fun_out_of_called(ref)
					if len(actual_types) != len(fun.arg_types):
						continue#continue searching
					for actual_arg,arg in zip(actual_types,fun.arg_types,strict=True):
						if actual_arg != arg:
							break#break to continue
					else:
						return fun#found fun
					continue
				print(f"ERROR: {node.loc} did not find function to match {tuple(actual_types)!s} in mix '{called}'", file=stderr)
				sys.exit(46)
			print(f"ERROR: {node.loc}: '{called}' object is not callable", file=stderr)
			sys.exit(47)

		fun = get_fun_out_of_called(self.check(node.func))
		if len(fun.arg_types) != len(node.args):
			print(f"ERROR: {node.loc}: function '{fun}' accepts {len(fun.arg_types)} arguments, provided {len(node.args)}", file=stderr)
			sys.exit(48)
		for idx, arg in enumerate(node.args):
			typ = self.check(arg)
			needed = actual_types[idx]
			if typ != needed:
				print(f"ERROR: {node.loc}: '{fun}' function's argument {idx} takes '{needed}', got '{typ}'", file=stderr)
				sys.exit(49)
		return fun.return_type
	def check_bin_exp(self, node:nodes.BinaryExpression) -> Type:
		left = self.check(node.left)
		right = self.check(node.right)
		return node.typ(left,right)
	def check_expr_state(self, node:nodes.ExprStatement) -> Type:
		self.check(node.value)
		return types.VOID
	def check_token(self, token:Token) -> Type:
		if   token == TT.STRING    : return types.STR
		elif token == TT.INTEGER   : return types.INT
		elif token == TT.CHARACTER : return types.CHAR
		elif token == TT.SHORT     : return types.SHORT
		else:
			assert False, f"unreachable {token.typ=} {token=} {token.loc = !s}"
	def check_assignment(self, node:nodes.Assignment) -> Type:
		actual_type = self.check(node.value)
		if node.var.typ != actual_type:
			print(f"ERROR: {node.var.name.loc}: specified type '{node.var.typ}' does not match actual type '{actual_type}' in variable assignment", file=stderr)
			sys.exit(50)
		self.variables[node.var.name.operand] = node.var.typ
		return types.VOID
	def check_refer(self, node:nodes.ReferTo) -> Type:
		typ = self.variables.get(node.name.operand)
		if typ is None:
			print(f"ERROR: {node.name.loc}: did not find variable '{node.name}'", file=stderr)
			sys.exit(51)
		return typ
	def check_defining(self, node:nodes.Defining) -> Type:
		self.variables[node.var.name.operand] = node.var.typ
		return types.VOID
	def check_save(self, node:nodes.Save) -> Type:
		space = self.check(node.space)
		value = self.check(node.value)
		if not isinstance(space, types.Ptr):
			print(f"ERROR: {node.loc}: expected pointer to value, got '{space}'", file=stderr)
			sys.exit(52)
		if space.pointed != value:
			print(f"ERROR: {node.loc}: space type '{space}' does not match value's type '{value}'", file=stderr)
			sys.exit(53)
		return types.VOID
	def check_reassignment(self, node:nodes.ReAssignment) -> Type:
		actual = self.check(node.value)
		specified = self.variables.get(node.name.operand)
		if specified is None:#auto
			specified = actual
			self.variables[node.name.operand] = actual
		if actual != specified:
			print(f"ERROR: {node.name.loc}: variable type '{specified}' does not match provided type '{actual}' (to override specify type)", file=stderr)
			sys.exit(54)
		return types.VOID
	def check_if(self, node:nodes.If) -> Type:
		actual = self.check(node.condition)
		if actual != types.BOOL:
			print(f"ERROR: {node.loc}: if statement expected {types.BOOL} value, got {actual}", file=stderr)
			sys.exit(55)
		if node.else_code is None:
			return self.check(node.code) #@return
		actual_if = self.check(node.code)
		actual_else = self.check(node.else_code) #@return
		if actual_if != actual_else:
			print(f"ERROR: {node.loc}: one branch return's while another does not (tip:refactor without 'else')", file=stderr)
			sys.exit(56)
		return actual_if
	def check_while(self, node:nodes.While) -> Type:
		actual = self.check(node.condition)
		if actual != types.BOOL:
			print(f"ERROR: {node.loc}: while statement expected {types.BOOL} value, got {actual}", file=stderr)
			sys.exit(57)
		return self.check(node.code)
	def check_unary_exp(self, node:nodes.UnaryExpression) -> Type:
		return node.typ(self.check(node.left))
	def check_constant(self, node:nodes.Constant) -> Type:
		return node.typ
	def check_var(self, node:nodes.Var) -> Type:
		return types.VOID
	def check_const(self, node:nodes.Const) -> Type:
		return types.VOID
	def check_struct(self, node:nodes.Struct) -> Type:
		return types.VOID
	def check_mix(self, node:nodes.Mix) -> Type:
		return types.VOID
	def check_use(self, node:nodes.Use) -> Type:
		return types.VOID
	def check_return(self, node:nodes.Return) -> Type:
		ret = self.check(node.value)
		if ret != self.expected_return_type:
			print(f"ERROR: {node.loc}: actual return type ({ret}) does not match expected return type ({self.expected_return_type})", file=stderr)
			sys.exit(58)
		return ret
	def check_dot(self, node:nodes.Dot) -> Type:
		origin = self.check(node.origin)
		if isinstance(origin, types.Module):
			typ = self.modules[origin.module.uid].variables.get(node.access.operand)
			if typ is None:
				print(f"ERROR: {node.loc}: module '{origin.path}' does not have variable named '{node.access}'", file=stderr)
				sys.exit(59)
			return typ
		if not isinstance(origin,types.Ptr):
			print(f"ERROR: {node.loc}: trying to '.' not of the pointer/module", file=stderr)
			sys.exit(60)
		pointed = origin.pointed
		if isinstance(pointed, types.Struct): return types.Ptr(node.lookup_struct(pointed.struct)[1])
		else:
			print(f"ERROR: {node.loc}: trying to '.' of the {pointed}, which is not supported", file=stderr)
			sys.exit(61)
	def check_get_item(self, node:nodes.GetItem) -> Type:
		origin = self.check(node.origin)
		subscript = self.check(node.subscript)
		if origin == types.STR:
			if subscript != types.INT:
				print(f"ERROR: {node.loc} string subscript should be {types.INT}, not {subscript}", file=stderr)
				sys.exit(62)
			return types.CHAR
		if not isinstance(origin,types.Ptr):
			print(f"ERROR: {node.loc}: trying to get item not of the pointer or string", file=stderr)
			sys.exit(63)
		pointed = origin.pointed
		if isinstance(pointed, types.Array):
			if subscript != types.INT:
				print(f"ERROR: {node.loc} array subscript should be {types.INT}, not {subscript}", file=stderr)
				sys.exit(64)
			return types.Ptr(pointed.typ)
		else:
			print(f"ERROR: {node.loc}: trying to get item of the {pointed}, which is not supported", file=stderr)
			sys.exit(65)
	def check_string_cast(self, node:nodes.StrCast) -> Type:
		# length should be int, pointer should be ptr(char)
		length = self.check(node.length)
		if length != types.INT:
			print(f"ERROR: {node.loc}: string length should be {types.INT}, not {length}", file=stderr)
			sys.exit(66)
		pointer = self.check(node.pointer)
		if pointer != types.Ptr(types.CHAR):
			print(f"ERROR: {node.loc}: string pointer should be {types.Ptr(types.CHAR)}, not {pointer}", file=stderr)
			sys.exit(67)
		return types.STR
	def check_cast(self, node:nodes.Cast) -> Type:
		left = self.check(node.value)
		right = node.typ
		isptr:Callable[[Type], bool] = lambda typ: isinstance(typ, types.Ptr)
		if not(
			(isptr(left) and isptr(right)) or
			(left == types.STR   and isptr(right)        ) or
			(left == types.STR   and right == types.INT  ) or
			(left == types.BOOL  and right == types.CHAR ) or
			(left == types.BOOL  and right == types.SHORT) or
			(left == types.BOOL  and right == types.INT  ) or
			(left == types.CHAR  and right == types.SHORT) or
			(left == types.CHAR  and right == types.INT  ) or
			(left == types.SHORT and right == types.INT  ) or
			(left == types.INT   and right == types.SHORT) or
			(left == types.INT   and right == types.CHAR ) or
			(left == types.INT   and right == types.BOOL ) or
			(left == types.SHORT and right == types.CHAR ) or
			(left == types.SHORT and right == types.BOOL ) or
			(left == types.CHAR  and right == types.BOOL )
		):
			print(f"ERROR: {node.loc}: trying to cast type '{left}' to type '{node.typ}' which is not supported", file=stderr)
			sys.exit(68)
		return node.typ
	def check(self, node:Node|Token) -> Type:
		if   type(node) == nodes.Import           : return self.check_import        (node)
		elif type(node) == nodes.FromImport       : return self.check_from_import   (node)
		elif type(node) == nodes.Fun              : return self.check_fun           (node)
		elif type(node) == nodes.Var              : return self.check_var           (node)
		elif type(node) == nodes.Const            : return self.check_const         (node)
		elif type(node) == nodes.Mix              : return self.check_mix           (node)
		elif type(node) == nodes.Struct           : return self.check_struct        (node)
		elif type(node) == nodes.Code             : return self.check_code          (node)
		elif type(node) == nodes.Call             : return self.check_call          (node)
		elif type(node) == nodes.BinaryExpression : return self.check_bin_exp       (node)
		elif type(node) == nodes.UnaryExpression  : return self.check_unary_exp     (node)
		elif type(node) == nodes.Constant         : return self.check_constant      (node)
		elif type(node) == nodes.ExprStatement    : return self.check_expr_state    (node)
		elif type(node) == nodes.Assignment       : return self.check_assignment    (node)
		elif type(node) == nodes.ReferTo          : return self.check_refer         (node)
		elif type(node) == nodes.Defining         : return self.check_defining      (node)
		elif type(node) == nodes.ReAssignment     : return self.check_reassignment  (node)
		elif type(node) == nodes.Save             : return self.check_save          (node)
		elif type(node) == nodes.If               : return self.check_if            (node)
		elif type(node) == nodes.While            : return self.check_while         (node)
		elif type(node) == nodes.Return           : return self.check_return        (node)
		elif type(node) == nodes.Dot              : return self.check_dot           (node)
		elif type(node) == nodes.GetItem          : return self.check_get_item      (node)
		elif type(node) == nodes.Cast             : return self.check_cast          (node)
		elif type(node) == nodes.StrCast          : return self.check_string_cast   (node)
		elif type(node) == nodes.Use              : return self.check_use           (node)
		elif type(node) == Token                  : return self.check_token         (node)
		else:
			assert False, f"Unreachable, unknown {type(node)=}"
