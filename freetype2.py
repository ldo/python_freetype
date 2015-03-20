"""A Python 3 wrapper for FreeType <http://www.freetype.org/> using
ctypes. This is not a complete wrapper for all FreeType
functionality, but it should be comprehensive enough to be
useful. Functionality that is (mostly) covered (as per topics at
<http://www.freetype.org/freetype2/docs/reference/ft2-toc.html>):

    * base interface
    * glyph management
    * computations
    * outline processing
    * quick retrieval of advance values
    * bitmap handling
    * scanline converter
    * glyph stroker

in addition to which, a convenience function is supplied to use
Fontconfig to find matching fonts, and functions are available to
interface to Pycairo, if installed:

    * convert a Bitmap to an ImageSurface (requires that your Pycairo
      support ImageSurface.create_for_data)
    * draw the contours of an Outline as a Path
"""
#+
# Copyright 2015 Lawrence D'Oliveiro <ldo@geek-central.gen.nz>.
# Dual-licensed under the FreeType licence
# <http://git.savannah.gnu.org/cgit/freetype/freetype2.git/tree/docs/FTL.TXT>
# and GPLv2 <http://git.savannah.gnu.org/cgit/freetype/freetype2.git/tree/docs/GPLv2.TXT>
# or later, to be compatible with FreeType itself.
#-

import math
from numbers import \
    Number
import array
import ctypes as ct
import struct
import weakref
try :
    import cairo
except ImportError :
    cairo = None
#end try

ft = ct.cdll.LoadLibrary("libfreetype.so.6")
try :
    fc = ct.cdll.LoadLibrary("libfontconfig.so.1")
except OSError as fail :
    if True : # if fail.errno == 2 : # ENOENT
      # no point checking, because it is None! (Bug?)
        fc = None
    else :
        raise
    #end if
#end try
libc = ct.cdll.LoadLibrary("libc.so.6")

def struct_to_dict(item, itemtype, indirect, extra_decode = None) :
    "decodes the elements of a ctypes Structure into a dict. extra_decode" \
    " optionally specifies special conversions for particular fields."
    if indirect :
        item = item.contents
    #end if
    result = {}
    for k in itemtype._fields_ :
        k = k[0]
        field = getattr(item, k)
        if extra_decode != None :
            decode = extra_decode.get(k)
            if decode == None :
                decode = extra_decode.get(None)
            #end if
            if decode != None :
                field = decode(field)
            #end if
        #end if
        result[k] = field
    #end for
    return \
        result
#end struct_to_dict

