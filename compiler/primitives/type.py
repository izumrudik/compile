from enum import Enum as pythons_enum, auto
from dataclasses import dataclass, field
from .core import Config,Place,ET,GENERIC_RECURSION_DEPTH
__all__ = [
	'Type',
]
class Type:
	def __str__(self) -> str:
		raise TypeError("Method is abstract")
	def __repr__(self) -> str: return str(self)
	@property
	def llvm(self) -> str:
		raise TypeError("Method is abstract")
	@property
	def sized(self) -> bool:
		raise TypeError("Method is abstract")
	def replace(self,generics:tuple['Generic',...],filler:tuple['Type',...]) -> 'Type':
		assert len(generics) == len(filler)
		raise TypeError("Method is abstract")


@dataclass(slots=True, frozen=True, repr=False)
class Generic(Type):
	name:str
	generic_uid:int
	def __str__(self) -> str:
		return self.name
	@property
	def sized(self) -> bool:
		return True
	@property
	def llvm(self) -> str:
		return f"#/;$unreplaced generic {self.name} with uid {self.generic_uid}$;/#"
	def replace(self,generics:tuple['Generic',...],filler:tuple['Type',...]) -> 'Type':
		assert len(generics) == len(filler)
		for idx,i in enumerate(generics):
			if i.generic_uid == self.generic_uid:
				return filler[idx]
		return self

@dataclass(slots=True, frozen=True, repr=False,)
class Generics:
	generics:tuple[Generic,...]
	implicit_generics:tuple[Generic,...]
	generate_values:set[tuple[tuple[Type,...],tuple[Type,...]]] = field(default_factory=set)
	dependent_generics:set[tuple['Generics',tuple[Type,...]]] = field(default_factory=set)
	def fill_generics(self,fill_vals:tuple[Type,...],generic_context:'list[Generics]',fill_what:Type,config:Config,place:Place) -> Type:
		self.add(fill_vals,generic_context,(),(),1,config,place)
		return self.replace(fill_vals,fill_what)
	def add(self,fill_vals:tuple[Type,...],generic_context:'list[Generics]',i:tuple['Generic',...],j:tuple[Type,...],recursion_depth:int,config:Config,place:Place) -> None:
		if recursion_depth>=GENERIC_RECURSION_DEPTH:
			config.errors.add_error(ET.GENERIC_RECURSION,place, f"reached generic recursion limit of {recursion_depth}, while filling generics")
			return
		if len(generic_context) != 0:
			assert len(self.generate_values) == 0, "Assumes linear reference pattern"
			generic_context[-1].dependent_generics.add((self,fill_vals))
			return
		for gen,fill in zip(self.generics,fill_vals): # make sure recursion replaces new values
			try:
				idx = i.index(gen)
			except ValueError:
				i+=gen,
				j+=fill,
			else:
				i = (*i[:idx],gen,*i[idx+1:])
				j = (*j[:idx],fill,*j[idx+1:])
		new_value = (fill_vals,tuple(x.replace(i,j) for x in self.implicit_generics))
		if new_value in self.generate_values:
			return#already been there
		self.generate_values.add(new_value)
		for ref,vals in self.dependent_generics:
			ref.add(tuple(x.replace(i,j) for x in vals),generic_context,i,j,recursion_depth+1,config,place)
	def replace(self,fill_vals:tuple[Type,...],replace_what:Type) -> Type:
		return replace_what.replace(self.generics,fill_vals)
	def replace_llvmid(self,suffix:str,llvmid:str) -> str:
		return f'{llvmid[0]}"{llvmid[1:]}{suffix}"'
	def replace_llvm(self,fill_vals:tuple[Type,...],uid:str) -> str:
		assert len(fill_vals) == len(self.generics)
		if len(fill_vals) == 0:return uid
		return f"{uid}.generics:{', '.join(f'{i.llvm}' for i in fill_vals)}"
	def replace_txt(self,fill_vals:tuple[Type,...],txt:str) -> str:
		return replace_txt(self.generics,fill_vals,txt)
	def __hash__(self) -> int:
		return hash((self.implicit_generics,self.generics))
	def __str__(self) -> str:
		if len(self.generics) == 0:
			return f""
		return f"<{', '.join(map(str,self.generics))}>"
	def __repr__(self) -> str:return str(self)
	@classmethod
	def empty(cls) -> 'Generics':
		return cls((),())
def replace_txt(generics:tuple[Generic,...],fill_vals:tuple[Type,...],txt:str) -> str:
	for generic,fill_value in zip(generics,fill_vals,strict=True):
		txt = txt.replace(generic.llvm,fill_value.llvm)
	return txt
class Primitive(Type,pythons_enum):
	INT   = auto()
	STR   = auto()
	BOOL  = auto()
	VOID  = auto()
	CHAR  = auto()
	SHORT = auto()
	def __str__(self) -> str:
		return self.name.lower()
	@property
	def llvm(self) -> str:
		table:dict[Type, str] = {
			Primitive.VOID : 'void',
			Primitive.INT  : 'i64',
			Primitive.SHORT: 'i32',
			Primitive.CHAR : 'i8',
			Primitive.BOOL : 'i1',
			Primitive.STR  : '%str.type',
		}
		return table[self]
	@property
	def sized(self) -> bool:
		return self != VOID
	def replace(self,generics:tuple['Generic',...],filler:tuple['Type',...]) -> 'Primitive':
		return self

