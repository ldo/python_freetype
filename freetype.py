#+
# A Python 3 wrapper for FreeType <http://www.freetype.org/> using ctypes.
#
# Copyright 2015 Lawrence D'Oliveiro <ldo@geek-central.gen.nz>.
# Dual-licensed under the FreeType licence
# <http://git.savannah.gnu.org/cgit/freetype/freetype2.git/tree/docs/FTL.TXT>
# and GPLv2 <http://git.savannah.gnu.org/cgit/freetype/freetype2.git/tree/docs/GPLv2.TXT>
# or later, to be compatible with FreeType itself.
#-

from numbers import \
    Number
import enum
import ctypes as ct
import struct
import weakref

ft = ct.cdll.LoadLibrary("libfreetype.so")

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
    "useful definitions adapted from freetype.h. See the more Pythonic wrappers" \
    " defined further down in preference to accessing low-level structures directly."

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
                ("buffer", ct.POINTER(ct.c_ubyte)),
                ("num_grays", ct.c_short),
                ("pixel_mode", ct.c_byte),
                ("palette_mode", ct.c_byte),
                ("palette", ct.c_void_p),
            ]
    #end Bitmap

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

    # TODO: define an enum and represent as a set rather than an integer?
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

    # TODO: define an enum and represent as a set rather than an integer?
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
                ("horiResolution", ct.c_uint),
                ("vertResolution", ct.c_uint),
            ]
    #end Size_RequestRec
    Size_Request = ct.POINTER(Size_RequestRec)

    # TODO: define an enum and represent as a set rather than an integer?
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

#end FT

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

class Vector :
    "Pythonic representation of an FT.Vector, with conversions to/from FreeType form."

    def __init__(self, x, y) :
        "args should be float values."
        self.x = x
        self.y = y
    #end __init__

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

#end Vector
def _vector_convs() :

    def def_vector_conv(name, shift) :
        if shift != 0 :
            factor = 1 << shift
            coord_to = lambda x : round(x * factor)
            coord_from = lambda i : i / factor
        else :
            coord_to = lambda x : round(x)
            coord_from = lambda i : float(i)
        #end if
        conv_to = lambda self : FT.Vector(coord_to(self.x), coord_to(self.y))
        conv_to.__name__ = "to_ft_%s" % name
        conv_to.__doc__ = "returns an FT.Vector value representing the contents of this Vector with coordinates interpreted as %s" % name
        conv_from = lambda vec : Vector(coord_from(vec.x), coord_from(vec.y))
        conv_from.__name__ = "from_ft_%s" % name
        conv_from.__doc__ = "creates a new Vector from an FT.Vector with coordinates interpreted as %s" % name
        setattr(Vector, conv_to.__name__, conv_to)
        setattr(Vector, conv_from.__name__, staticmethod(conv_from))
    #end def_vector_conv

#begin _vector_convs
    for \
        name, shift \
    in \
        (
            ("int", 0),
            ("f16_16", 16),
            ("f26_6", 6),
        ) \
    :
        def_vector_conv(name, shift)
    #end for
#end _vector_convs
_vector_convs()
del _vector_convs

class Matrix :
    "Pythonic representation of an FT.Matrix, with conversions to/from FreeType form."

    def __init__(self, xx, xy, yx, yy) :
        "args should be float values."
        self.xx = xx
        self.xy = xy
        self.yx = yx
        self.yy = yy
    #end __init__

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

#end Matrix

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

class FTException(Exception) :
    "just to identify a FreeType-specific error exception."

    def __init__(self, code) :
        self.args = (("FreeType error %d" % code),)
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
    # “ftobj” points to the FT object to be decoded.

    def def_simple_attr(field, convert) :

        def attr(self) :
            return \
                convert(getattr(self.ftobj.contents, field))
        #end attr

    #begin def_simple_attr
        if convert == None :
            convert = lambda x : x
        #end if
        setattr(clas, field, property(attr))
    #end def_simple_attr

    def def_struct_attr(field, fieldtype, indirect, extra_decode) :

        def attr(self) :
            return \
                struct_to_dict \
                  (
                    getattr(self.ftobj.contents, field),
                    fieldtype,
                    indirect,
                    extra_decode
                  )
        #end attr

    #begin def_struct_attr
        setattr(clas, field, property(attr))
    #end def_struct_attr

#begin def_extra_fields
    for field, convert in simple_fields :
        def_simple_attr(field, convert)
    #end for
    for field, fieldtype, indirect, extra_decode in struct_fields :
        def_struct_attr(field, fieldtype, indirect, extra_decode)
    #end for
#end def_extra_fields