class FT :
    "useful definitions adapted from freetype.h. You will need to use the constants," \
    " but apart from that, see the more Pythonic wrappers defined outside this" \
    " class in preference to accessing low-level structures directly."

    # General ctypes gotcha: when passing addresses of ctypes-constructed objects
    # to routine calls, do not construct the objects directly in the call. Otherwise
    # the refcount goes to 0 before the routine is actually entered, and the object
    # can get prematurely disposed. Always store the object reference into a local
    # variable, and pass the value of the variable instead.

    Error = ct.c_int # hopefully this is always correct

    class LibraryRec(ct.Structure) :
        pass # private
    #end LibraryRec
    Library = ct.POINTER(LibraryRec)

    Encoding = ct.c_uint

    def ENC_TAG(tag) :
        """converts tag, which must be a four-byte string, into an integer suitable
        as an Encoding value."""
        return struct.unpack(">I", tag.encode("ascii"))[0]
    #end ENC_TAG

    ENCODING_NONE = ENC_TAG('\x00\x00\x00\x00')

    ENCODING_MS_SYMBOL = ENC_TAG('symb')
    ENCODING_UNICODE = ENC_TAG('unic')

    ENCODING_SJIS = ENC_TAG('sjis')
    ENCODING_GB2312 = ENC_TAG('gb  ')
    ENCODING_BIG5 = ENC_TAG('big5')
    ENCODING_WANSUNG = ENC_TAG('wans')
    ENCODING_JOHAB = ENC_TAG('joha')

    # for backwards compatibility
    ENCODING_MS_SJIS = ENCODING_SJIS
    ENCODING_MS_GB2312 = ENCODING_GB2312
    ENCODING_MS_BIG5 = ENCODING_BIG5
    ENCODING_MS_WANSUNG = ENCODING_WANSUNG
    ENCODING_MS_JOHAB = ENCODING_JOHAB

    ENCODING_ADOBE_STANDARD = ENC_TAG('ADOB')
    ENCODING_ADOBE_EXPERT = ENC_TAG('ADBE')
    ENCODING_ADOBE_CUSTOM = ENC_TAG('ADBC')
    ENCODING_ADOBE_LATIN_1 = ENC_TAG('lat1')

    ENCODING_OLD_LATIN_2 = ENC_TAG('lat2')

    ENCODING_APPLE_ROMAN = ENC_TAG('armn')

    Glyph_Format = ct.c_uint

    def IMAGE_TAG(tag) :
        """converts tag, which must be a four-byte string, into an integer suitable
        as a Glyph_Format value."""
        return struct.unpack(">I", tag.encode("ascii"))[0]
    #end IMAGE_TAG

    GLYPH_FORMAT_NONE = IMAGE_TAG('\x00\x00\x00\x00')

    GLYPH_FORMAT_COMPOSITE = IMAGE_TAG('comp')
    GLYPH_FORMAT_BITMAP = IMAGE_TAG('bits')
    GLYPH_FORMAT_OUTLINE = IMAGE_TAG('outl')
    GLYPH_FORMAT_PLOTTER = IMAGE_TAG('plot')

    Pos = ct.c_long # might be integer, or 16.16 fixed, or 26.6 fixed
    Fixed = ct.c_ulong # 16.16 fixed-point

    class Vector(ct.Structure) :
        pass
    Vector._fields_ = \
            [
                ("x", Pos),
                ("y", Pos),
            ]
    #end Vector

    class Generic(ct.Structure) :
        Finalizer = ct.CFUNCTYPE(None, ct.c_void_p)
        _fields_ = \
            [
                ("data", ct.c_void_p),
                ("finalizer", Finalizer),
            ]
    #end Generic

    class BBox(ct.Structure) :
        pass
    BBox._fields_ = \
            [
                ("xMin", Pos),
                ("yMin", Pos),
                ("xMax", Pos),
                ("yMax", Pos),
            ]
    #end BBox

    class Bitmap_Size(ct.Structure) :
        pass
    Bitmap_Size._fields_ = \
            [
                ("height", ct.c_short),
                ("width", ct.c_short),

                ("size", Pos),

                ("x_ppem", Pos),
                ("y_ppem", Pos),
            ]
    #end Bitmap_Size

    class Size_Metrics(ct.Structure) :
        pass
    Size_Metrics._fields_ = \
            [
                ("x_ppem", ct.c_ushort), # horizontal pixels per EM
                ("y_ppem", ct.c_ushort), # vertical pixels per EM

                ("x_scale", Fixed), # scaling values used to convert font
                ("y_scale", Fixed), # units to 26.6 fractional pixels

                ("ascender", Pos), # ascender in 26.6 frac. pixels
                ("descender", Pos), # descender in 26.6 frac. pixels
                ("height", Pos), # text height in 26.6 frac. pixels
                ("max_advance", Pos), # max horizontal advance, in 26.6 pixels
            ]
    #end Size_Metrics

    class Glyph_Metrics(ct.Structure) :
        pass
    Glyph_Metrics._fields_ = \
            [
                ("width", Pos),
                ("height", Pos),

                ("horiBearingX", Pos),
                ("horiBearingY", Pos),
                ("horiAdvance", Pos),

                ("vertBearingX", Pos),
                ("vertBearingY", Pos),
                ("vertAdvance", Pos),
            ]
    #end Glyph_Metrics

    class FaceRec(ct.Structure) :
        "initial public part of an FT_Face"
        pass # forward
    #end FaceRec
    Face = ct.POINTER(FaceRec)

    class CharMapRec(ct.Structure) :
        pass
    CharMapRec._fields_ = \
            [
                ("face", Face),
                ("encoding", Encoding),
                ("platform_id", ct.c_ushort),
                ("encoding_id", ct.c_ushort),
            ]
    #end CharMapRec
    CharMap = ct.POINTER(CharMapRec)

    # CharMapRec.platform_id codes
    # from <https://developer.apple.com/fonts/TrueType-Reference-Manual/RM06/Chap6cmap.html>
    PLATFORM_UNICODE = 0
    PLATFORM_MACINTOSH = 1
    PLATFORM_MICROSOFT = 3
    PLATFORM_ADOBE = 7 # guess
    # CharMapRec.encoding_id values for PLATFORM_UNICODE
    ENCODING_UNICODE_DEFAULT = 0
    ENCODING_UNICODE_11 = 1 # Unicode 1.1
    ENCODING_UNICODE_ISO10646_1993 = 2
    ENCODING_UNICODE_20_BMP = 3 # Unicode 2.0+, BMP only
    ENCODING_UNICODE_20_BMP_PLUS = 4 # Unicode 2.0+, BMP and beyond
    ENCODING_UNICODE_VARSEQ = 5 # Unicode Variation Sequences
    ENCODING_UNICODE_FULL = 6 # full Unicode coverage

    class SizeRec(ct.Structure) :
        Size_Internal = ct.c_void_p
    SizeRec._fields_ = \
            [
                ("face", Face), # parent face object
                ("generic", Generic), # generic pointer for client uses
                ("metrics", Size_Metrics), # size metrics
                ("internal", SizeRec.Size_Internal),
            ]
    #end SizeRec
    Size = ct.POINTER(SizeRec)

    # values for Outline.flags
    OUTLINE_NONE = 0x0
    OUTLINE_OWNER = 0x1
    OUTLINE_EVEN_ODD_FILL = 0x2
    OUTLINE_REVERSE_FILL = 0x4
    OUTLINE_IGNORE_DROPOUTS = 0x8
    OUTLINE_SMART_DROPOUTS = 0x10
    OUTLINE_INCLUDE_STUBS = 0x20

    OUTLINE_HIGH_PRECISION = 0x100
    OUTLINE_SINGLE_PASS = 0x200

    class Outline(ct.Structure) :
        pass
    Outline._fields_ = \
            [
                ("n_contours", ct.c_short), # number of contours in glyph
                ("n_points", ct.c_short), # number of points in the glyph

                ("points", ct.POINTER(Vector)), # the outline's points
                ("tags", ct.POINTER(ct.c_ubyte)), # the points flags
                ("contours", ct.POINTER(ct.c_short)), # the contour end points

                ("flags", ct.c_uint), # outline masks
            ]
    #end Outline

    Pixel_Mode = ct.c_uint
    # values for Pixel_Mode
    PIXEL_MODE_NONE = 0
    PIXEL_MODE_MONO = 1
    PIXEL_MODE_GRAY = 2
    PIXEL_MODE_GRAY2 = 3
    PIXEL_MODE_GRAY4 = 4
    PIXEL_MODE_LCD = 5
    PIXEL_MODE_LCD_V = 6

    class Bitmap(ct.Structure) :
        _fields_ = \
            [
                ("rows", ct.c_int),
                ("width", ct.c_int),
                ("pitch", ct.c_int),
                ("buffer", ct.c_void_p),
                ("num_grays", ct.c_short),
                ("pixel_mode", ct.c_byte),
                ("palette_mode", ct.c_byte),
                ("palette", ct.c_void_p),
            ]
    #end Bitmap
    BitmapPtr = ct.POINTER(Bitmap)

    class GlyphSlotRec(ct.Structure) :
        Slot_Internal = ct.c_void_p
        SubGlyph = ct.c_void_p
        pass # forward
    GlyphSlot = ct.POINTER(GlyphSlotRec)
    GlyphSlotRec._fields_ = \
            [
                ("library", Library),
                ("face", Face),
                ("next", GlyphSlot),
                ("reserved", ct.c_uint), # retained for binary compatibility
                ("generic", Generic),

                ("metrics", Glyph_Metrics),
                ("linearHoriAdvance", Fixed),
                ("linearVertAdvance", Fixed),
                ("advance", Vector),

                ("format", Glyph_Format),

                ("bitmap", Bitmap),
                ("bitmap_left", ct.c_int),
                ("bitmap_top", ct.c_int),

                ("outline", Outline),

                ("num_subglyphs", ct.c_uint),
                ("subglyphs", GlyphSlotRec.SubGlyph),

                ("control_data", ct.c_void_p),
                ("control_len", ct.c_long),

                ("lsb_delta", Pos),
                ("rsb_delta", Pos),

                ("other", ct.c_void_p),

                ("internal", GlyphSlotRec.Slot_Internal),
            ]
    #end GlyphSlotRec

    FACE_FLAG_SCALABLE = ( 1 <<  0 )
    FACE_FLAG_FIXED_SIZES = ( 1 <<  1 )
    FACE_FLAG_FIXED_WIDTH = ( 1 <<  2 )
    FACE_FLAG_SFNT = ( 1 <<  3 )
    FACE_FLAG_HORIZONTAL = ( 1 <<  4 )
    FACE_FLAG_VERTICAL = ( 1 <<  5 )
    FACE_FLAG_KERNING = ( 1 <<  6 )
    FACE_FLAG_FAST_GLYPHS = ( 1 <<  7 )
    FACE_FLAG_MULTIPLE_MASTERS = ( 1 <<  8 )
    FACE_FLAG_GLYPH_NAMES = ( 1 <<  9 )
    FACE_FLAG_EXTERNAL_STREAM = ( 1 << 10 )
    FACE_FLAG_HINTER = ( 1 << 11 )
    FACE_FLAG_CID_KEYED = ( 1 << 12 )
    FACE_FLAG_TRICKY = ( 1 << 13 )
    FACE_FLAG_COLOR = ( 1 << 14 )

    STYLE_FLAG_ITALIC = ( 1 << 0 )
    STYLE_FLAG_BOLD = ( 1 << 1 )

    KERNING_DEFAULT = 0 # scaled and grid-fitted
    KERNING_UNFITTED = 1 # scaled but not grid-fitted
    KERNING_UNSCALED = 2 # return value in original font units

    #class FaceRec(ct.Structure) :
    #   "initial public part of an FT_Face"
    FaceRec._fields_ = \
            [
                ("num_faces", ct.c_long),
                ("face_index", ct.c_long),

                ("face_flags", ct.c_ulong),
                ("style_flags", ct.c_ulong),

                ("num_glyphs", ct.c_long),

                ("family_name", ct.c_char_p),
                ("style_name", ct.c_char_p),

                ("num_fixed_sizes", ct.c_long),
                ("available_sizes", ct.POINTER(Bitmap_Size)),

                ("num_charmaps", ct.c_long),
                ("charmaps", ct.POINTER(CharMap)),

                ("generic", Generic),

                # The following member variables (down to `underline_thickness')
                # are only relevant to scalable outlines; cf. @FT_Bitmap_Size
                # for bitmap fonts.
                ("bbox", BBox),

                ("units_per_EM", ct.c_ushort),
                ("ascender", ct.c_short),
                ("descender", ct.c_short),
                ("height", ct.c_short),

                ("max_advance_width", ct.c_short),
                ("max_advance_height", ct.c_short),

                ("underline_position", ct.c_short),
                ("underline_thickness", ct.c_short),

                ("glyph", GlyphSlot),
                ("size", Size),
                ("charmap", CharMap),
              # additional private fields follow
            ]
    #end FaceRec

    Size_Request_Type = ct.c_uint
    # values for Size_Request_Type
    SIZE_REQUEST_TYPE_NOMINAL = 0
    SIZE_REQUEST_TYPE_REAL_DIM = 1
    SIZE_REQUEST_TYPE_BBOX = 2
    SIZE_REQUEST_TYPE_CELL = 3
    SIZE_REQUEST_TYPE_SCALES = 4
    SIZE_REQUEST_TYPE_MAX = 5

    class Size_RequestRec(ct.Structure) :
        pass
    Size_RequestRec._fields_ = \
            [
                ("type", Size_Request_Type),
                ("width", ct.c_long),
                ("height", ct.c_long),
                ("horiResolution", ct.c_uint), # actually 26.6, it appears
                ("vertResolution", ct.c_uint), # actually 26.6, it appears
            ]
    #end Size_RequestRec
    Size_Request = ct.POINTER(Size_RequestRec)

    LOAD_DEFAULT = 0x0
    LOAD_NO_SCALE = ( 1 << 0 )
    LOAD_NO_HINTING = ( 1 << 1 )
    LOAD_RENDER = ( 1 << 2 )
    LOAD_NO_BITMAP = ( 1 << 3 )
    LOAD_VERTICAL_LAYOUT = ( 1 << 4 )
    LOAD_FORCE_AUTOHINT = ( 1 << 5 )
    LOAD_CROP_BITMAP = ( 1 << 6 )
    LOAD_PEDANTIC = ( 1 << 7 )
    LOAD_IGNORE_GLOBAL_ADVANCE_WIDTH = ( 1 << 9 )
    LOAD_NO_RECURSE = ( 1 << 10 )
    LOAD_IGNORE_TRANSFORM = ( 1 << 11 )
    LOAD_MONOCHROME = ( 1 << 12 )
    LOAD_LINEAR_DESIGN = ( 1 << 13 )
    LOAD_NO_AUTOHINT = ( 1 << 15 )
      # Bits 16..19 are used by `FT_LOAD_TARGET_'
    LOAD_COLOR = ( 1 << 20 )

    # extra load flag for FT_Get_Advance and FT_Get_Advances functions
    ADVANCE_FLAG_FAST_ONLY = 0x20000000

    SUBGLYPH_FLAG_ARGS_ARE_WORDS = 1
    SUBGLYPH_FLAG_ARGS_ARE_XY_VALUES = 2
    SUBGLYPH_FLAG_ROUND_XY_TO_GRID = 4
    SUBGLYPH_FLAG_SCALE = 8
    SUBGLYPH_FLAG_XY_SCALE = 0x40
    SUBGLYPH_FLAG_2X2 = 0x80
    SUBGLYPH_FLAG_USE_MY_METRICS = 0x200

    # FSType flags
    FSTYPE_INSTALLABLE_EMBEDDING = 0x0000
    FSTYPE_RESTRICTED_LICENSE_EMBEDDING = 0x0002
    FSTYPE_PREVIEW_AND_PRINT_EMBEDDING = 0x0004
    FSTYPE_EDITABLE_EMBEDDING = 0x0008
    FSTYPE_NO_SUBSETTING = 0x0100
    FSTYPE_BITMAP_EMBEDDING_ONLY = 0x0200

    Render_Mode = ct.c_uint
    # values for Render_Mode
    RENDER_MODE_NORMAL = 0
    RENDER_MODE_LIGHT = 1
    RENDER_MODE_MONO = 2
    RENDER_MODE_LCD = 3
    RENDER_MODE_LCD_V = 4
    RENDER_MODE_MAX = 5

    class Matrix(ct.Structure) :
        pass
    Matrix._fields_ = \
        [
            ("xx", Fixed),
            ("xy", Fixed),
            ("yx", Fixed),
            ("yy", Fixed),
        ]
    #end Matrix

    Glyph_BBox_Mode = ct.c_uint
    # values for Glyph_BBox_Mode
    GLYPH_BBOX_UNSCALED = 0
    GLYPH_BBOX_SUBPIXELS = 0
    GLYPH_BBOX_GRIDFIT = 1
    GLYPH_BBOX_TRUNCATE = 2
    GLYPH_BBOX_PIXELS = 3

    class GlyphRec(ct.Structure) :
        pass
    GlyphRec._fields_ = \
        [
            ("library", Library),
            ("clazz", ct.c_void_p), # const FT_Glyph_Class*
            ("format", Glyph_Format),
            ("advance", Vector),
        ]
    #end GlyphRec
    Glyph = ct.POINTER(GlyphRec)

    class BitmapGlyphRec(ct.Structure) :
        pass
    BitmapGlyphRec._fields_ = \
        [
            ("root", GlyphRec),
            ("left", ct.c_int),
            ("top", ct.c_int),
            ("bitmap", Bitmap),
        ]
    #end BitmapGlyphRec
    BitmapGlyph = ct.POINTER(BitmapGlyphRec)

    class OutlineGlyphRec(ct.Structure) :
        pass
    OutlineGlyphRec._fields_ = \
        [
            ("root", GlyphRec),
            ("outline", Outline),
        ]
    #end OutlineGlyphRec
    OutlineGlyph = ct.POINTER(OutlineGlyphRec)

    Outline_MoveToFunc = ct.CFUNCTYPE(ct.c_int, ct.POINTER(Vector), ct.c_void_p)
    Outline_LineToFunc = ct.CFUNCTYPE(ct.c_int, ct.POINTER(Vector), ct.c_void_p)
    Outline_ConicToFunc = ct.CFUNCTYPE(ct.c_int, ct.POINTER(Vector), ct.POINTER(Vector), ct.c_void_p)
    Outline_CubicToFunc = ct.CFUNCTYPE(ct.c_int, ct.POINTER(Vector), ct.POINTER(Vector), ct.POINTER(Vector), ct.c_void_p)

    class Outline_Funcs(ct.Structure) :
        pass
    Outline_Funcs._fields_ = \
        [
            ("move_to", Outline_MoveToFunc),
            ("line_to", Outline_LineToFunc),
            ("conic_to", Outline_ConicToFunc),
            ("cubic_to", Outline_CubicToFunc),
            ("shift", ct.c_int),
            ("delta", Pos),
        ]
    #end Outline_Funcs

    Orientation = ct.c_uint
    ORIENTATION_TRUETYPE = 0
    ORIENTATION_POSTSCRIPT = 1
    ORIENTATION_FILL_RIGHT = ORIENTATION_TRUETYPE
    ORIENTATION_FILL_LEFT = ORIENTATION_POSTSCRIPT
    ORIENTATION_NONE = 2

    Stroker_LineJoin = ct.c_uint
    STROKER_LINEJOIN_ROUND = 0
    STROKER_LINEJOIN_BEVEL = 1
    STROKER_LINEJOIN_MITER_VARIABLE = 2
    STROKER_LINEJOIN_MITER = STROKER_LINEJOIN_MITER_VARIABLE
    STROKER_LINEJOIN_MITER_FIXED = 3

    Stroker_LineCap = ct.c_uint
    STROKER_LINECAP_BUTT = 0
    STROKER_LINECAP_ROUND = 1
    STROKER_LINECAP_SQUARE = 2

    StrokerBorder = ct.c_uint
    STROKER_BORDER_LEFT = 0
    STROKER_BORDER_RIGHT = 1

    class RasterRec(ct.Structure) :
        pass # private
    #end RasterRec
    Raster = ct.POINTER(RasterRec)

    class Span(ct.Structure) :
        _fields_ = \
            [
                ("x", ct.c_short),
                ("len", ct.c_ushort),
                ("coverage", ct.c_ubyte),
            ]
    #end Span
    SpanPtr = ct.POINTER(Span)

    SpanFunc = ct.CFUNCTYPE(None, ct.c_int, ct.c_int, SpanPtr, ct.c_void_p)

    Raster_BitTest_Func = ct.CFUNCTYPE(ct.c_int, ct.c_int, ct.c_int, ct.c_void_p)
    Raster_BitSet_Func = ct.CFUNCTYPE(None, ct.c_int, ct.c_int, ct.c_void_p)

    class Raster_Params(ct.Structure) :
        pass
    #end Raster_Params
    Raster_Params._fields_ = \
        [
            ("target", BitmapPtr),
            ("source", ct.c_void_p),
            ("flags", ct.c_int),
            ("gray_spans", SpanFunc),
            ("black_spans", SpanFunc), # unused
            ("bit_test", Raster_BitTest_Func), # unused
            ("bit_set", Raster_BitSet_Func), # unused
            ("user", ct.c_void_p),
            ("clip_box", BBox),
        ]
    Raster_ParamsPtr = ct.POINTER(Raster_Params)

    # bit masks for Raster_Params.flags
    RASTER_FLAG_DEFAULT = 0x0
    RASTER_FLAG_AA = 0x1
    RASTER_FLAG_DIRECT = 0x2
    RASTER_FLAG_CLIP = 0x4

    Raster_NewFunc = ct.CFUNCTYPE(ct.c_int, ct.c_void_p, Raster)
    Raster_DoneFunc = ct.CFUNCTYPE(None, Raster)
    Raster_ResetFunc = ct.CFUNCTYPE(None, Raster, ct.POINTER(ct.c_ubyte), ct.c_ulong)
    Raster_SetModeFunc = ct.CFUNCTYPE(ct.c_int, Raster, ct.c_ulong, ct.c_void_p)
    Raster_RenderFunc = ct.CFUNCTYPE(ct.c_int, Raster, Raster_ParamsPtr)

    class Raster_Funcs(ct.Structure) :
        pass
    #end Raster_Funcs
    Raster_Funcs._fields_ = \
        [
            ("glyph_format", Glyph_Format),
            ("raster_new", Raster_NewFunc),
            ("raster_reset", Raster_ResetFunc),
            ("raster_set_mode", Raster_SetModeFunc),
            ("raster_render", Raster_RenderFunc),
            ("raster_done", Raster_DoneFunc),
        ]

