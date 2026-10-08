#!/usr/bin/env python3
"""Compile using native libxkbcommon and prove only the two keys change."""
import ctypes as c
import json
from pathlib import Path
import sys

class Names(c.Structure):
    _fields_ = [(key, c.c_char_p) for key in ('rules','model','layout','variant','options')]


def validate(root):
    lib = c.CDLL('libxkbcommon.so.0')
    declarations = {
        'xkb_context_new': ([c.c_int], c.c_void_p),
        'xkb_context_include_path_append': ([c.c_void_p,c.c_char_p], c.c_int),
        'xkb_keymap_new_from_names': ([c.c_void_p,c.POINTER(Names),c.c_int], c.c_void_p),
        'xkb_keymap_key_get_name': ([c.c_void_p,c.c_uint], c.c_char_p),
        'xkb_keymap_min_keycode': ([c.c_void_p], c.c_uint),
        'xkb_keymap_max_keycode': ([c.c_void_p], c.c_uint),
        'xkb_keymap_num_layouts_for_key': ([c.c_void_p,c.c_uint], c.c_uint),
        'xkb_keymap_num_levels_for_key': ([c.c_void_p,c.c_uint,c.c_uint], c.c_uint),
        'xkb_keymap_key_get_syms_by_level': ([c.c_void_p,c.c_uint,c.c_uint,c.c_uint,c.POINTER(c.POINTER(c.c_uint))], c.c_int),
        'xkb_keysym_get_name': ([c.c_uint,c.c_char_p,c.c_size_t], c.c_int),
        'xkb_keymap_unref': ([c.c_void_p], None),
        'xkb_context_unref': ([c.c_void_p], None),
    }
    for name,(args,result) in declarations.items():
        fn=getattr(lib,name);fn.argtypes=args;fn.restype=result
    ctx=lib.xkb_context_new(1)  # Explicit isolated validation include paths.
    maps=[]
    try:
        for path in (root,Path('/usr/share/X11/xkb')):
            if not lib.xkb_context_include_path_append(ctx,str(path).encode()):
                raise ValueError('XKB include path rejected')
        for option in (b'',b'gts9:swap_escape_grave'):
            keymap=lib.xkb_keymap_new_from_names(ctx,c.byref(Names(b'evdev',b'pc105',b'us',None,option)),0)
            if not keymap:raise ValueError('XKB compilation failed')
            maps.append(keymap)
        def values(keymap,code):
            result=[]
            for group in range(lib.xkb_keymap_num_layouts_for_key(keymap,code)):
                levels=[]
                for level in range(lib.xkb_keymap_num_levels_for_key(keymap,code,group)):
                    pointer=c.POINTER(c.c_uint)()
                    count=lib.xkb_keymap_key_get_syms_by_level(keymap,code,group,level,c.byref(pointer))
                    names=[]
                    for i in range(count):
                        buf=c.create_string_buffer(128);lib.xkb_keysym_get_name(pointer[i],buf,128);names.append(buf.value.decode())
                    levels.append(names)
                result.append(levels)
            return result
        differences={}
        for code in range(lib.xkb_keymap_min_keycode(maps[0]),lib.xkb_keymap_max_keycode(maps[0])+1):
            before,after=values(maps[0],code),values(maps[1],code)
            if before!=after:
                name=lib.xkb_keymap_key_get_name(maps[0],code).decode();differences[name]={'before':before,'after':after}
        if set(differences)!={'ESC','TLDE'} or differences['ESC']['after']!=[[['grave'],['asciitilde']]] or differences['TLDE']['after']!=[[['Escape']]]:
            raise ValueError('unexpected symbol changes: '+repr(differences))
        return {'verdict':'PASS','only_changed_keys':differences,'layout':'us','option':'gts9:swap_escape_grave'}
    finally:
        for keymap in maps:lib.xkb_keymap_unref(keymap)
        lib.xkb_context_unref(ctx)

if __name__=='__main__':
    print(json.dumps(validate(Path(sys.argv[1])),indent=2))
