from trml2pdf import parseString, parseNode

import reportlab.rl_config
reportlab.rl_config.warnOnMissingFontGlyphs = 0

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import reportlab

enc = 'UTF-8'

#repeat these for all the fonts needed
pdfmetrics.registerFont(TTFont('Kinnari', 'Kinnari.ttf',enc))
pdfmetrics.registerFont(TTFont('Kinnari-Bold', 'Kinnari-Bold.ttf',enc))
pdfmetrics.registerFont(TTFont('Kinnari-Italic', 'Kinnari-Italic.ttf',enc))
pdfmetrics.registerFont(TTFont('Kinnari-BoldItalic', 'Kinnari-BoldItalic.ttf',enc))

pdfmetrics.registerFont(TTFont('THSarabun', 'THSarabun.ttf',enc))
pdfmetrics.registerFont(TTFont('THSarabun Bold', 'THSarabun Bold.ttf',enc))
pdfmetrics.registerFont(TTFont('THSarabun Italic', 'THSarabun Italic.ttf',enc))
pdfmetrics.registerFont(TTFont('THSarabun BoldItalic', 'THSarabun BoldItalic.ttf',enc))

from reportlab.lib.fonts import addMapping

#repeat these for all the fonts needed
addMapping('Kinnari', 0, 0, 'Kinnari') #normal
addMapping('Kinnari-Bold', 1, 0, 'Kinnari-Bold') #bold
addMapping('Kinnari-Italic', 0, 1, 'Kinnari-Italic') #italic
addMapping('Kinnari-BoldItalic', 1, 1, 'Kinnari-BoldItalic') #italic and bold

addMapping('THSarabun', 0, 0, 'THSarabun') #normal
addMapping('THSarabun Bold', 1, 0, 'THSarabun Bold') #bold
addMapping('THSarabun Italic', 0, 1, 'THSarabun Italic') #italic
addMapping('THSarabun BoldItalic', 1, 1, 'THSarabun BoldItalic') #italic and bold

#.apidoc title: RML to PDF engine

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