#end FT

class Error :
    "names for error codes and corresponding message strings."
    # automatically generated by util/gen_errors.c. Do not hand-edit
    # this class; instead, re-run that and replace this with its output.

    # Error codes:
    Ok = 0
    Cannot_Open_Resource = 1
    Unknown_File_Format = 2
    Invalid_File_Format = 3
    Invalid_Version = 4
    Lower_Module_Version = 5
    Invalid_Argument = 6
    Unimplemented_Feature = 7
    Invalid_Table = 8
    Invalid_Offset = 9
    Array_Too_Large = 10
    Missing_Module = 11
    Missing_Property = 12
    Invalid_Glyph_Index = 16
    Invalid_Character_Code = 17
    Invalid_Glyph_Format = 18
    Cannot_Render_Glyph = 19
    Invalid_Outline = 20
    Invalid_Composite = 21
    Too_Many_Hints = 22
    Invalid_Pixel_Size = 23
    Invalid_Handle = 32
    Invalid_Library_Handle = 33
    Invalid_Driver_Handle = 34
    Invalid_Face_Handle = 35
    Invalid_Size_Handle = 36
    Invalid_Slot_Handle = 37
    Invalid_CharMap_Handle = 38
    Invalid_Cache_Handle = 39
    Invalid_Stream_Handle = 40
    Too_Many_Drivers = 48
    Too_Many_Extensions = 49
    Out_Of_Memory = 64
    Unlisted_Object = 65
    Cannot_Open_Stream = 81
    Invalid_Stream_Seek = 82
    Invalid_Stream_Skip = 83
    Invalid_Stream_Read = 84
    Invalid_Stream_Operation = 85
    Invalid_Frame_Operation = 86
    Nested_Frame_Access = 87
    Invalid_Frame_Read = 88
    Raster_Uninitialized = 96
    Raster_Corrupted = 97
    Raster_Overflow = 98
    Raster_Negative_Height = 99
    Too_Many_Caches = 112
    Invalid_Opcode = 128
    Too_Few_Arguments = 129
    Stack_Overflow = 130
    Code_Overflow = 131
    Bad_Argument = 132
    Divide_By_Zero = 133
    Invalid_Reference = 134
    Debug_OpCode = 135
    ENDF_In_Exec_Stream = 136
    Nested_DEFS = 137
    Invalid_CodeRange = 138
    Execution_Too_Long = 139
    Too_Many_Function_Defs = 140
    Too_Many_Instruction_Defs = 141
    Table_Missing = 142
    Horiz_Header_Missing = 143
    Locations_Missing = 144
    Name_Table_Missing = 145
    CMap_Table_Missing = 146
    Hmtx_Table_Missing = 147
    Post_Table_Missing = 148
    Invalid_Horiz_Metrics = 149
    Invalid_CharMap_Format = 150
    Invalid_PPem = 151
    Invalid_Vert_Metrics = 152
    Could_Not_Find_Context = 153
    Invalid_Post_Table_Format = 154
    Invalid_Post_Table = 155
    Syntax_Error = 160
    Stack_Underflow = 161
    Ignore = 162
    No_Unicode_Glyph_Name = 163
    Glyph_Too_Big = 164
    Missing_Startfont_Field = 176
    Missing_Font_Field = 177
    Missing_Size_Field = 178
    Missing_Fontboundingbox_Field = 179
    Missing_Chars_Field = 180
    Missing_Startchar_Field = 181
    Missing_Encoding_Field = 182
    Missing_Bbx_Field = 183
    Bbx_Too_Big = 184
    Corrupted_Font_Header = 185
    Corrupted_Font_Glyphs = 186

    # Mapping from codes to message strings:
    Message = \
        {
            0 : "no error",
            1 : "cannot open resource",
            2 : "unknown file format",
            3 : "broken file",
            4 : "invalid FreeType version",
            5 : "module version is too low",
            6 : "invalid argument",
            7 : "unimplemented feature",
            8 : "broken table",
            9 : "broken offset within table",
            10 : "array allocation size too large",
            11 : "missing module",
            12 : "missing property",
            16 : "invalid glyph index",
            17 : "invalid character code",
            18 : "unsupported glyph image format",
            19 : "cannot render this glyph format",
            20 : "invalid outline",
            21 : "invalid composite glyph",
            22 : "too many hints",
            23 : "invalid pixel size",
            32 : "invalid object handle",
            33 : "invalid library handle",
            34 : "invalid module handle",
            35 : "invalid face handle",
            36 : "invalid size handle",
            37 : "invalid glyph slot handle",
            38 : "invalid charmap handle",
            39 : "invalid cache manager handle",
            40 : "invalid stream handle",
            48 : "too many modules",
            49 : "too many extensions",
            64 : "out of memory",
            65 : "unlisted object",
            81 : "cannot open stream",
            82 : "invalid stream seek",
            83 : "invalid stream skip",
            84 : "invalid stream read",
            85 : "invalid stream operation",
            86 : "invalid frame operation",
            87 : "nested frame access",
            88 : "invalid frame read",
            96 : "raster uninitialized",
            97 : "raster corrupted",
            98 : "raster overflow",
            99 : "negative height while rastering",
            112 : "too many registered caches",
            128 : "invalid opcode",
            129 : "too few arguments",
            130 : "stack overflow",
            131 : "code overflow",
            132 : "bad argument",
            133 : "division by zero",
            134 : "invalid reference",
            135 : "found debug opcode",
            136 : "found ENDF opcode in execution stream",
            137 : "nested DEFS",
            138 : "invalid code range",
            139 : "execution context too long",
            140 : "too many function definitions",
            141 : "too many instruction definitions",
            142 : "SFNT font table missing",
            143 : "horizontal header (hhea) table missing",
            144 : "locations (loca) table missing",
            145 : "name table missing",
            146 : "character map (cmap) table missing",
            147 : "horizontal metrics (hmtx) table missing",
            148 : "PostScript (post) table missing",
            149 : "invalid horizontal metrics",
            150 : "invalid character map (cmap) format",
            151 : "invalid ppem value",
            152 : "invalid vertical metrics",
            153 : "could not find context",
            154 : "invalid PostScript (post) table format",
            155 : "invalid PostScript (post) table",
            160 : "opcode syntax error",
            161 : "argument stack underflow",
            162 : "ignore",
            163 : "no Unicode glyph name found",
            164 : "glyph to big for hinting",
            176 : "`STARTFONT' field missing",
            177 : "`FONT' field missing",
            178 : "`SIZE' field missing",
            179 : "`FONTBOUNDINGBOX' field missing",
            180 : "`CHARS' field missing",
            181 : "`STARTCHAR' field missing",
            182 : "`ENCODING' field missing",
            183 : "`BBX' field missing",
            184 : "`BBX' too big",
            185 : "Font header corrupted or missing fields",
            186 : "Font glyphs corrupted or missing fields",
        }

#end Error

# not sure that any of these are really necessary...
ft.FT_Init_FreeType.restype = FT.Error
ft.FT_New_Face.restype = FT.Error
# ft.FT_New_face.argtypes = (FT.Library?, ct.c_char_p, ct.c_int, ct.POINTER(FT.Face))
ft.FT_Select_Charmap.argtypes = (FT.Face, FT.Encoding)
ft.FT_Select_Charmap.restype = FT.Error
ft.FT_Set_Charmap.argtypes = (FT.Face, FT.CharMap)
ft.FT_Set_Charmap.restype = FT.Error
ft.FT_Get_First_Char.restype = ct.c_ulong
ft.FT_Get_Next_Char.restype = ct.c_ulong
ft.FT_Get_X11_Font_Format.restype = ct.c_char_p
ft.FT_Get_Postscript_Name.restype = ct.c_char_p
ft.FT_Get_FSType_Flags.restype = ct.c_ushort

if fc != None :
    fc.FcInit.restype = ct.c_bool
    fc.FcNameParse.argtypes = (ct.c_char_p,)
    fc.FcNameParse.restype = ct.c_void_p
    fc.FcConfigSubstitute.argtypes = (ct.c_void_p, ct.c_void_p, ct.c_int)
    fc.FcConfigSubstitute.restype = ct.c_bool
    fc.FcDefaultSubstitute.argtypes = (ct.c_void_p,)
    fc.FcDefaultSubstitute.restype = None
    fc.FcPatternGetString.argtypes = (ct.c_void_p, ct.c_char_p, ct.c_int, ct.c_void_p)
    fc.FcPatternGetString.restype = ct.c_int
    fc.FcPatternGetInteger.argtypes = (ct.c_void_p, ct.c_char_p, ct.c_int, ct.c_void_p)
    fc.FcPatternGetInteger.restype = ct.c_int
    fc.FcPatternDestroy.argtypes = (ct.c_void_p,)
    fc.FcPatternDestroy.restype = None
    fc.FcFreeTypeQueryFace.restype = ct.c_void_p
    fc.FcNameUnparse.argtypes = (ct.c_void_p,)
    fc.FcNameUnparse.restype = ct.c_void_p

    class _FC :
        # minimal Fontconfig interface, just sufficient for my needs.

        FcMatchPattern = 0
        FcResultMatch = 0

    #end _FC

    class _FcPatternManager :
        # context manager which collects a list of FcPattern objects requiring disposal.

        def __init__(self) :
            self.to_dispose = []
        #end __init__

        def __enter__(self) :
            return \
                self
        #end __enter__

        def collect(self, pattern) :
            "collects another FcPattern reference to be disposed."
            # c_void_p function results are peculiar: they return integers
            # for non-null values, but None for null.
            if pattern != None :
                self.to_dispose.append(pattern)
            #end if
            return \
                pattern
        #end collect

        def __exit__(self, exception_type, exception_value, traceback) :
            for pattern in self.to_dispose :
                fc.FcPatternDestroy(pattern)
            #end for
        #end __exit__

    #end _FcPatternManager

#end if

def _ensure_fc() :
    # ensures Fontconfig is usable, raising suitable exceptions if not.
    if fc == None :
        raise NotImplementedError("Fontconfig not available")
    #end if
    if not fc.FcInit() :
        raise RuntimeError("failed to initialize Fontconfig.")
    #end if
#end _ensure_fc

libc.memcpy.argtypes = (ct.c_void_p, ct.c_void_p, ct.c_size_t)
libc.memcpy.restype = None
libc.free.argtypes = (ct.c_void_p,)

