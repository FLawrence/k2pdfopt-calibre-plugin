#!/usr/bin/env python
# ~*~ coding: utf-8 ~*~
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2024, Ahmed Zaki <azaki00.dev@gmail.com>'
__docformat__ = 'restructuredtext en'

autocrop = '''Auto crop.  For books or papers that have dark edges
due to copying artifacts, this option will attempt to
automatically crop out those dark regions so that k2pdfopt
can correctly process the source file.'''

autostraighten = '''Attempt to automatically straighten tilted source pages.'''

break_after = '''Break output pages at end of each input
page'''

max_cols = '''Set max number of columns.  <maxcol> can be 1, 2, or 4.
Default is -col 2.  -col 1 disables column searching.'''

color = '''Output in color.  Default is grayscale.'''

cover_image = '''page number to user a cover image for the first page of
the converted PDF. Can be usefull if the cover is not converted pages
and you want to insert again at the beginning'''

drf = '''Display resolution multiplier.  Default = 1.0.  Using a
value greater than 1 should improve the resolution of the
output file (but will make it larger in file size).
E.g. -dr 2 will double the output DPI, the device width
(in pixels), and the device height (in pixels)'''

erase_vl = '''Detects and erases vertical lines in the source document
which may be keeping k2pdfopt from correctly separating
columns or wrapping text, e.g. column dividers.'''

erase_hl = '''Detects and erases horizontal lines in the source document
which may be keeping k2pdfopt from correctly wrapping text.'''

font_size = '''The output document is scaled so that the median font size in
the converted file is <points> points.'''

landscape = '''Set output to be in landscape mode.'''

modes = '''Shortcut for setting multiple options at once which
determine the basic way in which k2pdfopt will behave.
Available modes are:
    Copy             "Copy" mode.  This isn't really intended for
                     use with an e-reader.  It just creates a
                     bitmapped copy of your source document at the
                     exact same dimensions.  This can be useful in
                     order to eliminate any font compatibility
                     issues or if you want to eliminate selectable
                     text (follow with -mode copy with -ocr-).
    Fit Page        "Fit Page" mode.  Also can use -mode fitpage.
                     Fits the entire contents of each source page
                     onto the reader display.
    Fit Width       "Fit Width" mode.  Fits the text to the width
                     of the reader in landscape mode without doing any
                     text re-flow.  This is the best way to preserve
                     the original layout of the source document.
                     To fit to the reader width in portrait mode, add
                     -ls- after -mode fw to turn off landscape.
    2 Columns       "Two-column" mode.  Optimizes for a 2-column scientific
                     article with native PDF output.
    Trim Margins     "Trim margins" mode.  Same as -mode copy, but
                     sets the output to be trimmed to the margins and
                     the width and height of the output to match the
                     trimmed source pages.  Also uses native mode.
    Crop             "Crop" mode.  Used with the -cbox option, this
                     puts each cropped area on a separate page,
                     untrimmed, and sizes the page to the cropped
                     region.
    Concat           "Concatenation" mode.  Similar to -mode crop,
                     but keeps the output pages the same size as the
                     source pages and fits as many crop-boxed regions
                     onto each new output page as possible without
                     breaking them across pages.
    Defualt         "Default" mode. This is the mode you get if you
                     run k2pdfopt with no customized options.'''


native = '''Use "native" PDF output format.  NOTE: if you want native
PDF output, it's probably best to use a -mode option like
-mode fitwidth or -mode 2col, both of which automatically
turn on native PDF output and optimize other settings for it.
Native PDF output preserves the native source PDF contents,
i.e. the output PDF file is not rendered as a sequence of
bitmapped pages like in the default k2pdfopt output mode.
Instead, the source PDF's native content is used along with
additional PDF instructions to translate, scale, and crop
the source content.  With native PDF output, if the source
file has selectable text, the text remains selectable in
the output file.  The output file can also be zoomed
without loss of fidelity.  This may also result in a
smaller output file (but not always).  By default, native
PDF output format is turned off.'''

ocr = '''Attempt to use optical character
recognition (OCR) in order to embed searchable text into
the output PDF document.'''

pages = '''Specify pages to convert.  <pagelist> must not have any
spaces.  E.g. -p 1-3,5,9,10- would do pages 1 through 3,
page 5, page 9, and pages 10 through the end.  The letters
'e' and 'o' can be used to denote even and odd pages, e.g.
    -p o,e        Process all odd pages, then all even ones.
    -p 2-52e,3-33o    Process 2,4,6,...,52,3,5,7,...,33.'''

rtl = '''Right-to-left page scans'''

reflow = '''Enable text wrapping. Text wrapping disables native PDF output'''

cmdopts = '''Command line options. All options here will have precedence over
similar options specified through GUI.
Supports calibre template language (when invoked inside calibre)'''