INT   = Primitive.INT
BOOL  = Primitive.BOOL
STR   = Primitive.STR
VOID  = Primitive.VOID
CHAR  = Primitive.CHAR
SHORT = Primitive.SHORT
@dataclass(slots=True, frozen=True, repr=False)
class Ptr(Type):
	pointed:Type
	def __str__(self) -> str:
		return f"*{self.pointed}"
	@property
	def llvm(self) -> str:
		p = self.pointed.llvm
		if p == 'ptr':
			return "ptr"
		if p == 'void':
			return 'i8*'
		return f"{p}*"
	@property
	def sized(self) -> bool:
		return True
	def replace(self,generics:tuple['Generic',...],filler:tuple['Type',...]) -> 'Type':
		return Ptr(self.pointed.replace(generics,filler))
PTR = Ptr(VOID)
@dataclass(repr=False,eq=False)#no slots or frozen to simulate a pointer
class Struct(Type):#modifying is allowed only to create recursive data
	name:str
	variables:tuple[tuple[str,Type],...]
	struct_uid:int
	funs:'tuple[tuple[str,Fun,str],...]'
	generics:Generics
	suffix:str
	generic_filler:tuple[Type,...]
	generic_filled:bool = False
	@property
	def generic_safe(self) -> bool:
		return len(self.generics.generics) == 0 or self.generic_filled
	def make_generic_safe(self) -> None:
		self.generic_filled = True
	def __str__(self) -> str:
		if not self.generic_safe:
			return f"{self.name}"
		return f"{self.name}!<{', '.join(map(str,self.generic_filler))}>"
	def get_magic(self, magic:'str') -> 'tuple[Fun,str]|None':
		for name,fun,llvmid in self.funs:
			if name == f'__{magic}__':
				return fun,llvmid
		return None
	@property
	def llvm(self) -> str:
		return self.generics.replace_llvmid(self.suffix,f"%struct.{self.struct_uid}.{self.name}")
	def is_sized(self) -> bool:
		return all(var.sized for _,var in self.variables)
	_is_sizing:bool = False
	@property
	def sized(self) -> bool:
		if self._is_sizing:
			return False
		self._is_sizing = True
		ret = self.is_sized()
		self._is_sizing = False
		return ret
	def __hash__(self) -> int:
		return hash((
			self.struct_uid,
			self.generic_filler
		))
	def __eq__(self,other:object) -> bool:
		if not isinstance(other,Struct):
			return NotImplemented
		return hash(self) == hash(other)
	_current_obj:'None|Struct' = None
	def replace(self,generics:tuple['Generic',...],filler:tuple['Type',...]) -> 'Struct':
		if self._current_obj is not None:return self._current_obj
		out = Struct('',(),0,(),Generics.empty(),'',())
		self._current_obj = out
		out.__dict__ = self.__dict__.copy() #type: ignore
		out.suffix = replace_txt(generics,filler,out.suffix)
		out.funs = tuple((a,fun.replace(generics,filler),replace_txt(generics,filler,b)) for a,fun,b in out.funs)
		out.variables = tuple((a,b.replace(generics,filler)) for a,b in out.variables)
		out.generic_filler = tuple(a.replace(generics,filler) for a in out.generic_filler)
		self._current_obj = None
		return out

@dataclass(slots=True, frozen=True, repr=False)
class Fun(Type):
	visible_arg_types:tuple[Type, ...]
	return_type:Type
	generics:Generics
	generic_filled:bool = False
	@property
	def generic_safe(self) -> bool:
		return self.generic_filled or len(self.generics.generics) == 0 
	def make_generic_safe(self) -> 'Fun':
		return Fun(self.visible_arg_types,self.return_type,self.generics,generic_filled=True)
	def __str__(self) -> str:
		return f"({', '.join(f'{arg}' for arg in self.visible_arg_types)}){self.generics} -> {self.return_type}"
	@property
	def llvm(self) -> str:
		return f"{{ {self.fun_llvm}, {PTR.llvm} }}"
	@property
	def fun_llvm(self) -> str:
		return f"{self.return_type.llvm} ({', '.join((PTR.llvm,*(arg.llvm for arg in self.visible_arg_types)))})*"
	@property
	def sized(self) -> bool:
		return len(self.generics.generics) == 0
	def replace(self,generics:tuple['Generic',...],filler:tuple['Type',...]) -> 'Fun':
		return Fun(tuple(i.replace(generics,filler) for i in self.visible_arg_types),self.return_type.replace(generics,filler),self.generics,self.generic_filled)

@dataclass(slots=True, frozen=True, repr=False)
class Module(Type):
	module_uid:'int'
	path:'str'
	def __str__(self) -> str:
		return f"#module({self.path})"
	@property
	def llvm(self) -> str:
		assert False, "Module type is not saveable"
	@property
	def sized(self) -> bool:
		return False
	def replace(self,generics:tuple['Generic',...],filler:tuple['Type',...]) -> 'Module':
		return self