def make_fixed_conv(shift) :
    "returns two functions, the first converting a float value to fixed" \
    " point with shift places to the right of the binary point, the second" \
    " converting that format to a float."
    factor = 1 << shift
    places = (32 - shift, shift)
    conv_to = lambda x : round(x * factor)
    conv_to.__name__ = "to_f%d_%d" % places
    conv_to.__doc__ = "converts a float value to fixed %d.%d format" % places
    conv_from = lambda i : i / factor
    conv_from.__name__ = "from_f%d_%d" % places
    conv_from.__doc__ = "converts a fixed %d.%d value to a float" % places
    return \
        (conv_to, conv_from)
#end make_fixed_conv

to_f26_6, from_f26_6 = make_fixed_conv(6)
to_f16_16, from_f16_16 = make_fixed_conv(16)

from_tag = lambda x : struct.pack(">I", x).decode("ascii")
from_tag.__name__ = "from_tag"
from_tag.__doc__ = "converts an integer tag code to more comprehensible four-character form."

class FTException(Exception) :
    "just to identify a FreeType-specific error exception."

    def __init__(self, code) :
        self.args = (("FreeType error %d -- %s" % (code, Error.Message.get(code, "?"))),)
    #end __init__

#end FTException

def check(sts) :
    "ensures a successful return from a FreeType call."
    if sts != 0 :
        raise FTException(sts)
    #end if
#end check

def def_extra_fields(clas, simple_fields, struct_fields) :
    # bulk definition of extra read-only Python attributes that correspond in a
    # straightforward fashion to FT structure fields. Assumes the instance attribute
    # “_ftobj” points to the FT object to be decoded.

    def def_simple_attr(field, doc, convert) :
        if convert != None :
            def attr(self) :
                return \
                    convert(getattr(self._ftobj.contents, field))
            #end attr
        else :
            def attr(self) :
                return \
                    getattr(self._ftobj.contents, field)
            #end attr
        #end if
        if doc != None :
            attr.__doc__ = doc
        #end if
        setattr(clas, field, property(attr))
    #end def_simple_attr

    def def_struct_attr(field, fieldtype, indirect, doc, extra_decode) :

        def attr(self) :
            return \
                struct_to_dict \
                  (
                    getattr(self._ftobj.contents, field),
                    fieldtype,
                    indirect,
                    extra_decode
                  )
        #end attr

    #begin def_struct_attr
        if doc != None :
            attr.__doc__ = doc
        #end if
        setattr(clas, field, property(attr))
    #end def_struct_attr

#begin def_extra_fields
    for field, doc, convert in simple_fields :
        def_simple_attr(field, doc, convert)
    #end for
    for field, fieldtype, indirect, doc, extra_decode in struct_fields :
        def_struct_attr(field, fieldtype, indirect, doc, extra_decode)
    #end for
#end def_extra_fields

#+
# Higher-level wrapper classes for FreeType objects
#-

def ft_convs(clas, ft_type, fields) :
    # defines conversions to/from components of different fixed-point formats.

    def def_ft_conv(name, shift) :
        if shift != 0 :
            factor = 1 << shift
            coord_to = lambda x : round(x * factor)
            coord_from = lambda i : i / factor
        else :
            coord_to = lambda x : round(x)
            coord_from = lambda i : float(i)
        #end if
        conv_to = lambda self : ft_type(*tuple(coord_to(getattr(self, k)) for k in fields))
        conv_to.__name__ = "to_ft_%s" % name
        conv_to.__doc__ = "returns an FT.%s value representing the contents of this %s with coordinates interpreted as %s" % (ft_type.__name__, clas.__name__, name)
        conv_from = lambda ftobj : clas(*tuple(coord_from(getattr(ftobj, k)) for k in fields))
        conv_from.__name__ = "from_ft_%s" % name
        conv_from.__doc__ = "creates a new %s from an FT.%s with coordinates interpreted as %s" % (clas.__name__, ft_type.__name__, name)
        setattr(clas, conv_to.__name__, conv_to)
        setattr(clas, conv_from.__name__, staticmethod(conv_from))
    #end def_ft_conv

#begin ft_convs
    for \
        name, shift \
    in \
        (
            ("int", 0),
            ("f16_16", 16),
            ("f26_6", 6),
        ) \
    :
        def_ft_conv(name, shift)
    #end for
#end ft_convs

deg = math.pi / 180
  # all angles are in radians. You can use the standard Python functions math.degrees
  # and math.radians to convert back and forth, or multiply and divide by this deg
  # factor: multiply by deg to convert degrees to radians, and divide by deg to convert
  # the other way, e.g.
  #
  #     math.sin(45 * deg)
  #     math.atan(1) / deg
circle = 2 * math.pi
  # Alternatively, you can work in units of full circles. E.g.
  # 0.25 * circle is equivalent to 90°

class Vector :
    "Pythonic representation of an FT.Vector, with conversions to/from FreeType form."

    __slots__ = ("x", "y") # to forestall typos

    def __init__(self, x, y) :
        "args should be float values."
        self.x = x
        self.y = y
    #end __init__

    def __getitem__(self, i) :
        "being able to access elements by index allows a Vector to be cast to a tuple or list."
        return \
            (self.x, self.y)[i]
    #end __getitem__

    # conversions to/from FreeType format added below

    def __repr__(self) :
        return \
            "Vector(%.3f, %.3f)" % (self.x, self.y)
    #end __repr__

    def __add__(v1, v2) :
        return \
            (
                lambda : NotImplemented,
                lambda : Vector(v1.x + v2.x, v1.y + v2.y)
            )[isinstance(v2, Vector)]()
    #end __add__

    def __sub__(v1, v2) :
        return \
            (
                lambda : NotImplemented,
                lambda : Vector(v1.x - v2.x, v1.y - v2.y)
            )[isinstance(v2, Vector)]()
    #end __sub__

    def __mul__(v, f) :
        if isinstance(f, Vector) :
            result = Vector(v.x * f.x, v.y * f.y)
        elif isinstance(f, Number) :
            result = Vector(v.x * f, v.y * f)
        else :
            result = NotImplemented
        #end if
        return \
            result
    #end __mul__
    __rmul__ = __mul__

    def __truediv__(v, f) :
        if isinstance(f, Vector) :
            result = Vector(v.x / f.x, v.y / f.y)
        elif isinstance(f, Number) :
            result = Vector(v.x / f, v.y / f)
        else :
            result = NotImplemented
        #end if
        return \
            result
    #end __truediv__

    @staticmethod
    def unit(angle) :
        "returns the unit vector with the specified direction."
        return \
            Vector(math.cos(angle), math.sin(angle))
    #end unit

    def rotate(self, angle) :
        "returns the Vector rotated by the specified angle."
        cos = math.cos(angle)
        sin = math.sin(angle)
        return \
            Vector(self.x * cos - self.y * sin, self.x * sin + self.y * cos)
    #end rotate

    def __abs__(self) :
        "use abs() to get the length of a Vector."
        return \
            math.hypot(self.x, self.y)
    #end __abs__

    def angle(self) :
        "returns the Vector’s rotation angle."
        return \
            math.atan2(self.y, self.x)
    #end angle

    @staticmethod
    def from_polar(length, angle) :
        "constructs a Vector from a length and a direction."
        return \
            Vector(length * math.cos(angle), length * math.sin(angle))
    #end from_polar

#end Vector
ft_convs(Vector, FT.Vector, ("x", "y"))

class Matrix :
    "Pythonic representation of an FT.Matrix, with conversions to/from FreeType form."

    __slots__ = ("xx", "xy", "yx", "yy") # to forestall typos

    def __init__(self, xx, xy, yx, yy) :
        "args should be float values."
        self.xx = xx
        self.xy = xy
        self.yx = yx
        self.yy = yy
    #end __init__

    def __repr__(self) :
        return \
            "Matrix(%.3f, %.3f, %.3f, %.3f)" % (self.xx, self.xy, self.yx, self.yy)
    #end __repr__

    @staticmethod
    def from_ft(mat) :
        "creates a new Matrix from an FT.Matrix value."
        args = {}
        for field, _ in FT.Matrix._fields_ :
            args[field] = from_f16_16(getattr(mat, field))
        #end for
        return \
            Matrix(**args)
    #end from_ft

    def to_ft(self) :
        "returns an FT.Matrix value representing the conversion of this Matrix."
        args = {}
        for field, _ in FT.Matrix._fields_ :
            args[field] = to_f16_16(getattr(self, field))
        #end for
        return \
            FT.Matrix(**args)
    #end to_ft

    # I do my own implementations of arithmetic operations, since I don’t see
    # any point in wrapping the FreeType ones (unless you require lesser accuracy...)

    def __mul__(m1, m2) :
        "vector/matrix multiplication."
        if isinstance(m2, Matrix) :
            result = \
                Matrix \
                  (
                    xx = m1.xx * m2.xx + m1.xy * m2.yx,
                    xy = m1.xx * m2.xy + m1.xy * m2.yy,
                    yx = m1.yx * m2.xx + m1.yy * m2.yx,
                    yy = m1.yx * m2.xy + m1.yy * m2.yy,
                  )
        elif isinstance(m2, Vector) :
            result = \
                Vector \
                  (
                    x = m1.xx * m2.x + m1.xy * m2.y,
                    y = m1.yx * m2.x + m1.yy * m2.y,
                  )
        else :
            raise TypeError("Matrix can only multiply Vector or Matrix")
        #end if
        return \
            result
    #end __mul__

    def det(m) :
        "matrix determinant."
        return \
            m.xx * m.yy - m.xy * m.yx
    #end det

    def inv(m) :
        "matrix inverse."
        det = m.det()
        return \
            Matrix \
              (
                xx = m.yy / det,
                xy = - m.xy / det,
                yx = - m.yx / det,
                yy = m.xx / det,
              )
    #end inv

    def __truediv__(m1, m2) :
        "division = multiplication by matrix inverse."
        if not isinstance(m2, Matrix) :
            raise TypeError("Matrix can only be divided by Matrix")
        #end if
        return \
            m1.__mul__(m2.inv())
    #end __truediv__

    @property
    def ident(self) :
        "identity matrix."
        return \
            Matrix(xx = 1.0, xy = 0.0, yx = 0.0, yy = 1.0)
    #end ident

    @staticmethod
    def scaling(sx, sy) :
        "returns a Matrix that scales by the specified x- and y-factors."
        return \
            Matrix \
              (
                xx = sx,
                xy = 0.0,
                yx = 0.0,
                yy = sy,
              )
    #end scaling

    @staticmethod
    def rotation(angle) :
        "returns a Matrix that rotates by the specified angle."
        cos = math.cos(angle)
        sin = math.sin(angle)
        return \
            Matrix \
              (
                xx = cos,
                xy = - sin,
                yx = sin,
                yy = cos,
              )
    #end rotation

    @staticmethod
    def skewing(x_skew, y_skew) :
        "returns a Matrix that skews in the x- and y-directions by the specified amounts."
        return \
            Matrix \
              (
                xx = 1,
                xy = x_skew,
                yx = y_skew,
                yy = 1
              )
    #end skewing

#end Matrix

class BBox :
    "high-level wrapper around an FT.BBox. Coordinates are always stored as floats, but can" \
    " be converted to/from appropriate FreeType scaled fixed-point types."

    __slots__ = ("xMin", "yMin", "xMax", "yMax") # to forestall typos

    def __init__(self, xMin, yMin, xMax, yMax) :
        self.xMin = xMin
        self.yMin = yMin
        self.xMax = xMax
        self.yMax = yMax
    #end __init__

    def __repr__(self) :
        return \
            "BBox(%.3f, %.3f, %.3f, %.3f)" % (self.xMin, self.yMin, self.xMax, self.yMax)
    #end __repr__

#end BBox
ft_convs(BBox, FT.BBox, ("xMin", "yMin", "xMax", "yMax"))

del ft_convs # my work is done

