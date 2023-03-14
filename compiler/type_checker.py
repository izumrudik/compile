from dataclasses import dataclass
from enum import Enum, auto
from typing import Callable

from .primitives import nodes, Node, ET, Config, Type, types, DEFAULT_TEMPLATE_STRING_FORMATTER, BUILTIN_WORDS, Place
__all__ = (
	'SemanticTokenType',
	'SemanticTokenModifier',
	'SemanticToken',
	'TypeChecker',
)
class SemanticTokenType(Enum):
	MODULE           = auto()
	STRUCT           = auto()
	ARGUMENT         = auto()
	VARIABLE         = auto()
	PROPERTY         = auto()
	FUNCTION         = auto()
	BOUND_FUNCTION   = auto()
	MIX              = auto()
	STRING           = auto()
	INTEGER          = auto()
	CHARACTER_STRING = auto()
	CHARACTER_NUMBER = auto()
	SHORT            = auto()
	OPERATOR         = auto()
	TYPE             = auto()
	ENUM 		     = auto()
	ENUM_ITEM        = auto()
	def __str__(self) -> str:
		return self.name.lower().replace('_', ' ')
class SemanticTokenModifier(Enum):
	DECLARATION  = auto()
	DEFINITION   = auto()
	STATIC       = auto()
	def __str__(self) -> str:
		return self.name.lower()
@dataclass(frozen=True, slots=True)
class SemanticToken:
	place:Place
	typ:SemanticTokenType
	modifiers:tuple[SemanticTokenModifier,...] = ()
	value_type:Type|None = None
	def_place:Place|None = None

expand:Callable[
[tuple[Type,Place]|None],
tuple[Type,Place]|tuple[None,None]] = lambda x:(None,None) if x is None else (x[0],x[1])

imported_modules:'dict[str,TypeChecker]' = {}

