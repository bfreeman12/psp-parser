import re
import json
from pytesseract import pytesseract 
import glob
import fitz
from PIL import Image

pytesseract.tesseract_cmd = r'/usr/bin/tesseract'

image_folder=f'./images/test/'

def extract_embedded_images( file_path) -> None:
        '''Saves .PNG files extracted from the report to ./images. Returns None'''
        doc = fitz.Document(file_path)

        for i in range(len(doc)):
            for img in doc.get_page_images(i):
                print(f'extracting page {i+1} image {img[0]}')
                xref = img[0]
                pix = fitz.Pixmap(doc, xref)
                try:
                    pix= fitz.Pixmap(fitz.csRGB, pix)
                except:
                    print('Exception in image extraction')
                    pass
                if pix.n < 5:       # this is GRAY or RGB
                    pix.save("%s%s-%s.png" % (image_folder,i+1, xref))
                else:               # CMYK: convert to RGB first
                    pix1 = fitz.Pixmap(fitz.csRGB, pix)
                    pix1.save("%s%s-%s.png" % (image_folder,i+1, xref))
                    pix1 = None
                pix = None
        return

def get_word_bbox(word, image):
    image=Image.open(f'{image}')
    result = pytesseract.image_to_data(image, lang='eng')
    
    return result



extract_embedded_images('./test.pdf')
files = glob.glob(f'{image_folder}*.png')
for f in files:
    print(get_word_bbox('bad', image=f))