class Library :
    "Instantiate this to open the FreeType library. Use the new_face or find_face" \
    " methods to open a font file and construct a new Face object."

    __slots__ = ("lib", "__weakref__") # to forestall typos

    def __init__(self) :
        self.lib = ct.c_void_p(0)
        check(ft.FT_Init_FreeType(ct.byref(self.lib)))
    #end __init__

    def __del__(self) :
        if self.lib.value != None :
            ft.FT_Done_FreeType(self.lib)
            self.lib.value = None
        #end if
    #end __del__

    @property
    def version(self) :
        "the FreeType library version, as a triple of integers: (major, minor, patch)."
        ver_major = ct.c_int()
        ver_minor = ct.c_int()
        ver_patch = ct.c_int()
        ft.FT_Library_Version(self.lib, ct.byref(ver_major), ct.byref(ver_minor), ct.byref(ver_patch))
        return \
            (ver_major.value, ver_minor.value, ver_patch.value)
    #end version

    def new_face(self, filename, face_index = 0) :
        "loads an FT.Face from a file and returns a Face object for it."
        result_face = FT.Face()
        check(ft.FT_New_Face(self.lib, filename.encode("utf-8"), face_index, ct.byref(result_face)))
        return \
            Face(self, result_face, filename)
    #end new_face

    def find_face(self, pattern) :
        "finds a font file by trying to match a Fontconfig pattern string, loads an FT.Face" \
        " from it and returns a Face object."
        _ensure_fc()
        with _FcPatternManager() as patterns :
            search_pattern = patterns.collect(fc.FcNameParse(pattern.encode("utf-8")))
            if search_pattern == None :
                raise RuntimeError("cannot parse font name pattern")
            #end if
            if not fc.FcConfigSubstitute(None, search_pattern, _FC.FcMatchPattern) :
                raise RuntimeError("cannot substitute font configuration")
            #end if
            fc.FcDefaultSubstitute(search_pattern)
            match_result = ct.c_int()
            found_pattern = patterns.collect(fc.FcFontMatch(None, search_pattern, ct.byref(match_result)))
            if found_pattern == None or match_result.value != _FC.FcResultMatch :
                raise RuntimeError("cannot match font name")
            #end if
            name_ptr = ct.c_char_p()
            face_index_ptr = ct.c_int()
            if fc.FcPatternGetString(found_pattern, b"file", 0, ct.byref(name_ptr)) != _FC.FcResultMatch :
                raise RuntimeError("cannot get font file name")
            #end if
            if fc.FcPatternGetInteger(found_pattern, b"index", 0, ct.byref(face_index_ptr)) != _FC.FcResultMatch :
                raise RuntimeError("cannot get font file index")
            #end if
            found_filename = name_ptr.value.decode("utf-8")
            face_index = face_index_ptr.value
        #end with
        return \
            self.new_face(found_filename, face_index)
    #end find_face

#end Library

class Face :
    "represents an FT.Face. Do not instantiate directly; call Library.new_face" \
    " or Library.find_face instead."

    __slots__ = \
        (
            "_ftobj", "_lib",
            "filename", "family_name", "style_name",
            "num_faces", "face_index", "face_flags", "style_flags", "num_glyphs",
            "available_sizes", "charmaps",
        ) # to forestall typos

    def __init__(self, lib, face, filename) :
        self._ftobj = face
        self._lib = weakref.ref(lib)
        facerec = ct.cast(self._ftobj, FT.Face).contents
        self.filename = filename
        # following attrs don't change, but perhaps it is simpler to define them
        # via def_extra_fields anyway
        for \
            field \
        in \
            (
                "num_faces",
                "face_index",
                "face_flags",
                "style_flags",
                "num_glyphs",
            ) \
        :
            setattr(self, field, getattr(facerec, field))
        #end for
        for \
            field \
        in \
            (
                "family_name",
                "style_name",
            ) \
        :
            setattr(self, field, getattr(facerec, field).decode("utf-8"))
        #end for
        # end attributes which could go into def_extra_fields call
        for \
            nr_field, ptr_field, elt_type, deref, exclude \
        in \
            (
                ("num_fixed_sizes", "available_sizes", FT.Bitmap_Size, False, ()),
                ("num_charmaps", "charmaps", FT.CharMapRec, True, ("face",)),
            ) \
        :
            nr_items = getattr(facerec, nr_field)
            elts = getattr(facerec, ptr_field)
            items = []
            for i in range(0, nr_items) :
                elt = elts[i]
                if deref :
                    elt = elt.contents
                #end if
                item = {}
                for k in elt_type._fields_ :
                    k, t = k
                    if k not in exclude :
                        item[k] = getattr(elt, k)
                        if t is FT.Encoding :
                            item[k] = from_tag(item[k])
                        elif t is FT.Pos :
                            item[k] = from_f26_6(item[k])
                        #end if
                    #end if
                #end for
                if deref :
                    item["."] = elts[i]
                #end if
                items.append(item)
            #end for
            setattr(self, ptr_field, items)
        #end for
    #end __init__

    def __del__(self) :
        if self._ftobj != None and self._lib() != None :
            # self._lib might have vanished prematurely during program exit
            check(ft.FT_Done_Face(self._ftobj))
            self._ftobj = None
        #end if
    #end __del__

    @property
    def font_format(self) :
        "the font format."
        return \
            ft.FT_Get_X11_Font_Format(self._ftobj).decode("utf-8")
    #end font_format

    @property
    def fc_pattern(self) :
        "a Fontconfig pattern string describing this Face."
        _ensure_fc()
        with _FcPatternManager() as patterns :
            descr_pattern = patterns.collect(fc.FcFreeTypeQueryFace(self._ftobj, ct.c_char_p(self.filename.encode("utf-8")), self._ftobj.contents.face_index, None))
            if descr_pattern == None :
                raise RuntimeError("cannot construct font name pattern")
            #end if
            resultstr = fc.FcNameUnparse(descr_pattern)
            if resultstr == None :
                raise RuntimeError("cannot unparse font name pattern")
            #end if
            result = ct.cast(resultstr, ct.c_char_p).value.decode("utf-8")
            libc.free(resultstr)
        #end with
        return \
            result
    #end fc_pattern

    def select_charmap(self, encoding) :
        check(ft.FT_Select_Charmap(self._ftobj, encoding))
    #end select_charmap

    def set_charmap(self, charmap) :
        "charmap should be an element of self.charmaps"
        check(ft.FT_Set_Charmap(self._ftobj, charmap["."]))
    #end set_charmap

    def get_charmap_index(self, charmap) :
        "charmap should be an element of self.charmaps; attempting" \
        " to generalize this seems to lead to segfaults."
        return \
            ft.FT_Get_Charmap_Index(charmap["."])
    #end get_charmap_index

    def set_char_size(self, size = None, width = None, height = None, resolution = None, horz_resolution = None, vert_resolution = None) :
        "sets the character size and resolution in various ways: you can specify width and height" \
        " separately, or size for both; similarly you can specify horz_resolution and" \
        " vert_resolution separately, or resolution for both."
        assert \
            (
                (size != None) != (width != None and height != None)
            and
                (resolution != None) != (horz_resolution != None and vert_resolution != None)
            ), \
            "need to specify either size or width and height, and either resolution or horz_resolution and vert_resolution"
        if width == None :
            width = size
        #end if
        if height == None :
            height = size
        #end if
        if horz_resolution == None :
            horz_resolution = resolution
        #end if
        if vert_resolution == None :
            vert_resolution = resolution
        #end if
        check(ft.FT_Set_Char_Size
          (
            self._ftobj,
            to_f26_6(width),
            to_f26_6(height),
            horz_resolution,
            vert_resolution,
          ))
    #end set_char_size

    def set_pixel_sizes(self, pixel_width, pixel_height) :
        check(ft.FT_Set_Pixel_Sizes(self._ftobj, int(pixel_width), int(pixel_height)))
    #end set_pixel_sizes

    def request_size(self, reqtype, width, height, horiResolution, vertResolution) :
        req = FT.Size_RequestRec(int(reqtype), int(width), int(height), to_f26_6(horiResolution), to_f26_6(vertResolution))
        check(ft.FT_Request_Size(self._ftobj, ct.byref(req)))
    #end request_size

    def select_size(self, strike_index) :
        check(ft.FT_Select_Size(self._ftobj, int(strike_index)))
    #end select_size

    def set_transform(self, matrix, delta) :
        "matrix and delta should be the Pythonic Matrix and Vector, not the FT types."
        ftmat = matrix.to_ft()
        ftdelta = delta.to_ft_f26_6() # this is a guess
        ft.FT_Set_Transform(self._ftobj, ct.byref(ftmat), ct.byref(ftdelta))
    #end set_transform

    def char_glyphs(self) :
        "generator which yields successive (char_code, glyph_code) pairs defined for" \
        " the current charmap."
        glyph_index = ct.c_uint(0)
        char_code = ft.FT_Get_First_Char(self._ftobj, ct.byref(glyph_index))
        while glyph_index.value != 0 :
            yield char_code, glyph_index.value
            char_code = ft.FT_Get_Next_Char(self._ftobj, char_code, ct.byref(glyph_index))
        #end while
    #end char_glyphs

    def get_char_index(self, charcode) :
        return \
            ft.FT_Get_Char_Index(self._ftobj, charcode)
    #end get_char_index

    def load_glyph(self, glyph_index, load_flags) :
        check(ft.FT_Load_Glyph(self._ftobj, glyph_index, load_flags))
    #end load_glyph

    def load_char(self, char_code, load_flags) :
        check(ft.FT_Load_Char(self._ftobj, char_code, load_flags))
    #end load_char

    def glyph_slots(self) :
        "generator which yields each element of the linked list of glyph slots in turn."
        glyph = self._ftobj.contents.glyph
        while True :
            yield GlyphSlot(glyph)
            try :
                glyph = glyph.contents.next
                _ = glyph.contents # check it's not just wrapping a null pointer
            except ValueError : # assume because of NULL pointer access
                break
            #end try
        #end while
    #end glyph_slots

    @property
    def glyph(self) :
        "the first or only glyph slot."
        return \
            GlyphSlot(self._ftobj.contents.glyph)
    #end glyph

    def get_kerning(self, left_glyph, right_glyph, kern_mode) :
        result = FT.Vector()
        check(ft.FT_Get_Kerning(self._ftobj, left_glyph, right_glyph, kern_mode, ct.byref(result)))
        if self._ftobj.contents.face_flags & FT.FACE_FLAG_SCALABLE != 0 and kern_mode != FT.KERNING_UNSCALED :
            result = Vector.from_ft_f26_6(result)
        else :
            result = Vector.from_ft_int(result)
        #end if
        return \
            result
    #end get_kerning

    def get_track_kerning(self, point_size, degree) :
        result = FT.Fixed(0)
        check(ft.FT_Get_Track_Kerning(self._ftobj, to_f16_16(point_size), degree, ct.byref(result)))
        return \
            from_f26_6(result.value)
    #end get_track_kerning

    def get_advance(self, gindex, load_flags) :
        result = FT.Fixed(0)
        check(ft.FT_Get_Advance(self._ftobj, gindex, load_flags, ct.byref(result)))
        return \
            (from_f16_16, int)[load_flags & FT.LOAD_NO_SCALE != 0](result.value)
    #end get_advance

    def get_advances(self, start, count, load_flags) :
        result = (count * FT.Fixed)()
        check(ft.FT_Get_Advances(self._ftobj, start, count, load_flags, ct.byref(result)))
        return \
            tuple((from_f16_16, int)[load_flags & FT.LOAD_NO_SCALE != 0](item) for item in result)
    #end get_advances

    def get_glyph_name(self, glyph_index) :
        "returns the name of the specified glyph."
        buffer_max = 256 # enough?
        buffer = (buffer_max * ct.c_char)()
        check(ft.FT_Get_Glyph_Name(self._ftobj, int(glyph_index), ct.byref(buffer), buffer_max))
        return \
            buffer.value.decode("utf-8")
    #end get_glyph_name

    def get_name_index(self, glyph_name) :
        "returns the index of the specified glyph name."
        return \
            ft.FT_Get_Name_Index(self._ftobj, ct.c_char_p(glyph_name.encode("utf-8")))
    #end get_name_index

    @property
    def postscript_name(self) :
        "the PostScript name of the font, if it has one."
        result = ft.FT_Get_Postscript_Name(self._ftobj)
        if bool(result) :
            result = result.decode("utf-8")
        else :
            result = None
        #end if
        return \
            result
    #end postscript_name

    @property
    def fstype_flags(self) :
        "the FSType flags which specify the licensing restrictions on font embedding/subsetting."
        return \
            ft.FT_Get_FSType_Flags(self._ftobj)
    #end fstype_flags