class TypeChecker:
	__slots__ = ('config', 'module', 'modules', 'names', 'type_names', 'expected_return_type', 'semantic', 'semantic_tokens', 'generic_context')
	def __init__(self, module:nodes.Module, config:Config, semantic:bool = False) -> None:
		self.module              :nodes.Module                 = module
		self.config              :Config                       = config
		self.names               :dict[str, tuple[Type,Place]] = {}#regular definitions like `var x int`
		self.type_names          :dict[str, tuple[Type,Place]] = {}#type definitions like `struct X {}`
		self.modules             :dict[int, TypeChecker]       = {}
		self.expected_return_type:Type                         = types.VOID
		self.generic_context     :list[types.Generics]         = []
		self.semantic            :bool                         = semantic
		self.semantic_tokens     :set[SemanticToken]           = set()
	def go_check(self) -> 'TypeChecker':
		if self.module.builtin_module is not None:
			tc = self.import_module(self.module.builtin_module)
			for name in BUILTIN_WORDS:
				type_definition = tc.type_names.get(name)
				definition = tc.names.get(name)
				assert type_definition is not None or None is not definition, f"Unreachable, std.builtin does not have word '{name}' defined, but it must"
				if definition is not None:
					self.names[name] = definition
				if type_definition is not None:
					self.type_names[name] = type_definition
		for top in self.module.tops:
			self.check(top)
		return self

	def import_module(self,module:nodes.Module) -> 'TypeChecker':
		if module.path in imported_modules:
			tc = imported_modules[module.path]
		else:
			tc = TypeChecker(module, self.config)
			tc.go_check()
			imported_modules[module.path] = tc
		self.modules[module.uid] = tc
		return tc

	def check_import(self, node:nodes.Import) -> Type:
		self.import_module(node.module)
		self.names[node.name] = types.Module(node.module.uid,node.module.path),node.path_place
		if self.semantic:self.semantic_tokens.add(SemanticToken(node.path_place, SemanticTokenType.MODULE, (SemanticTokenModifier.DECLARATION,)))
		return types.VOID
	def check_from_import(self, node:nodes.FromImport) -> Type:
		tc = self.import_module(node.module)
		for nam in node.imported_names:
			name = nam.operand
			type_definition = tc.type_names.get(name)
			definition = tc.names.get(name)
			if type_definition is definition is None:
				self.config.errors.add_error(ET.IMPORT_NAME, node.place, f"name '{name}' is not defined in module '{node.module.path}'")
			if self.semantic:
				self.semantic_reference_helper_from_typ(definition, nam.place, (SemanticTokenModifier.DECLARATION,))
			if definition is not None:
				self.names[name] = definition
			if type_definition is not None:
				self.type_names[name] = type_definition
		if self.semantic:self.semantic_tokens.add(SemanticToken(node.path_place, SemanticTokenType.MODULE, (SemanticTokenModifier.DECLARATION,)))
		return types.VOID
	def check_enum(self, node:nodes.Enum) -> Type:
		generics = node.generics.typ()
		old_type_names = self.type_names.copy()
		old_context = self.generic_context.copy()
		if len(generics.generics) != 0:
			self.generic_context.append(generics)
		for generic in node.generics.generics:
			self.type_names[generic.name.operand] = generic.typ(),generic.name.place
		enum_type = self.enum_to_typ(node)
		old_type_names[node.name.operand] = self.type_names[node.name.operand] = enum_type,node.name.place
		self.names[node.name.operand] = types.EnumKind(enum_type),node.name.place
		if self.semantic:self.semantic_tokens.add(SemanticToken(node.name.place, SemanticTokenType.ENUM, (SemanticTokenModifier.DEFINITION,)))
		for fun in node.funs:
			rt = self.fun_to_typ(fun).return_type
			self.check_bound_fun_helper(enum_type,fun,rt)
		if self.semantic:
			for item in node.items:
				self.semantic_tokens.add(SemanticToken(item.place, SemanticTokenType.ENUM_ITEM, (SemanticTokenModifier.DEFINITION,)))
		for typed_item in node.typed_items:
			self.validate(self.check(typed_item.typ),ET.INVALID_ENUM_ITEM,typed_item.typ.place)
			if self.semantic:
				self.semantic_tokens.add(SemanticToken(typed_item.name.place, SemanticTokenType.ENUM_ITEM, (SemanticTokenModifier.DEFINITION,), self.check(typed_item.typ)))
		self.type_names = old_type_names
		self.generic_context = old_context
		return types.VOID
	def check_fun(self, node:nodes.Fun, semantic_type:SemanticTokenType = SemanticTokenType.FUNCTION, bound_args:int=0, add_name:bool=True) -> Type:
		assert bound_args == 0 or not add_name

		if node.is_main:#check main
			if len(node.generics.generics) != 0:
				self.config.errors.add_error(ET.MAIN_GENERIC, node.generics.place, f"entry point (function 'main') has to not be generic, found {node.generics}")
			if node.return_type is not None:
				if self.check(node.return_type) != types.VOID:
					self.config.errors.add_error(ET.MAIN_RETURN, node.return_type_place, f"entry point (function 'main') has to return {types.VOID}, found '{node.return_type}'")
			if len(node.arg_types) != 0:
				self.config.errors.add_error(ET.MAIN_ARGS, node.args_place, f"entry point (function 'main') has to take no arguments, found '({', '.join(map(str,node.arg_types))})'")
		
		#store previous state
		vars_before = self.names.copy()
		ert_before = self.expected_return_type
		type_vars_before = self.type_names.copy()
		old_context = self.generic_context.copy()
		# modify state
		generics = node.generics.typ()
		fun_typ = self.fun_to_typ(node,0)
		if len(generics.generics) != 0:
			self.generic_context.append(generics)
		for generic in node.generics.generics:
			self.type_names[generic.name.operand] = generic.typ(),generic.name.place
		if add_name and bound_args==0:#check for struct/enum funs
			self.names[node.name.operand] = fun_typ,node.name.place
			vars_before[node.name.operand] = self.names[node.name.operand]
		for arg in node.arg_types:
			arg_typ = self.check(arg.typ)
			self.names[arg.name.operand] = arg_typ,arg.name.place
			self.validate(arg_typ,ET.INVALID_FUN_ARG,arg.place)

		specified_return_type = fun_typ.return_type
		self.expected_return_type = specified_return_type
		if specified_return_type is not types.VOID:#free pass
			self.validate(specified_return_type,ET.INVALID_FUN_RETURN, node.return_type_place)
		#run
		actual_return_type = self.check(node.code)

		if specified_return_type != actual_return_type:
			self.config.errors.add_error(ET.FUN_RETURN, node.return_type_place, f"specified return type is '{specified_return_type}' but function did not return")

		if self.semantic:#semantic
			self.semantic_tokens.add(SemanticToken(node.name.place,semantic_type,(SemanticTokenModifier.DEFINITION,), self.fun_to_typ(node,bound_args)))
			for arg in node.arg_types:
				self.semantic_tokens.add(SemanticToken(arg.name.place,SemanticTokenType.ARGUMENT,(SemanticTokenModifier.DECLARATION,)))

		#restore previous state
		self.names = vars_before
		self.expected_return_type = ert_before
		self.type_names = type_vars_before
		self.generic_context = old_context
		return types.VOID

	def validate(self,value:Type,et:ET,place:Place,context:str='this context') -> None:
		if not value.sized or not value.generic_safe(self.generic_context):
			self.config.errors.add_error(et,place,f"'{value}' is invalid for use in {context} (not sized/generic)")

	def check_code(self, node:nodes.Code) -> Type:
		vars_before = self.names.copy()
		ret:Type = types.VOID
		for statement in node.statements:
			#every statement's check should return types.VOID if (and only if) there is a way, that `return` can be not executed in it
			r = self.check(statement)
			#... should return self.expected_return_type if (and only if) `return` will be definitely executed it this statement
			if ret == types.VOID != r:
				ret = r
				assert r == self.expected_return_type, f"{type(statement)} statement did not follow return rules"
				#other things are not allowed
		self.names = vars_before #this is scoping
		return ret
	def check_call(self, node:nodes.Call) -> Type:
		return self.call_helper(self.check(node.func), tuple(self.check(arg) for arg in node.args), node.place)
	def call_helper(self, function:Type, args:tuple[Type,...], place:Place) -> Type:
		def get_fun_out_of_called(called:Type) -> types.Fun:
			if isinstance(called, types.Fun):
				return called
			if isinstance(called, types.StructKind):
				m = called.struct.get_magic('init')
				if m is None:
					self.config.errors.critical_error(ET.INIT_MAGIC, place, f"structure '{called}' has no '__init__' magic defined")
				magic,_ = m
				return types.Fun(
					magic.visible_arg_types,
					types.Ptr(called.struct),
					called.struct.generics,
					called.struct.generic_filler,
				)
			if isinstance(called, types.Mix):
				for ref in called.funs:
					fun = get_fun_out_of_called(ref)
					if len(args) != len(fun.visible_arg_types):
						continue#continue searching
					for actual_arg,arg in zip(args,fun.visible_arg_types,strict=True):
						if actual_arg != arg:
							break#break to continue
					else:
						return fun#found fun
					continue
				self.config.errors.critical_error(ET.CALL_MIX, place, f"did not find function to match '{','.join(map(str,args))}' contract in mix '{called.name}'")
			self.config.errors.critical_error(ET.CALLABLE, place, f"'{called}' object is not callable")
		fun = get_fun_out_of_called(function)
		if len(fun.visible_arg_types) != len(args):
			self.config.errors.add_error(ET.CALL_ARGS, place, f"function '{fun}' accepts {len(fun.visible_arg_types)} arguments, provided {len(args)} arguments")
			return fun.return_type
		if not fun.generic_safe(self.generic_context):
			fill_types = self.try_infer_generics(fun.visible_arg_types,args,fun.generics.generics)
			if fill_types is None:
				self.config.errors.add_error(ET.CALL_GENERIC, place, f"could not infer generic types for function '{fun}', specify them with !<> syntax")
			else:
				f = self.generic_fill_helper(fill_types,fun,place)
				assert isinstance(f,types.Fun)
				fun = f
		for idx, typ in enumerate(args):
			needed = fun.visible_arg_types[idx]
			if typ != needed:
				self.config.errors.add_error(ET.CALL_ARG, place, f"function '{fun}' argument {idx} takes '{needed}', got '{typ}'")
			self.validate(typ,ET.INVALID_CALL_ARG, place, f"call argument #{idx}")
		return fun.return_type
	def try_infer_generics(self, defined_types:tuple[Type,...], provided_types:tuple[Type,...],generics:tuple[types.Generic,...]) -> None|tuple[Type,...]:
		inferred_generics:tuple[types.Generic, ...] = ()
		inferred_values:tuple[Type, ...] = ()
		for defined,provided in zip(defined_types,provided_types,strict=True):
			g,f=defined.infer_generics(provided)
			inferred_generics,inferred_values = inferred_generics+g,inferred_values+f
		out = []
		for generic in generics:
			try:
				value = inferred_values[inferred_generics.index(generic)]
			except ValueError: return None
			for idx,i in enumerate(inferred_generics):
				if i == generic and inferred_values[idx] != value: return None
			out.append(value)
		return tuple(out)
	def check_bin_exp(self, node:nodes.BinaryOperation) -> Type:
		left = self.check(node.left)
		right = self.check(node.right)
		self.validate(left,ET.INVALID_BIN_OP_LEFT,node.left.place)
		self.validate(right,ET.INVALID_BIN_OP_LEFT,node.right.place)
		result = node.typ(left,right, self.config)
		if self.semantic:
			self.semantic_tokens.add(SemanticToken(node.operation_place,SemanticTokenType.OPERATOR,value_type=result))
		return result
	def check_expr_state(self, node:nodes.ExprStatement) -> Type:
		self.check(node.value)
		return types.VOID
	def check_str(self, node:nodes.Str) -> Type:
		result = types.STR
		if self.semantic:self.semantic_tokens.add(SemanticToken(node.place,SemanticTokenType.STRING,value_type=result))
		return result
	def check_int(self, node:nodes.Int) -> Type:
		result = types.INT
		if self.semantic:self.semantic_tokens.add(SemanticToken(node.place,SemanticTokenType.INTEGER,value_type=result))
		return result
	def check_short(self, node:nodes.Short) -> Type:
		result = types.SHORT
		if self.semantic:self.semantic_tokens.add(SemanticToken(node.place,SemanticTokenType.SHORT,value_type=result))
		return result
	def check_char_str(self, node:nodes.CharStr) -> Type:
		result = types.CHAR
		if self.semantic:self.semantic_tokens.add(SemanticToken(node.place,SemanticTokenType.CHARACTER_STRING,value_type=result))
		return result
	def check_char_num(self, node:nodes.CharNum) -> Type:
		result = types.CHAR
		if self.semantic:self.semantic_tokens.add(SemanticToken(node.place,SemanticTokenType.CHARACTER_NUMBER,value_type=result))
		return result
	def check_assignment(self, node:nodes.Assignment) -> Type:
		actual_type = self.check(node.value)
		if self.semantic:
			self.semantic_tokens.add(SemanticToken(node.var.name.place,SemanticTokenType.VARIABLE, (SemanticTokenModifier.DEFINITION,),actual_type))
		if self.check(node.var.typ) != actual_type:
			self.config.errors.add_error(ET.ASSIGNMENT, node.place, f"specified type '{node.var.typ}' does not match actual type '{actual_type}' in assignment")
		self.validate(actual_type,ET.INVALID_ASSIGNMENT,node.value.place)
		self.names[node.var.name.operand] = types.Ptr(self.check(node.var.typ)),node.var.name.place
		return types.VOID
	def semantic_reference_helper_from_typ(self, definition:tuple[Type,Place]|None, place:Place, modifiers:tuple[SemanticTokenModifier, ...] = ()) -> None:
		typ, def_place = expand(definition)
		if self.semantic:
			if   isinstance(typ, types.Struct)    :self.semantic_tokens.add(SemanticToken(place,SemanticTokenType.STRUCT,   modifiers, typ, def_place))
			elif isinstance(typ, types.Fun)       :self.semantic_tokens.add(SemanticToken(place,SemanticTokenType.FUNCTION, modifiers, typ, def_place))
			elif isinstance(typ, types.Mix)       :self.semantic_tokens.add(SemanticToken(place,SemanticTokenType.MIX,      modifiers, typ, def_place))
			elif isinstance(typ, types.Module)    :self.semantic_tokens.add(SemanticToken(place,SemanticTokenType.MODULE,   modifiers, typ, def_place))
			else                                  :self.semantic_tokens.add(SemanticToken(place,SemanticTokenType.VARIABLE, modifiers, typ, def_place))
	def check_refer(self, node:nodes.ReferTo) -> Type:
		typ = self.names.get(node.name.operand)
		if self.semantic:
			self.semantic_reference_helper_from_typ(typ, node.name.place)
		if typ is None:
			self.config.errors.add_error(ET.REFER, node.place, f"did not find name '{node.name}'")
			return types.VOID
		return typ[0]
	def check_declaration(self, node:nodes.Declaration) -> Type:
		typ = self.check(node.var.typ)
		if self.semantic:
			self.semantic_tokens.add(SemanticToken(node.var.name.place,SemanticTokenType.VARIABLE, (SemanticTokenModifier.DECLARATION,),typ))
		self.validate(typ,ET.INVALID_DECLARATION,node.var.typ.place)
		
		if node.times is None:
			self.names[node.var.name.operand] = types.Ptr(typ), node.var.name.place
			return types.VOID
		times = self.check(node.times)
		if times != types.INT:
			self.config.errors.add_error(ET.DECLARATION_TIMES, node.place, f"number of elements to allocate should be an '{types.INT}', got '{times}'")
		self.names[node.var.name.operand] = types.Ptr(types.Array(typ)),node.var.name.place
		return types.VOID
	def check_save(self, node:nodes.Save) -> Type:
		space = self.check(node.space)
		value = self.check(node.value)
		if not isinstance(space, types.Ptr):
			self.config.errors.add_error(ET.SAVE_PTR, node.place, f"expected pointer to save into, got '{space}'")
			return types.VOID
		if space.pointed != value:
			self.config.errors.add_error(ET.SAVE, node.place, f"space type '{space}' does not match value's type '{value}'")
		self.validate(value,ET.INVALID_SAVE,node.value.place)
		return types.VOID
	def check_variable_save(self, node:nodes.VariableSave) -> Type:
		space,_ = expand(self.names.get(node.space.operand))
		value = self.check(node.value)
		if self.semantic:
			self.semantic_tokens.add(SemanticToken(node.space.place,SemanticTokenType.VARIABLE, (SemanticTokenModifier.DEFINITION,),value))
		if space is None:#auto
			space = types.Ptr(value)
			self.names[node.space.operand] = space,node.space.place
		self.validate(value,ET.INVALID_VSAVE,node.value.place)
		if not isinstance(space, types.Ptr):
			self.config.errors.add_error(ET.VSAVE_PTR, node.place, f"expected pointer to save into, got '{space}'")
			return types.VOID
		if space.pointed != value:
			self.config.errors.add_error(ET.VSAVE, node.place, f"space-pointed type '{space.pointed}' does not match value's type '{value}'")
		return types.VOID
	def check_if(self, node:nodes.If) -> Type:
		actual = self.check(node.condition)
		if actual != types.BOOL:
			self.config.errors.add_error(ET.IF, node.condition.place, f"if statement expected '{types.BOOL}' type, got '{actual}'")
		if node.else_code is None:
			self.check(node.code)
			return types.VOID
		actual_if = self.check(node.code)
		actual_else = self.check(node.else_code)
		if actual_if != actual_else:
			self.config.errors.add_error(ET.IF_BRANCH, node.place, f"if branches are inconsistent: one branch returns while other does not (refactor without 'else')")
			return actual_if if actual_else == types.VOID else actual_else
		return actual_if
	def check_while(self, node:nodes.While) -> Type:
		actual = self.check(node.condition)
		if actual != types.BOOL:
			self.config.errors.add_error(ET.WHILE, node.place, f"while statement expected '{types.BOOL}' type, got '{actual}'")
		return self.check(node.code)
	def check_set(self, node:nodes.Set) -> Type:
		value = self.check(node.value)
		if self.semantic:
			self.semantic_tokens.add(SemanticToken(node.name.place,SemanticTokenType.VARIABLE, (SemanticTokenModifier.DEFINITION,),value))
		self.names[node.name.operand] = value,node.name.place
		return types.VOID
	def check_unary_exp(self, node:nodes.UnaryExpression) -> Type:
		result = node.typ(self.check(node.left), self.config)
		self.validate(result,ET.INVALID_UNARY_OP,node.left.place)
		if self.semantic:
			self.semantic_tokens.add(SemanticToken(node.operation.place,SemanticTokenType.OPERATOR,value_type=result))
		return result
	def check_constant(self, node:nodes.Constant) -> Type:
		return node.typ
	def check_var(self, node:nodes.Var) -> Type:
		typ = self.check(node.typ)
		self.names[node.name.operand] = types.Ptr(typ),node.name.place
		self.validate(typ,ET.INVALID_VAR,node.typ.place)
		if self.semantic:
			self.semantic_tokens.add(SemanticToken(node.name.place,SemanticTokenType.VARIABLE, (SemanticTokenModifier.DECLARATION,),typ))
		return types.VOID
	def check_const(self, node:nodes.Const) -> Type:
		self.names[node.name.operand] = types.INT,node.name.place
		if self.semantic:
			self.semantic_tokens.add(SemanticToken(node.name.place,SemanticTokenType.VARIABLE, (SemanticTokenModifier.DEFINITION,),types.INT))
		return types.VOID
	def fun_to_typ(self,node:nodes.Fun, bound_args:int=0) -> types.Fun:
		copied_type_names = self.type_names.copy()
		for generic in node.generics.generics:
			self.type_names[generic.name.operand] = generic.typ(),generic.name.place
		generics = node.generics.typ()
		out = types.Fun(tuple(self.check(arg.typ) for arg in node.arg_types[bound_args:]),
		  self.check(node.return_type) if node.return_type is not None else types.VOID,
		  generics,
		  generics.generics)
		self.type_names = copied_type_names
		return out
	def struct_to_typ(self,node:nodes.Struct) -> types.Struct:
		copied_type_names = self.type_names.copy()
		struct = types.Struct('',(),0,(),types.Generics.empty(),'',())
		self.type_names[node.name.operand] = struct,node.name.place
		generics = node.generics.typ()
		right_version = types.Struct(node.name.operand,
			       tuple((arg.name.operand,self.check(arg.typ)) for arg in node.variables),
				   node.uid,
				   tuple((fun.name.operand,self.fun_to_typ(fun,1),self.get_suffix(fun.llvmid)) for fun in node.funs),
				   generics,
				   self.get_suffix(''),
				   generics.generics)
		struct.__dict__ = right_version.__dict__#FIXME
		self.type_names = copied_type_names
		return struct
	def get_suffix(self,llvmid:str) -> str:
		if len(self.generic_context) == 0:return llvmid
		suffix = ''
		for context in self.generic_context:
			suffix = context.replace_llvm(context.generics,suffix)
		return types.Generics.replace_llvmid(suffix,llvmid)
	def enum_to_typ(self,node:nodes.Enum) -> types.Enum:
		copied_type_names = self.type_names.copy()
		enum_type = types.Enum('',(),(),(),0,types.Generics.empty(),'',())
		self.type_names[node.name.operand] = enum_type,node.name.place
		generics = node.generics.typ()
		right_version = types.Enum(node.name.operand,
			     tuple(item.operand for item in node.items),
				 tuple((item.name.operand,self.check(item.typ)) for item in node.typed_items),
				 tuple((fun.name.operand,self.fun_to_typ(fun,1),self.get_suffix(fun.llvmid)) for fun in node.funs),
				 node.uid,generics,
				 self.get_suffix(''),
				 generics.generics)
		enum_type.__dict__ = right_version.__dict__#FIXME
		self.type_names = copied_type_names
		return enum_type

	def check_struct(self, node:nodes.Struct) -> Type:
		generics = node.generics.typ()
		old_type_names = self.type_names.copy()
		old_context = self.generic_context.copy()
		if len(generics.generics) != 0:
			self.generic_context.append(generics)
		for generic in node.generics.generics:
			self.type_names[generic.name.operand] = generic.typ(),generic.name.place
		struct_type = self.struct_to_typ(node)
		old_type_names[node.name.operand] = self.type_names[node.name.operand] = struct_type,node.name.place
		self.names[node.name.operand] = types.StructKind(struct_type),node.name.place
		if self.semantic:
			self.semantic_tokens.add(SemanticToken(node.name.place,SemanticTokenType.STRUCT, (SemanticTokenModifier.DEFINITION,),struct_type))
		for var in node.variables:
			self.validate(self.check(var.typ),ET.INVALID_STRUCT_VAR,var.typ.place)
			if self.semantic:
				self.semantic_tokens.add(SemanticToken(var.name.place,SemanticTokenType.PROPERTY, (SemanticTokenModifier.DEFINITION,),self.check(var.typ)))
		for fun in node.funs:
			rt = self.fun_to_typ(fun,1).return_type
			self.check_bound_fun_helper(types.Ptr(struct_type),fun,rt)
			if fun.name.operand == '__init__':
				if rt != types.VOID:
					self.config.errors.add_error(ET.INIT_MAGIC_RET, fun.return_type_place, f"'__init__' magic method should return '{types.VOID}', not '{fun.return_type}'")
		
		self.type_names = old_type_names
		self.generic_context = old_context
		return types.VOID
	def check_bound_fun_helper(self,self_should_be:Type,fun:nodes.Fun,rt:Type) -> None:
		if len(fun.arg_types)==0:
			self.config.errors.critical_error(ET.BOUND_FUN_ARGS, fun.args_place, f"bound function's argument 0 should be '{self_should_be}' (self), found 0 arguments")
		elif self.check(fun.arg_types[0].typ) != self_should_be:
			self.config.errors.add_error(ET.BOUND_FUN_ARG, fun.arg_types[0].place, f"bound function's argument 0 should be '{self_should_be}' (self) got '{fun.arg_types[0].typ}'")
		if fun.name == '__str__':
			if len(fun.arg_types) != 1:
				self.config.errors.critical_error(ET.BOUND_STR_MAGIC, fun.args_place, f"magic function '__str__' should have 1 argument, not {len(fun.arg_types)}")
			if rt != types.STR:
				self.config.errors.critical_error(ET.BOUND__STR__RET, fun.return_type_place, f"magic function '__str__' should return {types.STR}, not {fun.return_type}")
		self.check_fun(fun, SemanticTokenType.BOUND_FUNCTION,1,False)
	def check_mix(self, node:nodes.Mix) -> Type:
		self.names[node.name.operand] = types.Mix(tuple(self.check(fun_ref) for fun_ref in node.funs),node.name.operand),node.name.place
		if self.semantic:
			self.semantic_tokens.add(SemanticToken(node.name.place,SemanticTokenType.FUNCTION, (SemanticTokenModifier.DEFINITION,)))
		return types.VOID
	def check_use(self, node:nodes.Use) -> Type:
		self.names[node.as_name.operand] = types.Fun(tuple(self.check(arg) for arg in node.arg_types),self.check(node.return_type),types.Generics.empty(),()),node.name.place
		for arg in node.arg_types:
			self.validate(self.check(arg),ET.INVALID_USE_ARG, arg.place)
		if self.check(node.return_type) is not types.VOID:#free pass
			self.validate(self.check(node.return_type),ET.INVALID_USE_RETURN, node.return_type.place)
		if self.semantic:
			self.semantic_tokens.add(SemanticToken(node.name.place,SemanticTokenType.FUNCTION, (SemanticTokenModifier.DECLARATION,)))
			if node.as_name is not node.name:
				self.semantic_tokens.add(SemanticToken(node.as_name.place,SemanticTokenType.FUNCTION))
		return types.VOID
	def check_return(self, node:nodes.Return) -> Type:
		ret = self.check(node.value)
		if ret != self.expected_return_type:
			self.config.errors.add_error(ET.RETURN, node.place, f"actual return type '{ret}' does not match specified return type '{self.expected_return_type}'")
		if ret is not types.VOID:#gets a free pass
			self.validate(ret,ET.INVALID_RETURN, node.value.place)
		return self.expected_return_type
	def check_assert(self, node:nodes.Assert) -> Type:
		value = self.check(node.value)
		explanation = self.check(node.explanation)
		if value != types.BOOL:
			self.config.errors.add_error(ET.ASSERT_VALUE, node.value.place, f"assert value type '{value}' should be '{types.BOOL}'")
		if explanation != types.STR:
			self.config.errors.add_error(ET.ASSERT_EXPLANATION, node.explanation.place, f"assert explanation type '{explanation}' should be '{types.STR}'")
		return types.VOID
	def check_dot(self, node:nodes.Dot) -> Type:
		origin = self.check(node.origin)
		if isinstance(origin, types.Module):
			typ,place = expand(self.modules[origin.module_uid].names.get(node.access.operand))
			if self.semantic:
				self.semantic_tokens.add(SemanticToken(node.access.place,SemanticTokenType.PROPERTY, value_type=typ,def_place=place))
			if typ is None:
				self.config.errors.critical_error(ET.DOT_MODULE, node.access.place, f"name '{node.access}' was not found in module '{origin.path}'")
			return typ
		elif isinstance(origin, types.EnumKind):
			_,typ = node.lookup_enum_kind(origin, self.config)
			if self.semantic:
				self.semantic_tokens.add(SemanticToken(node.access.place,SemanticTokenType.ENUM_ITEM, value_type=typ))
			return typ
		elif isinstance(origin, types.Enum):
			fun,_ = node.lookup_enum(origin, self.config)
			typ = fun
		elif isinstance(origin,types.Ptr):
			pointed = origin.pointed
			if isinstance(pointed, types.Struct):
				k = node.lookup_struct(pointed, self.config)
				if isinstance(k[0],int):
					typ = types.Ptr(k[1])
				else:
					typ = k[0]
			else:
				self.config.errors.critical_error(ET.DOT, node.access.place, f"'{origin}' object doesn't have any attributes")#same
		else:
			self.config.errors.critical_error(ET.DOT, node.access.place, f"'{origin}' object doesn't have any attributes")#same
		if self.semantic:self.semantic_tokens.add(SemanticToken(node.access.place,SemanticTokenType.PROPERTY, value_type=typ))
		return typ

	def check_generic_fill(self, node:nodes.FillGeneric) -> Type:
		origin = self.check(node.origin)
		fill_types = tuple(self.check(fill_type) for fill_type in node.filler_types)
		return self.generic_fill_helper(fill_types,origin,node.access_place)
	def generic_fill_helper(self, fill_types:tuple[Type,...], origin:Type,access_place:Place) -> Type:
		if isinstance(origin, types.Fun):
			generics = origin.generics
		elif isinstance(origin, types.StructKind):
			generics = origin.struct.generics
		elif isinstance(origin, types.EnumKind):
			generics = origin.enum.generics
		elif isinstance(origin, types.Struct):
			generics = origin.generics
		elif isinstance(origin, types.Enum):
			generics = origin.generics
		else:
			self.config.errors.add_error(ET.GENERIC_FILL, access_place, f"'{origin}' object can't be generic")
			return types.VOID
		for idx,fill in enumerate(fill_types):
			self.validate(fill, ET.INVALID_GENERIC_FILL, access_place, f"generic filler type #{idx}")
		if len(fill_types) != len(generics.generics):
			self.config.errors.critical_error(ET.GENERIC_FILL_LEN, access_place, f"expected {len(generics.generics)} generic filler types, found {len(fill_types)}")
		return generics.fill_generics(fill_types,self.generic_context,origin,self.config,access_place)
	def check_subscript(self, node:nodes.Subscript) -> Type:
		origin = self.check(node.origin)
		subscripts = [self.check(subscript) for subscript in node.subscripts]
		if origin == types.STR:
			if len(subscripts) != 1:
				self.config.errors.critical_error(ET.STR_SUBSCRIPT_LEN, node.access_place, f"string subscripts should have 1 argument, not {len(subscripts)}")
			if subscripts[0] != types.INT:
				self.config.errors.add_error(ET.STR_SUBSCRIPT, node.access_place, f"string subscript should be 1 '{types.INT}' not '{subscripts[0]}'")
			return types.CHAR
		if isinstance(origin,types.Ptr):
			pointed = origin.pointed
			if isinstance(pointed, types.Array):
				if len(subscripts) != 1:
					self.config.errors.critical_error(ET.ARRAY_SUBSCRIPT_LEN, node.access_place, f"array subscripts should have 1 argument, not {len(subscripts)}")
				if subscripts[0] != types.INT:
					self.config.errors.add_error(ET.ARRAY_SUBSCRIPT, node.access_place, f"array subscript should be '{types.INT}' not '{subscripts[0]}'")
				return types.Ptr(pointed.typ)
			if isinstance(pointed, types.Struct):
				fu = pointed.get_magic('subscript')
				if fu is None:
					self.config.errors.critical_error(ET.SUBSCRIPT_MAGIC, node.access_place, f"structure '{pointed.name}' does not have __subscript__ magic defined")
				fun,_ = fu
				if len(subscripts) != len(fun.visible_arg_types):
					self.config.errors.critical_error(ET.STRUCT_SUB_LEN, node.access_place, f"'{pointed}' struct subscript should have {len(fun.visible_arg_types)} arguments, not {len(subscripts)}")
				for idx, subscript in enumerate(subscripts):
					if fun.visible_arg_types[idx] != subscript:
						self.config.errors.add_error(ET.STRUCT_SUBSCRIPT, node.access_place, f"invalid subscript argument {idx} '{subscript}' for '{pointed}', expected type '{fun.visible_arg_types[idx]}''")
					self.validate(subscript,ET.INVALID_SUBSCRIPT,node.access_place, f"subscript argument #{idx}")
				return fun.return_type
		self.config.errors.critical_error(ET.SUBSCRIPT, node.access_place, f"'{origin}' object is not subscriptable")
	def check_template(self, node:nodes.Template) -> Type:
		for val in node.values:
			self.validate(self.check(val),ET.INVALID_TEMPLATE_VAL, val.place)
		if node.formatter is None:
			formatter,_ = expand(self.names.get(DEFAULT_TEMPLATE_STRING_FORMATTER))
			assert formatter is not None, "DEFAULT_TEMPLATE_STRING_FORMATTER was not imported from sys.builtin"
		else:
			formatter = self.check(node.formatter)
		if not isinstance(formatter, types.Fun):
			assert node.formatter is not None, "DEFAULT_TEMPLATE_STRING_FORMATTER does not meet requirements to be a formatter"
			self.config.errors.critical_error(ET.TEMPLATE_FUN, node.formatter.place, f"template formatter should be a function, not '{formatter}'")
		if len(formatter.visible_arg_types) != 3:
			assert node.formatter is not None, "DEFAULT_TEMPLATE_STRING_FORMATTER does not meet requirements to be a formatter"
			self.config.errors.critical_error(ET.TEMPLATE_ARGS, node.formatter.place, f"template formatter should have 3 arguments, not {len(formatter.visible_arg_types)}")
		if formatter.visible_arg_types[0] != types.Ptr(types.Array(types.STR)):#*[]str
			assert node.formatter is not None, "DEFAULT_TEMPLATE_STRING_FORMATTER does not meet requirements to be a formatter"
			self.config.errors.add_error(ET.TEMPLATE_ARG0, node.formatter.place, f"template formatter argument 0 (strings) should be '{types.Ptr(types.Array(types.STR))}', not '{formatter.visible_arg_types[0]}'")
		if formatter.visible_arg_types[1] != types.Ptr(types.Array(types.STR)):#*[]str
			assert node.formatter is not None, "DEFAULT_TEMPLATE_STRING_FORMATTER does not meet requirements to be a formatter"
			self.config.errors.add_error(ET.TEMPLATE_ARG1, node.formatter.place, f"template formatter argument 1 (values) should be '{types.Ptr(types.Array(types.STR))}', not '{formatter.visible_arg_types[1]}'")
		if formatter.visible_arg_types[2] != types.INT:#int
			assert node.formatter is not None, "DEFAULT_TEMPLATE_STRING_FORMATTER does not meet requirements to be a formatter"
			self.config.errors.add_error(ET.TEMPLATE_ARG2, node.formatter.place, f"template formatter argument 2 (length) should be '{types.INT}', not '{formatter.visible_arg_types[2]}'")
		return formatter.return_type
	def check_string_cast(self, node:nodes.StrCast) -> Type:
		# length should be int, pointer should be ptr(*[]char)
		length = self.check(node.length)
		if length != types.INT:
			self.config.errors.add_error(ET.STR_CAST_LEN, node.place, f"string length should be '{types.INT}' not '{length}'")
		pointer = self.check(node.pointer)
		if pointer != types.Ptr(types.Array(types.CHAR)):
			self.config.errors.add_error(ET.STR_CAST_PTR, node.place, f"string pointer should be '{types.Ptr(types.Array(types.CHAR))}' not '{pointer}'")
		return types.STR
	def check_cast(self, node:nodes.Cast) -> Type:
		left = self.check(node.value)
		right = self.check(node.typ)
		isptr:Callable[[Type], bool] = lambda typ: isinstance(typ, types.Ptr)
		self.validate(left,ET.INVALID_CAST_VALUE,node.value.place)
		self.validate(right,ET.INVALID_CAST_TYPE,node.typ.place)
		if not (
			(isptr(left) and isptr(right)) or
			(left == types.STR   and right == types.Ptr(types.Array(types.CHAR))) or
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
			self.config.errors.critical_error(ET.CAST, node.place, f"casting type '{left}' to type '{right}' is not supported")
		return right
	def check_type_pointer(self, node:nodes.TypePointer) -> Type:
		if self.semantic:
			self.semantic_tokens.add(SemanticToken(node.place, SemanticTokenType.TYPE))
		pointed = self.check(node.pointed)
		return types.Ptr(pointed)
	def check_type_array(self, node:nodes.TypeArray) -> Type:
		if self.semantic:
			self.semantic_tokens.add(SemanticToken(node.place, SemanticTokenType.TYPE))
		element = self.check(node.typ)
		return types.Array(element, node.size)
	def check_type_fun(self, node:nodes.TypeFun) -> Type:
		if self.semantic:
			self.semantic_tokens.add(SemanticToken(node.place, SemanticTokenType.TYPE))
		args = tuple(self.check(arg) for arg in node.args)
		return_type:Type = types.VOID
		if node.return_type is not None:
			return_type = self.check(node.return_type)
		return types.Fun(args,return_type,types.Generics.empty(),())
	def check_type_reference(self, node:nodes.TypeReference) -> Type:
		name = node.ref.operand
		typ:Type|None = {
			'void': types.VOID,
			'bool': types.BOOL,
			'char': types.CHAR,
			'short': types.SHORT,
			'int': types.INT,
			'str': types.STR,
		}.get(name)
		if typ is not None: return typ
		assert len(types.Primitive) == 6, "Exhaustive check of Primitives, (implement next primitive type here)"
		typ,place = expand(self.type_names.get(name))
		if self.semantic:
			self.semantic_tokens.add(SemanticToken(node.place, SemanticTokenType.TYPE,value_type=typ,def_place=place))
		if typ is None:
			self.config.errors.critical_error(ET.TYPE_REFERENCE, node.ref.place, f"type '{name}' is not defined")
		
		fill_types = tuple(self.check(fill_type) for fill_type in node.filler_types)
		if len(fill_types) != 0:
			return self.generic_fill_helper(fill_types,typ,node.access_place)
		return typ
	def check_type_definition(self, node:nodes.TypeDefinition) -> Type:
		typ = self.check(node.typ)
		if self.semantic:
			self.semantic_tokens.add(SemanticToken(node.name.place, SemanticTokenType.TYPE, (SemanticTokenModifier.DEFINITION,)))
		self.type_names[node.name.operand] = typ,node.name.place
		self.validate(typ,ET.INVALID_TYPE_DEF,node.typ.place)
		return types.VOID
	def check_match(self, node:nodes.Match) -> Type:
		value = self.check(node.value)
		returns:list[tuple[Type,Place]] = []
		self.validate(value,ET.INVALID_MATCH,node.value.place)
		if isinstance(value, types.Enum):
			if self.semantic:
				self.semantic_tokens.add(SemanticToken(node.match_as.place, SemanticTokenType.VARIABLE, (SemanticTokenModifier.DECLARATION,)))
			for case in node.cases:
				names_before = self.names.copy()
				_, typ = node.lookup_enum(value, case, self.config)
				self.semantic_tokens.add(SemanticToken(case.name.place, SemanticTokenType.ENUM_ITEM, value_type=typ))
				self.names[node.match_as.operand] = typ,case.name.place
				returns.append((self.check(case.body),case.place))
				self.names = names_before
			if node.default is not None:
				returns.append((self.check(node.default),node.default.place))
		else:
			self.config.errors.add_error(ET.MATCH, node.place, f"matching type '{value}' is not supported")
		if len(returns) == 0:
			return types.VOID
		right_ret,_ = returns[0]
		for ret, place in returns:
			if ret != right_ret:
				self.config.errors.add_error(ET.MATCH_BRANCH, place, f"inconsistent branches: one branch returns, while other does not")
		if node.default is None:
			return types.VOID
		return right_ret
	def check(self, node:Node) -> Type:
		if type(node) == nodes.Assert           : return self.check_assert         (node)
		if type(node) == nodes.Assignment       : return self.check_assignment     (node)
		if type(node) == nodes.BinaryOperation  : return self.check_bin_exp        (node)
		if type(node) == nodes.Call             : return self.check_call           (node)
		if type(node) == nodes.Cast             : return self.check_cast           (node)
		if type(node) == nodes.CharNum          : return self.check_char_num       (node)
		if type(node) == nodes.CharStr          : return self.check_char_str       (node)
		if type(node) == nodes.Code             : return self.check_code           (node)
		if type(node) == nodes.Const            : return self.check_const          (node)
		if type(node) == nodes.Constant         : return self.check_constant       (node)
		if type(node) == nodes.Declaration      : return self.check_declaration    (node)
		if type(node) == nodes.Dot              : return self.check_dot            (node)
		if type(node) == nodes.Enum             : return self.check_enum           (node)
		if type(node) == nodes.ExprStatement    : return self.check_expr_state     (node)
		if type(node) == nodes.FillGeneric      : return self.check_generic_fill   (node)
		if type(node) == nodes.FromImport       : return self.check_from_import    (node)
		if type(node) == nodes.Fun              : return self.check_fun            (node)
		if type(node) == nodes.If               : return self.check_if             (node)
		if type(node) == nodes.Import           : return self.check_import         (node)
		if type(node) == nodes.Int              : return self.check_int            (node)
		if type(node) == nodes.Match            : return self.check_match          (node)
		if type(node) == nodes.Mix              : return self.check_mix            (node)
		if type(node) == nodes.ReferTo          : return self.check_refer          (node)
		if type(node) == nodes.Return           : return self.check_return         (node)
		if type(node) == nodes.Save             : return self.check_save           (node)
		if type(node) == nodes.Set              : return self.check_set            (node)
		if type(node) == nodes.Short            : return self.check_short          (node)
		if type(node) == nodes.Str              : return self.check_str            (node)
		if type(node) == nodes.StrCast          : return self.check_string_cast    (node)
		if type(node) == nodes.Struct           : return self.check_struct         (node)
		if type(node) == nodes.Subscript        : return self.check_subscript      (node)
		if type(node) == nodes.Template         : return self.check_template       (node)
		if type(node) == nodes.TypeArray        : return self.check_type_array     (node)
		if type(node) == nodes.TypeDefinition   : return self.check_type_definition(node)
		if type(node) == nodes.TypeFun          : return self.check_type_fun       (node)
		if type(node) == nodes.TypePointer      : return self.check_type_pointer   (node)
		if type(node) == nodes.TypeReference    : return self.check_type_reference (node)
		if type(node) == nodes.UnaryExpression  : return self.check_unary_exp      (node)
		if type(node) == nodes.Use              : return self.check_use            (node)
		if type(node) == nodes.Var              : return self.check_var            (node)
		if type(node) == nodes.VariableSave     : return self.check_variable_save  (node)
		if type(node) == nodes.While            : return self.check_while          (node)
		assert False, f"Unreachable, unknown {type(node)=}"