class Library :
    "Instantiate this to open the FreeType library. Use the new_face method to" \
    " open a font file and construct a new Face object."

    def __init__(self) :
        self.lib = ct.c_void_p(0)
        check(ft.FT_Init_FreeType(ct.byref(self.lib)))
        ver_major = ct.c_int()
        ver_minor = ct.c_int()
        ver_patch = ct.c_int()
        ft.FT_Library_Version(self.lib, ct.byref(ver_major), ct.byref(ver_minor), ct.byref(ver_patch))
        self.version = (ver_major.value, ver_minor.value, ver_patch.value)
        self.faces = weakref.WeakSet()
          # set of weak refs to child Face objects I create, to try to ensure they
          # are properly cleaned up if/when I disappear. Unfortunately circumstances
          # of invocation of __del__ methods aren’t reliable enough to avoid segfaults.
    #end __init__

    def __del__(self) :
        if self.lib.value != None :
            for face in set(self.faces) :
                face = face()
                if face != None :
                    face.__del__()
                #end if
            #end for
            ft.FT_Done_FreeType(self.lib)
            self.lib.value = None
        #end if
    #end __del__

    def new_face(self, filename, face_index = 0) :
        "loads an FT_Face from a file and returns a Face object for it."
        result_face = FT.Face()
        check(ft.FT_New_Face(self.lib, filename.encode("utf-8"), face_index, ct.byref(result_face)))
        return \
            Face(self, result_face)
    #end new_face

#end Library

class Face :
    "represents an FT_Face. Do not instantiate directly; call Library.new_face instead."

    def __init__(self, lib, face) :
        self.ftobj = face
        self._lib = weakref.ref(lib)
        lib.faces.add(self)
        facerec = ct.cast(self.ftobj, FT.Face).contents
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

    @property
    def lib(self) :
        # doesn't help with segfaults
        result = self._lib()
        assert result != None, "parent library has gone"
        return \
            result
    #end lib

    def __del__(self) :
        if self.ftobj != None :
            check(ft.FT_Done_Face(self.ftobj))
            self.ftobj = None
            self.lib.faces.remove(self)
        #end if
    #end __del__

    def select_charmap(self, encoding) :
        check(ft.FT_Select_Charmap(self.ftobj, encoding))
    #end select_charmap

    def set_charmap(self, charmap) :
        "charmap should be an element of self.charmaps"
        check(ft.FT_Set_Charmap(self.ftobj, charmap["."]))
    #end set_charmap

    def get_charmap_index(self, charmap) :
        "charmap should be an element of self.charmaps; attempting" \
        " to generalize this seems to lead to segfaults."
        return \
            ft.FT_Get_Charmap_Index(charmap["."])
    #end get_charmap_index

    def set_char_size(self, width = None, height = None, horz_resolution = None, vert_resolution = None) :
        assert \
            (
                (width != None or height != None)
            and
                (horz_resolution != None or vert_resolution != None)
            ), \
            "need to specify either width or height and either horizontal or vertical resolution"
        if width == None :
            width = height
        elif height == None :
            height = width
        #end if
        if horz_resolution == None :
            horz_resolution = vert_resolution
        elif vert_resolution == None :
            vert_resolution = horz_resolution
        #end if
        check(ft.FT_Set_Char_Size
          (
            self.ftobj,
            to_f26_6(width),
            to_f26_6(height),
            horz_resolution,
            vert_resolution,
          ))
    #end set_char_size

    def set_transform(self, matrix, delta) :
        "matrix and delta should be the Pythonic Matrix and Vector, not the FT types."
        # Note I explicitly put converted objects into local variables rather
        # than passing them straight to FT call, to ensure they don’t disappear
        # too soon
        ftmat = matrix.to_ft()
        ftdelta = delta.to_ft_f26_6() # this is a guess
        ft.FT_Set_Transform(self.ftobj, ct.byref(ftmat), ct.byref(ftdelta))
    #end set_transform

    def char_glyphs(self) :
        "generator which yields successive (char_code, glyph_code) pairs defined for" \
        " the current charmap."
        glyph_index = ct.c_uint(0)
        char_code = ft.FT_Get_First_Char(self.ftobj, ct.byref(glyph_index))
        while glyph_index.value != 0 :
            yield char_code, glyph_index.value
            char_code = ft.FT_Get_Next_Char(self.ftobj, char_code, ct.byref(glyph_index))
        #end while
    #end char_glyphs

    def get_char_index(self, charcode) :
        return \
            ft.FT_Get_Char_Index(self.ftobj, charcode)
    #end get_char_index

    def load_glyph(self, glyph_index, load_flags) :
        check(ft.FT_Load_Glyph(self.ftobj, glyph_index, load_flags))
    #end load_glyph

    def load_char(self, char_code, load_flags) :
        check(ft.FT_Load_Char(self.ftobj, char_code, load_flags))
    #end load_char

    def glyph_slots(self) :
        "generator which yields each element of the linked list of glyph slots in turn."
        glyph = self.ftobj.contents.glyph
        while True :
            yield GlyphSlot(glyph)
            try :
                glyph = glyph.contents.next
            except ValueError : # assume because of NULL pointer access
                break
            #end try
        #end while
    #end glyph_slots

    @property
    def glyph(self) :
        "returns the first or only glyph slot."
        return \
            GlyphSlot(self.ftobj.contents.glyph)
    #end glyph

    def get_kerning(self, left_glyph, right_glyph, kern_mode) :
        result = FT.Vector()
        check(ft.FT_Get_Kerning(self.ftobj, left_glyph, right_glyph, kern_mode, ct.byref(result)))
        if self.ftobj.contents.face_flags & FT.FACE_FLAG_SCALABLE != 0 and kern_mode != FT.KERNING_UNSCALED :
            result = Vector.from_ft_f16_16(result)
        else :
            result = Vector.from_ft_int(result)
        #end if
        return \
            result
    #end get_kerning

    def get_track_kerning(self, point_size, degree) :
        result = FT.Fixed(0)
        check(ft.FT_Get_Track_Kerning(self.ftobj, to_f16_16(point_size), degree, ct.byref(result)))
        return \
            from_16_16(result.value)
    #end get_track_kerning