#end Face
def_extra_fields \
  (
    clas = Face,
    simple_fields =
        (
            ("bbox", "bounding box in font units, big enough to contain any glyph (scalable fonts only)", BBox.from_ft_int),
            ("units_per_EM", "integer font units per em square (scalable fonts only)", None),
            ("ascender", "typographic ascender in font units (scalable fonts only)", None),
            ("descender", "typographic descender in font units, typically negative (scalable fonts only)", None),
            ("height", "vertical distance between successive lines, in font units, always positive (scalable fonts only)", None),
            ("max_advance_width", "maximum advance width in font units (scalable fonts only)", None),
            ("max_advance_height", "maximum advance height for vertical layouts (scalable fonts only)", None),
            ("underline_position", "position in font units of underline (scalable fonts only)", None),
            ("underline_thickness", "thickness in font units of underline (scalable fonts only)", None),
        ),
    struct_fields =
        (
            (
                "size", FT.SizeRec, True, "current active size",
                {
                    "metrics" :
                        lambda x :
                            struct_to_dict
                              (
                                item = x,
                                itemtype = FT.Size_Metrics,
                                indirect = False,
                                extra_decode =
                                    {
                                        "x_scale" : from_f16_16,
                                        "y_scale" : from_f16_16,
                                        "ascender" : from_f26_6,
                                        "descender" : from_f26_6,
                                        "height" : from_f26_6,
                                        "max_advance" : from_f26_6,
                                    }
                              )
                },
            ),
            ("charmap", FT.CharMapRec, True, "current active charmap", {"encoding" : from_tag}),
        ),
  )

class GlyphSlot :
    "represents an FT.GlyphSlotRec. Do not instantiate directly;" \
    " call Face.glyph_slots or access via Face.glyph and GlyphSlot.next links instead."

    __slots__ = ("_ftobj",) # to forestall typos

    def __init__(self, ftobj) :
        self._ftobj = ftobj
    #end __init__

    @property
    def next(self) :
        "link to next GlyphSlot, if any."
        try :
            result = GlyphSlot(self._ftobj.contents.next)
            _ = result.advance # check it's not just wrapping a null pointer
        except ValueError : # assume because of NULL pointer access
            result = None
        #end try
        return \
            result
    #end def

    @property
    def outline(self) :
        "the Outline, if format = FT.GLYPH_FORMAT_OUTLINE."
        assert self._ftobj.contents.format == FT.GLYPH_FORMAT_OUTLINE
        return \
            Outline(ct.pointer(self._ftobj.contents.outline), self, None)
    #end outline

    def render_glyph(self, render_mode) :
        "renders the loaded glyph to a bitmap."
        check(ft.FT_Render_Glyph(self._ftobj, render_mode))
    #end render_glyph

    @property
    def bitmap(self) :
        "the Bitmap, if format = FT.GLYPH_FORMAT_BITMAP."
        assert self._ftobj.contents.format == FT.GLYPH_FORMAT_BITMAP
        return \
            Bitmap(ct.pointer(self._ftobj.contents.bitmap), self, None)
    #end bitmap

    @property
    def bitmap_left(self) :
        "bitmap left bearing in integer pixels (only if glyph is a bitmap)"
        assert self._ftobj.contents.format == FT.GLYPH_FORMAT_BITMAP
        return \
            self._ftobj.contents.bitmap_left
    #end bitmap_left

    @property
    def bitmap_top(self) :
        "bitmap top bearing in integer pixels (only if glyph is a bitmap)"
        assert self._ftobj.contents.format == FT.GLYPH_FORMAT_BITMAP
        return \
            self._ftobj.contents.bitmap_top
    #end bitmap_left

    def own_bitmap(self) :
        "ensures the GlyphSlot has its own copy of bitmap storage."
        check(ft.FT_GlyphSlot_Own_Bitmap(self._ftobj))
    #end own_bitmap

    def get_glyph(self) :
        result = FT.Glyph()
        check(ft.FT_Get_Glyph(self._ftobj, ct.byref(result)))
        return \
            Glyph(result)
    #end get_glyph

    class SubGlyphInfo :
        "convenient container for info returned from get_subglyph_info." \
        " index, flags, arg1 and arg2 are integers, while transform is a Matrix." \
        " See FT.SUBGLYPH_FLAG_XXX for flags bits."

        def __init__(self, index, flags, arg1, arg2, transform) :
            self.index = index
            self.flags = flags
            self.arg1 = arg1
            self.arg2 = arg2
            self.transform = transform
        #end __init__

    #end SubGlyphInfo

    def get_subglyph_info(self, sub_index) :
        "returns info about the specified subglyph (sub_index must be in [0 .. num_subglyphs - 1])." \
        " The info will be returned in a SubGlyphInfo object."
        p_index = ct.c_int()
        p_flags = ct.c_uint()
        p_arg1 = ct.c_int()
        p_arg2 = ct.c_int()
        transform = FT.Matrix()
        # bug in some versions of FreeType (e.g. 2.5.2): FT_Get_SubGlyph_Info
        # currently always returns error, even on success.
        # so rather than check its error return, I do my own validation:
        if self._ftobj.contents.format != FT.GLYPH_FORMAT_COMPOSITE :
            raise TypeError("only composite glyphs have subglyphs")
        #end if
        if sub_index < 0 or sub_index >= self._ftobj.contents.num_subglyphs :
            raise IndexError("subglyph subindex out of range")
        #end if
        ft.FT_Get_SubGlyph_Info \
          (
            self._ftobj,
            sub_index,
            ct.byref(p_index),
            ct.byref(p_flags),
            ct.byref(p_arg1),
            ct.byref(p_arg2),
            ct.byref(transform),
          )
        return \
            GlyphSlot.SubGlyphInfo(p_index.value, p_flags.value, p_arg1.value, p_arg2.value, Matrix.from_ft(transform))
    #end get_subglyph_info

#end GlyphSlot
def_extra_fields \
  (
    clas = GlyphSlot,
    simple_fields =
        (
            ("linearHoriAdvance", "advance width of unhinted outline glyph", from_f16_16),
            ("linearVertAdvance", "advance height of unhinted outline glyph", from_f16_16),
            ("format",
                "glyph format, typically FT.GLYPH_FORMAT_BITMAP, FT.GLYPH_FORMAT_OUTLINE"
                " or FT.GLYPH_FORMAT_COMPOSITE",
                from_tag),
            ("advance", "transformed (hinted) advance in (possibly fractional) pixels", Vector.from_ft_f26_6),
            ("num_subglyphs",
                "number of subglyphs in a composite glyph. Only if format is"
                " FT.GLYPH_FORMAT_COMPOSITE, which can only happen if glyph was"
                " loaded with FT.LOAD_NO_RECURSE, and only with certain fonts",
                None),
        ),
    struct_fields =
        (
            ("metrics", FT.Glyph_Metrics, False, "metrics of last loaded glyph in slot", {None : from_f26_6}),
        ),
  )

# types of control points for outline curves
CURVEPT_ON = 1 # on-curve (corner)
CURVEPT_OFF2 = 0 # off-curve (quadratic Bézier segment)
CURVEPT_OFF3 = 2 # off-curve (cubic Bézier segment)