@dataclass(slots=True, frozen=True, repr=False)
class Mix(Type):
	funs:tuple[Type, ...]
	name:str
	def __str__(self) -> str:
		return f"#mix({self.name})"
	@property
	def llvm(self) -> str:
		return f"{{{', '.join(i.llvm for i in self.funs)}}}"
	@property
	def sized(self) -> bool:
		return True
	def replace(self,generics:tuple['Generic',...],filler:tuple['Type',...]) -> 'Mix':
		return Mix(tuple(fun.replace(generics,filler) for fun in self.funs),self.name)
@dataclass(slots=True, unsafe_hash=True, repr=False)
class Array(Type):
	typ:Type
	size:int = 0
	def __str__(self) -> str:
		if self.size == 0:
			return f"[]{self.typ}"
		return f"[{self.size}]{self.typ}"
	@property
	def llvm(self) -> str:
		return f"[{self.size} x {self.typ.llvm}]"
	def is_sized(self) -> bool:
		if self.size == 0:
			return False
		return self.typ.sized
	_is_sizing:bool = False
	@property
	def sized(self) -> bool:
		if self._is_sizing:
			return False
		self._is_sizing = True
		ret = self.is_sized()
		self._is_sizing = False
		return ret
	def replace(self,generics:tuple['Generic',...],filler:tuple['Type',...]) -> 'Array':
		return Array(self.typ.replace(generics,filler),self.size)
@dataclass(slots=True, unsafe_hash=True, repr=False)
class StructKind(Type):
	struct:'Struct'
	@property
	def generic_safe(self) -> bool:
		return self.struct.generic_safe
	def make_generic_safe(self) -> None:
		self.struct.make_generic_safe()
	@property
	def name(self) -> str:
		return self.struct.name
	@property
	def struct_uid(self) -> int:
		return self.struct.struct_uid
	def __str__(self) -> str:
		return f"#structkind({self.name})"
	@property
	def llvm(self) -> str:
		assert False, f"struct kind is not saveable"
	def is_sized(self) -> bool:
		return False
	@property
	def sized(self) -> bool:
		return False
	def replace(self,generics:tuple['Generic',...],filler:tuple['Type',...]) -> 'StructKind':
		return StructKind(self.struct.replace(generics,filler))
@dataclass(repr=False)#no slots or frozen to simulate a pointer
class Enum(Type):#modifying is allowed only to create recursive data
	name:str
	items:tuple[str,...]
	typed_items:tuple[tuple[str,Type],...]
	funs:'tuple[tuple[str,Fun,str],...]'
	enum_uid:int
	def get_magic(self, magic:'str') -> 'tuple[Fun,str]|None':
		for name,fun,llvmid in self.funs:
			if name == f'__{magic}__':
				return fun,llvmid
		return None
	@property
	def llvm(self) -> str:
		return f"%enum.{self.enum_uid}.{self.name}"
	@property
	def llvm_max_item(self) -> str:
		return f"%enum.max_item.{self.enum_uid}.{self.name}"
	@property
	def llvm_item_id(self) -> str:
		return f"%enum.item_id.{self.enum_uid}.{self.name}"
	def __str__(self) -> str:
		return self.name
	def is_sized(self) -> bool:
		return all(var.sized for _,var in self.typed_items)
	_is_sizing:bool = False
	@property
	def sized(self) -> bool:
		if self._is_sizing:
			return False
		self._is_sizing = True
		ret = self.is_sized()
		self._is_sizing = False
		return ret
	def __hash__(self) -> int:
		return hash((
			self.enum_uid,
			self.name,
			self.items,
		))
	_current_obj:'None|Enum' = None
	def replace(self,generics:tuple['Generic',...],filler:tuple['Type',...]) -> 'Enum':
		if self._current_obj is not None:return self._current_obj
		out = Enum('',(),(),(),0)
		self._current_obj = out
		out.__dict__ = self.__dict__.copy() #type: ignore
		out.funs = tuple((a,fun.replace(generics,filler),b) for a,fun,b in out.funs)
		out.typed_items = tuple((a,b.replace(generics,filler)) for a,b in out.typed_items)
		self._current_obj = None
		return out
@dataclass(slots=True, frozen=True, repr=False)
class EnumKind(Type):
	enum:'Enum'
	@property
	def name(self) -> str:
		return self.enum.name
	@property
	def enum_uid(self) -> int:
		return self.enum.enum_uid
	def __str__(self) -> str:
		return f"#enum_kind({self.name})"
	@property
	def llvm(self) -> str:
		assert False, f"enum kind is not saveable"
	def llvmid_of_type_function(self, idx:int) -> str:
		return f"@__enum.{self.enum_uid}.{self.name}.fun_to_create_enum_no.{idx}.{self.enum.typed_items[idx][0]}"
	@property
	def sized(self) -> bool:
		return False
	def replace(self,generics:tuple['Generic',...],filler:tuple['Type',...]) -> 'EnumKind':
		return EnumKind(self.enum.replace(generics,filler))