#end Face
def_extra_fields \
  (
    clas = Face,
    simple_fields =
        (
            ("units_per_EM", None),
            ("ascender", None),
            ("descender", None),
            ("height", None),
            ("max_advance_width", None),
            ("max_advance_height", None),
            ("underline_position", None),
            ("underline_thickness", None),
        ),
    struct_fields =
        (
            ("bbox", FT.BBox, False, None),
            (
                "size", FT.SizeRec, True,
                {
                    "metrics" :
                        lambda x :
                            struct_to_dict
                              (
                                item = x,
                                itemtype = FT.Size_Metrics,
                                indirect = False,
                                extra_decode = {"x_scale" : from_f16_16, "y_scale" : from_f16_16}
                              )
                },
            ),
            ("charmap", FT.CharMapRec, True, {"encoding" : from_tag}),
        ),
  )

class GlyphSlot :
    "represents an FT.GlyphSlotRec. Do not instantiate directly;" \
    " call Face.glyph_slots or access via Face.glyph and GlyphSlot.next links instead."

    def __init__(self, ftobj) :
        self.ftobj = ftobj
    #end __init__

    @property
    def next(self) :
        try :
            result = GlyphSlot(self.ftobj.contents.next)
        except ValueError : # assume because of NULL pointer access
            result = None
        #end try
        return \
            result
    #end def

    @property
    def outline(self) :
        return \
            Outline(self.ftobj.contents.outline)
    #end outline

    def render_glyph(self, render_mode) :
        "renders the loaded glyph to a bitmap."
        check(ft.FT_Render_Glyph(self.ftobj, render_mode))
    #end render_glyph

    @property
    def bitmap(self) :
        return \
            self.ftobj.contents.bitmap # direct low-level access for now
    #end bitmap

#end GlyphSlot
def_extra_fields \
  (
    clas = GlyphSlot,
    simple_fields =
        (
            ("linearHoriAdvance", from_f16_16),
            ("linearVertAdvance", from_f16_16),
            ("format", from_tag),
            ("bitmap_left", None),
            ("bitmap_top", None),
        ),
    struct_fields =
        (
            ("advance", FT.Vector, False, {None : from_f26_6}),
            ("metrics", FT.Glyph_Metrics, False, {None : from_f26_6}),
        ),
  )

@enum.unique
class CURVEPT(enum.Enum) :
    "types of control points for outline curves."
    ON = 1 # on-curve (corner)
    OFF2 = 0 # off-curve (quadratic Bézier segment)
    OFF3 = 2 # off-curve (cubic Bézier segment)
#end CURVEPT

class Outline :
    "Pythonic representation of an FT.Outline. Get one of these from GlyphSlot.outline."
    # TODO: outline-processing functions
    # <http://www.freetype.org/freetype2/docs/reference/ft2-outline_processing.html>?

    def __init__(self, ftobj) :
        self.ftobj = ftobj
    #end __init__

    @property
    def contours(self) :
        result = []
        pointindex = 0
        for contourindex in range(0, self.ftobj.n_contours) :
            contour = []
            endpoint = self.ftobj.contours[contourindex]
            while True :
                if pointindex == self.ftobj.n_points :
                    raise IndexError("contour point index has run off the end")
                #end if
                point = self.ftobj.points[pointindex]
                flag = self.ftobj.tags[pointindex]
                pt_type = flag & 3
                for c in CURVEPT :
                    if c.value == pt_type :
                        pt_type = c
                        break
                    #end if
                #end for
                assert isinstance(pt_type, CURVEPT)
                contour.append((Vector.from_ft_int(point), pt_type, flag >> 32))
                  # interpreting coords as ints is a guess
                if pointindex == endpoint :
                    break
                pointindex += 1
            #end while
            result.append(tuple(contour))
        #end for
        return \
            tuple(result)
    #end contours

#end Outline

del def_extra_fields # my job is done