class Outline :
    "Pythonic representation of an FT.Outline. Get one of these from" \
    " GlyphSlot.outline or Outline.new()."

    __slots__ = ("_ftobj", "_lib", "owner") # to forestall typos

    def __init__(self, ftobj, owner, lib) :
        self._ftobj = ftobj
        assert (owner != None) != (lib != None)
        if owner != None :
            self.owner = owner # keep a strong ref to ensure it doesn’t disappear unexpectedly
            self._lib = None
        else :
            self.owner = None
            self._lib = weakref.ref(lib)
        #end if
    #end __init__

    def __del__(self) :
        if self.owner == None and self._lib != None and self._lib() != None :
            if self._ftobj != None :
                check(ft.FT_Outline_Done(self._lib().lib, self._ftobj))
                self._ftobj = None
            #end if
        #end if
    #end __del__

    # wrappers for outline-processing functions
    # <http://www.freetype.org/freetype2/docs/reference/ft2-outline_processing.html>

    @staticmethod
    def new(lib) :
        "allocates a new Outline object with initially no control points or contours."
        if not isinstance(lib, Library) :
            raise TypeError("expecting a Library")
        #end if
        result = ct.pointer(FT.Outline())
        check(ft.FT_Outline_New(lib.lib, 0, 0, result))
        return \
            Outline(result, None, lib)
    #end new

    def copy(self, other) :
        "makes a copy of the contours of this Outline into other, which must have" \
        " the same numbers of control points and contours."
        if not isinstance(other, Outline) :
            raise TypeError("can only copy into another Outline")
        #end if
        check(ft.FT_Outline_Copy(self._ftobj, other._ftobj))
    #end copy

    def translate(self, x_offset, y_offset) :
        ft.FT_Outline_Translate(self._ftobj, to_f26_6(x_offset), to_f26_6(y_offset))
    #end translate

    def transform(self, matrix) :
        "transforms the Outline by the specified Matrix."
        ft.FT_Outline_Transform(self._ftobj, ct.byref(matrix.to_ft()))
    #end transform

    def embolden(self, strength) :
        "uniformly emboldens the Outline."
        check(ft.FT_Outline_Embolden(self._ftobj, to_f26_6(strength)))
    #end embolden

    def embolden_xy(self, x_strength, y_strength) :
        "non-uniformly emboldens the Outline."
        check(ft.FT_Outline_EmboldenXY(self._ftobj, to_f26_6(x_strength), to_f26_6(y_strength)))
    #end embolden

    def reverse(self) :
        "reverses the Outline direction."
        ft.FT_Outline_Reverse(self._ftobj)
    #end reverse

    def check(self) :
        "checks the Outline contents."
        check(ft.FT_Outline_Check(self._ftobj))
    #end check

    def get_cbox(self) :
        "returns the Outline’s control box, which encloses all the control points."
        result = FT.BBox()
        ft.FT_Outline_Get_CBox(self._ftobj, ct.byref(result))
        return \
            BBox.from_ft_f26_6(result)
    #end get_cbox

    def get_bbox(self) :
        "returns the Outline’s bounding box, which encloses the entire glyph."
        result = FT.BBox()
        check(ft.FT_Outline_Get_BBox(self._ftobj, ct.byref(result)))
        return \
            BBox.from_ft_f26_6(result)
    #end get_bbox

    def get_bitmap(self, lib, the_bitmap) :
        "renders the Outline into the pre-existing Bitmap."
        if not isinstance(lib, Library) :
            raise TypeError("expecting lib to be a Library")
        #end if
        if not isinstance(the_bitmap, Bitmap) :
            raise TypeError("expecting the_bitmap to be a Bitmap")
        #end if
        check(ft.FT_Outline_Get_Bitmap(lib.lib, self._ftobj, the_bitmap._ftobj))
    #end get_bitmap

    def get_orientation(self) :
        return \
            ft.FT_Outline_Get_Orientation(self._ftobj)
    #end get_orientation

    def render \
      (
        self,
        lib,
        target = None,
          # result will be anti-aliased greyscale if FT.RASTER_FLAG_AA is in flags,
          # else 1-bit monochrome
        flags = FT.RASTER_FLAG_DEFAULT,
        gray_spans = None,
          # ignored unless FT.RASTER_FLAG_DIRECT and FT.RASTER_FLAG_AA are in flags
        user = None,
        clip_box = None # ignored unless FT.RASTER_FLAG_CLIP is in flags
      ) :
        "renders the Outline to either the target Bitmap or through the gray_spans callback," \
        " depending on flags."
        if not isinstance(lib, Library) :
            raise TypeError("expecting lib to be a Library")
        #end if
        if target != None and not isinstance(target, Bitmap) :
            raise TypeError("expecting target to be a Bitmap")
        #end if
        params = FT.Raster_Params()
        if target != None :
            params.target = target._ftobj # BitmapPtr
        else :
            params.target = None
        #end if
        # params.source = self._ftobj # will be done by FreeType anyway
        params.flags = flags
        params.gray_spans = FT.SpanFunc(gray_spans)
        params.black_spans = FT.SpanFunc(0) # unused
        params.bit_test = FT.Raster_BitTest_Func(0) # unused
        params.bit_set = FT.Raster_BitSet_Func(0) # unused
        params.user = None # handled specially
        if clip_box != None :
            params.clip_box = clip_box.to_ft_int()
        else :
            params.clip_box = FT.BBox()
        #end if
        check(ft.FT_Outline_Render(lib.lib, self._ftobj, ct.byref(params)))
    #end render

    # end of wrappers for outline-processing functions

    @property
    def contours(self) :
        "a tuple of the contours of the outline. Each element is a tuple of curve" \
        " points, each in turn being a triple (coord : Vector, point_type : CURVEPT, dropout_flags : int)."
        result = []
        pointindex = 0
        ftobj = self._ftobj.contents
        for contourindex in range(0, ftobj.n_contours) :
            contour = []
            endpoint = ftobj.contours[contourindex]
            while True :
                if pointindex == ftobj.n_points :
                    raise IndexError("contour point index has run off the end")
                #end if
                point = ftobj.points[pointindex]
                flag = ftobj.tags[pointindex]
                pt_type = flag & 3
                contour.append((Vector.from_ft_f26_6(point), pt_type, flag >> 32))
                  # interpreting coords as f26.6 is a guess
                if pointindex == endpoint :
                    break
                pointindex += 1
            #end while
            result.append(tuple(contour))
        #end for
        return \
            tuple(result)
    #end contours

    def decompose(self, move_to, line_to, conic_to, cubic_to, arg = None) :
        "decomposes the contours of the outline and calls the specified actions" \
        " for each segment: move_to(pos, arg), line_to(pos, arg), conic_to(pos1, pos2, arg)" \
        " and cubic_to(pos1, pos2, pos3, arg), where the posn args are Vectors, and the" \
        " meaning of arg is up to you. Each action must return a status, 0 for success." \
        " If conic_to is None, then cubic_to will be called for conic segments with" \
        " control points suitably calculated to produce the right quadratic curve."

        pos0 = None
        from_ft = Vector.from_ft_f26_6

        def wrap_move_to(pos, _) :
            pos = from_ft(pos.contents)
            if conic_to == None :
                nonlocal pos0
                pos0 = pos
            #end if
            return \
                move_to(pos, arg)
        #end wrap_move_to

        def wrap_line_to(pos, _) :
            pos = from_ft(pos.contents)
            if conic_to == None :
                nonlocal pos0
                pos0 = pos
            #end if
            return \
                line_to(pos, arg)
        #end wrap_line_to

        def wrap_conic_to(qpos1, qpos2, _) :
            if conic_to != None :
                pos1 = from_ft(qpos1.contents)
                pos2 = from_ft(qpos2.contents)
                result = conic_to(pos1, pos2, arg)
            else :
                nonlocal pos0
                midpos = from_ft(qpos1.contents)
                pos3 = from_ft(qpos2.contents)
                # quadratic-to-cubic conversion taken from
                # <http://stackoverflow.com/questions/3162645/convert-a-quadratic-bezier-to-a-cubic>
                pos1 = pos0 + 2 * (midpos - pos0) / 3
                pos2 = pos3 + 2 * (midpos - pos3) / 3
                result = cubic_to(pos1, pos2, pos3, arg)
                pos0 = pos2
            #end if
            return \
                result
        #end wrap_conic_to

        def wrap_cubic_to(pos1, pos2, pos3, _) :
            pos1 = from_ft(pos1.contents)
            pos2 = from_ft(pos2.contents)
            pos3 = from_ft(pos3.contents)
            return \
                cubic_to(pos1, pos2, pos3, arg)
        #end wrap_cubic_to

    #begin decompose
        funcs = FT.Outline_Funcs \
          (
            move_to = FT.Outline_MoveToFunc(wrap_move_to),
            line_to = FT.Outline_LineToFunc(wrap_line_to),
            conic_to = FT.Outline_ConicToFunc(wrap_conic_to),
            cubic_to = FT.Outline_CubicToFunc(wrap_cubic_to),
            shift = 0,
            delta = 0,
          )
        check(ft.FT_Outline_Decompose(self._ftobj, ct.byref(funcs), ct.c_void_p(0)))
    #end decompose

    def draw(self, g) :
        "appends the Outline contours onto the current path being constructed in g, which" \
        " is expected to be a cairo.Context."

        def move_to(pos, _) :
            g.move_to(pos.x, pos.y)
            return \
                0
        #end move_to

        def line_to(pos, _) :
            g.line_to(pos.x, pos.y)
            return \
                0
        #end line_to

        def curve_to(pos1, pos2, pos3, _) :
            g.curve_to(pos1.x, pos1.y, pos2.x, pos2.y, pos3.x, pos3.y)
            return \
                0
        #end curve_to

    #begin draw
        if cairo == None :
            raise NotImplementedError("Pycairo not installed")
        #end if
        self.decompose \
          (
            move_to = move_to,
            line_to = line_to,
            conic_to = None,
            cubic_to = curve_to
          )
    #end draw

    def _append(self, that) :
        # appends the contours from FT.Outline that onto this one, extending the arrays appropriately.
        this_nr_contours = self._ftobj.contents.n_contours
        this_nr_points = self._ftobj.contents.n_points
        that_nr_contours = that.contents.n_contours
        that_nr_points = that.contents.n_points
        result = ct.pointer(FT.Outline())
        check(ft.FT_Outline_New
          (
            self._lib().lib,
            this_nr_points + that_nr_points,
            this_nr_contours + that_nr_contours,
            result
          ))
        libc.memcpy \
          (
            result.contents.points,
            self._ftobj.contents.points,
            this_nr_points * ct.sizeof(FT.Vector)
          )
        libc.memcpy \
          (
            ct.cast(result.contents.points, ct.c_void_p).value + this_nr_points * ct.sizeof(FT.Vector),
            that.contents.points,
            that_nr_points * ct.sizeof(FT.Vector)
          )
        libc.memcpy \
          (
            result.contents.tags,
            self._ftobj.contents.tags,
            this_nr_points * ct.sizeof(ct.c_ubyte)
          )
        libc.memcpy \
          (
            ct.cast(result.contents.tags, ct.c_void_p).value + this_nr_points * ct.sizeof(ct.c_ubyte),
            that.contents.tags,
            that_nr_points * ct.sizeof(ct.c_ubyte)
          )
        libc.memcpy \
          (
            result.contents.contours,
            self._ftobj.contents.contours,
            this_nr_contours * ct.sizeof(ct.c_short)
          )
        libc.memcpy \
          (
            ct.cast(result.contents.contours, ct.c_void_p).value + this_nr_contours * ct.sizeof(ct.c_short),
            that.contents.contours,
            that_nr_contours * ct.sizeof(ct.c_short)
          )
        result.contents.flags = self._ftobj.contents.flags # good enough?
        check(ft.FT_Outline_Done(self._lib().lib, self._ftobj))
        self._ftobj = result
    #end _append

    def append(self, other) :
        "appends the contours from Outline other onto this one, extending the arrays appropriately."
        if not isinstance(other, Outline) :
            raise TypeError("expecting another Outline")
        #end if
        self._append(other._ftobj)
    #end append

    def get_inside_border(self) :
        "returns the inside border for the Outline."
        return \
            ft.FT_Outline_GetInsideBorder(self._ftobj)
    #end get_inside_border

    def get_outside_border(self) :
        "returns the outside border for the Outline."
        return \
            ft.FT_Outline_GetOutsideBorder(self._ftobj)
    #end get_outside_border

#end Outline
def_extra_fields \
  (
    clas = Outline,
    simple_fields =
        (
            ("n_contours", "number of contours in glyph", None),
            ("n_points", "number of control points in glyph", None),
            ("flags",
                "bits that characterize the outline and give hints to the"
                " scan-converter and hinter. See FT.OUTLINE_XXX",
                None),
        ),
    struct_fields = ()
  )

class Glyph :
    "Pythonic representation of an FT.Glyph. Get one of these from GlyphSlot.get_glyph."

    __slots__ = ("_ftobj",) # to forestall typos

    def __init__(self, ftobj) :
        self._ftobj = ftobj
    #end __init__

    def __del__(self) :
        if self._ftobj != None :
            ft.FT_Done_Glyph(self._ftobj)
            self._ftobj = None
        #end if
    #end __del__

    def copy(self) :
        "returns a copy of the Glyph."
        result = FT.Glyph()
        check(ft.FT_Glyph_Copy(self._ftobj, ct.byref(result)))
        return \
            Glyph(result)
    #end copy

    def get_cbox(self, bbox_mode) :
        "returns a glyph’s control box, which contains all the curve control points."
        result = FT.BBox()
        ft.FT_Glyph_Get_CBox(self._ftobj, bbox_mode, ct.byref(result))
        return \
            (BBox.from_ft_f26_6, BBox.from_ft_int)[bbox_mode >= FT.GLYPH_BBOX_TRUNCATE](result)
    #end get_cbox

    def to_bitmap(self, render_mode, origin, replace) :
        "converts the Glyph to a BitmapGlyph, offset by the specified Vector origin." \
        " If replace, then the contents of the current Glyph is replaced; otherwise" \
        " a new Glyph object is returned. FIXME: FreeType bug? replace arg makes no" \
        " difference; the Glyph object is always replaced."
        result = ct.pointer(self._ftobj)
        check(ft.FT_Glyph_To_Bitmap(result, render_mode, ct.byref(origin.to_ft_f26_6()), int(replace)))
        if replace :
            self._ftobj = result.contents
            result = None
        else :
            result = Glyph(result.contents)
        #end if
        return \
            result
    #end to_bitmap

    @property
    def outline(self) :
        "the Outline, if format = FT.GLYPH_FORMAT_OUTLINE."
        assert self._ftobj.contents.format == FT.GLYPH_FORMAT_OUTLINE
        return \
            Outline(ct.pointer(ct.cast(self._ftobj, FT.OutlineGlyph).contents.outline), self, None)
    #end outline

    @property
    def left(self) :
        "bitmap left bearing in integer pixels (only if glyph is a bitmap)"
        assert self._ftobj.contents.format == FT.GLYPH_FORMAT_BITMAP
        return \
            ct.cast(self._ftobj, FT.BitmapGlyph).contents.left
    #end left

    @property
    def top(self) :
        "bitmap top bearing in integer pixels (only if glyph is a bitmap)"
        assert self._ftobj.contents.format == FT.GLYPH_FORMAT_BITMAP
        return \
            ct.cast(self._ftobj, FT.BitmapGlyph).contents.top
    #end top

    @property
    def bitmap(self) :
        "the Bitmap, if format = FT.GLYPH_FORMAT_BITMAP."
        assert self._ftobj.contents.format == FT.GLYPH_FORMAT_BITMAP
        return \
            Bitmap(ct.pointer(ct.cast(self._ftobj, FT.BitmapGlyph).contents.bitmap), self, None)
    #end bitmap

#end Glyph
def_extra_fields \
  (
    clas = Glyph,
    simple_fields =
        (
            ("format",
                "glyph format, typically FT.GLYPH_FORMAT_BITMAP, FT.GLYPH_FORMAT_OUTLINE"
                " or FT.GLYPH_FORMAT_COMPOSITE",
                from_tag),
            ("advance", "glyph advance width", Vector.from_ft_f16_16),
        ),
    struct_fields = ()
  )

class Bitmap :
    "Pythonic representation of an FT.Bitmap. Get one of these from GlyphSlot.bitmap," \
    " Glyph.bitmap, Outline.get_bitmap() or Bitmap.new_with_array()."
    # Seems there are no public APIs for explicitly allocating storage for one of these;
    # all the publicly-accessible Bitmap objects are owned by their containing structures.

    __slots__ = ("_ftobj", "_lib", "owner", "buffer") # to forestall typos

    def __init__(self, ftobj, owner, lib) :
        # lib is not None if I am to manage my own storage under control of FreeType;
        # owner is not None if it is the containing structure that owns my storage.
        self._ftobj = ftobj
        self.buffer = None
        assert owner == None or lib == None
        if owner != None :
            self.owner = owner # keep a strong ref to ensure it doesn’t disappear unexpectedly
            self._lib = None
        elif lib != None :
            self.owner = None
            self._lib = weakref.ref(lib)
        #end if
    #end __init__

    def __del__(self) :
        if self.buffer == None and self._lib != None and self._lib() != None :
            if self._ftobj != None :
                check(ft.FT_Bitmap_Done(self._lib().lib, self._ftobj))
                self._ftobj = None
            #end if
        #end if
    #end __del__

    @staticmethod
    def new_with_array(width, rows, pitch = None, bg = 0.0) :
        "constructs a Bitmap with storage residing in a Python array. The pixel" \
        " format is always PIXEL_MODE_GRAY."
        if pitch == None :
            if cairo == None :
                raise NotImplementedError("Pycairo not installed, cannot calculate default pitch")
            #end if
            pitch = cairo.ImageSurface.format_stride_for_width(cairo.FORMAT_A8, width)
              # simplify conversion to cairo.ImageSurface
        else :
            assert pitch >= width, "bitmap cannot fit specified width"
        #end if
        buffer = array.array("B", bytes((round(bg * 255),)) * rows * pitch)
        result = FT.Bitmap()
        ft.FT_Bitmap_New(ct.byref(result))
        result.rows = rows
        result.width = width
        result.pitch = pitch
        result.pixel_mode = FT.PIXEL_MODE_GRAY
        result.buffer = ct.cast(buffer.buffer_info()[0], ct.c_void_p)
        result.num_grays = 256
        result = Bitmap(ct.pointer(result), None, None)
        result.buffer = buffer
        return \
            result
    #end new_with_array

    def copy_with_array(self, pitch = None) :
        "returns a new Bitmap which is a copy of this one, with storage residing in" \
        " a Python array."
        src = self._ftobj.contents
        dst = FT.Bitmap()
        ft.FT_Bitmap_New(ct.byref(dst))
        for \
            attr \
        in \
            (
                "rows",
                "width",
                "pitch",
                "num_grays",
                "pixel_mode",
            ) \
        :
            setattr(dst, attr, getattr(src, attr))
        #end for
        buffer = self.to_array(pitch)
        dst.buffer = ct.cast(buffer.buffer_info()[0], ct.c_void_p)
        result = Bitmap(ct.pointer(dst), None, None)
        result.buffer = buffer
        return \
            result
    #end copy_with_array

    def to_array(self, pitch = None) :
        "returns a Python array object containing a copy of the Bitmap pixels."
        if pitch == None :
            pitch = self.pitch
        #end if
        buffer_size = self.rows * pitch
        buffer = array.array("B", b"0" * buffer_size)
        dstaddr = buffer.buffer_info()[0]
        srcaddr = ct.cast(self._ftobj.contents.buffer, ct.c_void_p).value
        src_pitch = self.pitch
        if pitch == src_pitch :
            libc.memcpy(dstaddr, srcaddr, buffer_size)
        else :
            # have to copy a row at a time
            if src_pitch < 0 or pitch < 0 :
                raise NotImplementedError("can’t cope with negative bitmap pitch")
            #end if
            assert pitch > src_pitch
            for i in range(0, self.rows) :
                libc.memcpy(dstaddr, srcaddr, src_pitch)
                dstaddr += pitch
                srcaddr += src_pitch
            #end for
        #end if
        return \
            buffer
    #end to_array

    # wrappers for FT.Bitmap functions
    # <http://www.freetype.org/freetype2/docs/reference/ft2-bitmap_handling.html>

    def copy(self, lib) :
        "returns a new Bitmap which is a copy of this one, with storage" \
        " allocated by the specified Library."
        result = ct.pointer(FT.Bitmap())
        ft.FT_Bitmap_New(result)
        check(ft.FT_Bitmap_Copy(lib.lib, self._ftobj, result))
        return \
            Bitmap(result, None, lib.lib)
    #end copy

    def embolden(self, lib, x_strength, y_strength) :
        "emboldens the bitmap by about the specified number of pixels horizontally and" \
        " vertically. lib is a Library object."
        assert self.buffer == None, "cannot embolden unless storage belongs to FreeType"
        check(ft.FT_Bitmap_Embolden
          (
            lib.lib,
            self._ftobj,
            to_f26_6(x_strength),
            to_f26_6(y_strength)
          ))
    #end embolden

    def convert(self, lib, alignment) :
        "creates and returns a new Bitmap with the pixel format converted to PIXEL_MODE_GRAY" \
        " and the specified alignment for the pitch (typically 1, 2 or 4)."
        result = ct.pointer(FT.Bitmap())
        ft.FT_Bitmap_New(result)
        check(ft.FT_Bitmap_Convert(lib.lib, self._ftobj, result, alignment))
        return \
            Bitmap(result, None, lib.lib)
    #end convert

    # end wrappers for FT.Bitmap functions

    def make_image_surface(self, copy = True) :
        "creates a Cairo ImageSurface containing (a copy of) the Bitmap pixels."
        if cairo == None :
            raise NotImplementedError("Pycairo not installed")
        #end if
        if self.pixel_mode == FT.PIXEL_MODE_MONO :
            cairo_format = cairo.FORMAT_A1
        elif self.pixel_mode == FT.PIXEL_MODE_GRAY :
            cairo_format = cairo.FORMAT_A8
        else :
            raise NotImplementedError("unsupported bitmap format %d" % self.pixel_mode)
        #end if
        src_pitch = self.pitch
        dst_pitch = cairo.ImageSurface.format_stride_for_width(cairo_format, self.width)
        if not copy and dst_pitch == src_pitch and self.buffer != None :
            pixels = self.buffer
        else :
            pixels = self.to_array(dst_pitch)
        #end if
        return \
            cairo.ImageSurface.create_for_data \
              (
                pixels,
                cairo_format,
                self.width,
                self.rows,
                dst_pitch
              )
    #end make_image_surface

#end Bitmap
def_extra_fields \
  (
    clas = Bitmap,
    simple_fields =
        (
            ("rows", "bitmap height in pixels", None),
            ("width", "bitmap width in pixels", None),
            ("pitch", "number of bytes actually occupied by each row of pixels", None),
            ("num_grays", "number of grey levels used, only if pixel_mode = FT.PIXEL_MODE_GRAY", None),
            ("pixel_mode", "see FT.PIXEL_MODE_XXX", None),
            ("palette_mode", "not used", None),
        ),
    struct_fields = ()
  )

class Stroker :
    "representation of a FreeType Stroker. Instantiate this with a Library instance."

    __slots__ = ("_ftobj", "_lib") # to forestall typos

    def __init__(self, lib) :
        if not isinstance(lib, Library) :
            raise TypeError("expecting a Library")
        #end if
        self._lib = weakref.ref(lib)
        result = ct.pointer(ct.c_void_p())
        check(ft.FT_Stroker_New(lib.lib, result))
        self._ftobj = result.contents
    #end __init__

    def __del__(self) :
        if self._ftobj != None and self._lib != None and self._lib() != None :
            ft.FT_Stroker_Done(self._ftobj)
            self._ftobj = None
        #end if
    #end __del__

    def stroke(self, glyph, replace) :
        if not isinstance(glyph, Glyph) :
            raise TypeError("expecting a Glyph")
        #end if
        result = ct.pointer(glyph._ftobj)
        check(ft.FT_Glyph_Stroke(result, self._ftobj, int(replace)))
        if replace :
            glyph._ftobj = result.contents
            result = None
        else :
            result = Glyph(result.contents)
        #end if
        return \
            result
    #end stroke

    def stroke_border(self, glyph, inside, replace) :
        if not isinstance(glyph, Glyph) :
            raise TypeError("expecting a Glyph")
        #end if
        result = ct.pointer(glyph._ftobj)
        check(ft.FT_Glyph_StrokeBorder(result, self._ftobj, int(inside), int(replace)))
        if replace :
            glyph._ftobj = result.contents
            result = None
        else :
            result = Glyph(result.contents)
        #end if
        return \
            result
    #end stroke_border

    def set(self, radius, line_cap, line_join, miter_limit) :
        ft.FT_Stroker_Set(self._ftobj, to_f16_16(radius), line_cap, line_join, to_f16_16(miter_limit))
    #end set

    def rewind(self) :
        ft.FT_Stroker_Rewind(self._ftobj)
    #end rewind

    def parse_outline(self, outline, opened) :
        if not isinstance(outline, Outline) :
            raise TypeError("expecting an Outline")
        #end if
        check(ft.FT_Stroker_ParseOutline(self._ftobj, outline._ftobj, int(opened)))
    #end parse_outline

    # TODO: FT_Stroker_BeginSubPath, FT_Stroker_EndSubPath,
    # FT_Stroker_LineTo, FT_Stroker_ConicTo, FT_Stroker_CubicTo

    def get_border_counts(self, border) :
        "returns a pair of integers (anum_points, anum_contours)."
        anum_points = ct.c_int()
        anum_contours = ct.c_int()
        check(ft.FT_Stroker_GetBorderCounts
          (
            self._ftobj,
            border,
            ct.byref(anum_points),
            ct.byref(anum_contours)
          ))
        return \
            (anum_points.value, anum_contours.value)
    #end get_border_counts

    def export_border(self, border, outline) :
        "appends the border contours onto the Outline object, extending its storage as necessary."
        assert self._lib() != None, "parent Library has gone"
        if not isinstance(outline, Outline) :
            raise TypeError("expecting an Outline")
        #end if
        nr_points, nr_contours = self.get_border_counts(border)
        temp = ct.pointer(FT.Outline())
        check(ft.FT_Outline_New(self._lib().lib, nr_points, nr_contours, temp))
        temp.contents.n_points = 0
        temp.contents.n_contours = 0
        ft.FT_Stroker_ExportBorder(self._ftobj, border, temp)
        outline._append(temp)
        check(ft.FT_Outline_Done(self._lib().lib, temp))
    #end export_border

    def get_counts(self) :
        "returns a pair of integers (anum_points, anum_contours)."
        anum_points = ct.c_int()
        anum_contours = ct.c_int()
        check(ft.FT_Stroker_GetCounts
          (
            self._ftobj,
            ct.byref(anum_points),
            ct.byref(anum_contours)
          ))
        return \
            (anum_points.value, anum_contours.value)
    #end get_counts

    def export(self, outline) :
        "appends the contours onto the Outline object, extending its storage as necessary."
        assert self._lib() != None, "parent Library has gone"
        if not isinstance(outline, Outline) :
            raise TypeError("expecting an Outline")
        #end if
        nr_points, nr_contours = self.get_counts()
        temp = ct.pointer(FT.Outline())
        check(ft.FT_Outline_New(self._lib().lib, nr_points, nr_contours, temp))
        temp.contents.n_points = 0
        temp.contents.n_contours = 0
        ft.FT_Stroker_Export(self._ftobj, temp)
        outline._append(temp)
        check(ft.FT_Outline_Done(self._lib().lib, temp))
    #end export

#end Stroker

del def_extra_fields # my job is done
