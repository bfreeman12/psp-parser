from pdfminer.high_level import extract_pages
from pdfminer.layout import LTTextContainer
import re
from pdfminer.converter import TextConverter
from pdfminer.pdfpage import PDFPage
import json
from PIL import Image
from pytesseract import pytesseract #optical character recognition
import os #for workspace management
import glob #for getting image file paths
import fitz # for image extraction from pdfs
import multiprocessing #for parallel processing
import time # remove?
import shutil # for workspace management
import logging
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError 
import traceback
from datetime import datetime



pytesseract.tesseract_cmd = r'/usr/bin/tesseract'
aws_config = Config(
    region_name='us-gov-west-1',
    signature_version='v4',
    retries={
        'max_attempts': 10,
        'mode': 'standard'
    }
)
ec2 = boto3.client('ec2', config = aws_config)
INSTANCE_ID = os.environ.get("INSTANCE_ID") #must be exported on server

class Report_Parser:
    def __init__(self, report_file:str)-> str:
        '''
        Initialize image folder, parse the assigned report_file. Then, create an annotated pdf for SAF/AAZ.
        '''
            
        self.page_to_text_dict = dict()
        self.image_folder=f'./images/MainProcess/'
        if not os.path.exists(self.image_folder):
            os.mkdir(self.image_folder)
            self.clear_images()
        self.unable_to_extract_all_images = False
        self.extract_embedded_images(report_file)  #TODO remove left comment for deployment
        print(f'parsing {report_file}')
        self.parse_text(report_file)
        self.parse_images()
        print(self.page_to_text_dict)
        self.clear_images()
        with open('./report_data.json', 'w') as f:
            json.dump(self.page_to_text_dict, f)
        with open('./badwords.json', 'r') as f:
            self.original_bad_words = json.load(f)
        with open('./goodwords.json', 'r') as f:
            self.original_good_words = json.load(f)
        with open('./report_data.json', 'r') as f:
            self.page_to_text_dict = json.load(f)
        self.report = fitz.open(report_file)
        this_reports_checkboxes = self.find_checkboxes(self.page_to_text_dict)
        this_reports_bad_checkboxes = self.get_bad_checkboxes(this_reports_checkboxes)
        self.interview_pages =  self.find_interview_pages(self.page_to_text_dict)
        self.comment_bad_words(report_file)
        self.comment_bad_checkboxes(this_reports_bad_checkboxes)
        if not self.unable_to_extract_all_images:
            self.report.save(f'./processed_packages/annotated_{report_file.split("packages/")[1]}')
        else:
            self.report.save(f'./processed_packages/partially_annotated_{report_file.split("packages/")[1]}')
        self.report.close()
        shutil.rmtree(self.image_folder)
        os.remove(report_file) #TODO remove left comment for deployment

    def comment_bad_checkboxes(self, bad_checkboxes) -> None:
        for page in bad_checkboxes:
            page_number = re.search('[0-9]+', page).group()
            print(page_number)
            annotated = []
            page_number = int(page_number)-1
            for checkbox in bad_checkboxes[page]:
                #Try to get matches with real text
                matches = self.report[page_number].search_for(checkbox)
                for match in matches:
                    print(match, page_number)
                    this_page = self.report[page_number]
                    annot = this_page.add_rect_annot(match)
                    self.report[page_number].reload_page()
                    annot.set_border({'dashes': [2], 'width': 0.2})
                    annot.set_colors({'stroke': (0, 0, 1)})
                    info = annot.info
                    info['title'] = f'Checkbox Match'
                    info['content'] = f'Checkbox Match {match} potentially derogatory'
                    annot.set_info(info)
                    annot.update()
                    self.report[page_number].reload_page()
                    annotated.extend(checkbox)
            if len(annotated) < len(bad_checkboxes[page]): #if some of the checkboxes were in pictures
                checkboxes_in_images= [x for x in bad_checkboxes[page] if x not in annotated]
                for checkbox in checkboxes_in_images:
                    this_page = self.report[page_number]
                    annot = this_page.add_rect_annot(fitz.Rect(300, 300, 350, 350))
                    annot.set_border({'dashes': [2], 'width': 0.2})
                    annot.set_colors({'stroke': (0, 0, 1)})
                    info = annot.info
                    info['title'] = f'Checkbox match'
                    info['content'] = f"Checkbox {checkbox} potentially derogatory.\nCouldn't get the exact location"
                    annot.set_info(info)
                    annot.update()
                

            
    def find_interview_pages(self, data) -> list:
        '''This def finds the pages in the report with interview data / fbi investigation data'''
        #TODO other is too broad
        report_pages = []
        for key in data:
            data[key]= [" ".join(data[key])]
            
            print(f'page {key} {re.search( "CASE +#[:]? +[0-9]+", data[key][0])}')
            if re.search( "CASE +#[:]? +[0-9]+", data[key][0]):
                report_pages.append(key)
        return report_pages

    def no_case_regex_generator(self, ambiguous_string) -> str:
        regex_string=[]
        for character in ambiguous_string:
            if re.search('[a-zA-Z]', character):
                regex_string=f'{regex_string}[{character.upper()}{character.lower()}]'
            else:
                regex_string= f'{regex_string}{character}'
        regex_string=f"\\b{regex_string}\\b"

        return regex_string

    def process_initializer(self):
        print(f'Starting {multiprocessing.current_process().name}')


    def find_checkboxes(self, data) -> dict:
        for key in data:
            data[key]= [" ".join(data[key])]
        master_dict={}
        for page in data:
            print(f'Extracting checkboxes from {page}')
            master_list=re.finditer('{ *[xX]? *}', data[page][0])

            nos=re.finditer('[Nn][Oo]: *{ *[xX]? *}|[Yy][Ee][Ss]: *{ *[xX]? *}', data[page][0])

            def get_end(match):
                return match.end()

            yes_no_ends =list(map(get_end, nos))
            all_ends =list(map(get_end, master_list))
            checkboxes= {
                            "yes/no":{},
                            "others":{}
                        }
            counter = 0
            for i in re.finditer('{ *[xX]? *}', data[page][0]):
                if not i.end() in yes_no_ends: #other kinds of checkboxes
                    counter+=1
                    '''
                    others
                    |question #
                    ||context
                    ||responses
                    ||checked
                    ||match_object
                    '''
                    checkboxes['others'].update({f'question {counter}' : {'responses':i.group(), 'match_object':i}})
                    if 'x' in i.group():
                        checkboxes['others'][f'question {counter}'].update({'checked':'yes'})
                    else:
                        checkboxes['others'][f'question {counter}'].update({'checked':'no'})
                    this_index = all_ends.index(i.end())
                    if this_index < 1:
                        previous_question = 0
                    else:
                        previous_question = all_ends[this_index-1]
                    question_start =  i.start()
                    checkboxes['others'][f'question {counter}'].update({'context':data[page][0][previous_question:question_start]})


            for q in range(int(len(yes_no_ends)/2)):
                    print(data[page][0])
                    print(len(yes_no_ends), yes_no_ends)
                    checkboxes['yes/no'].update({f'question {q}':{'responses':[], 'match_object':[]}})
            for i in re.finditer('[Nn][Oo]: *{ *[xX]? *}|[Yy][Ee][Ss]: *{ *[xX]? *}', data[page][0]): #yes no checkboxes
                if not f'question {int(yes_no_ends.index(i.end())/2)}' in checkboxes['yes/no'].keys(): #unbalanced yes/no
                    checkboxes['yes/no'].update({f'question {int(yes_no_ends.index(i.end())/2)}':{
                        'match_object':[i,i],
                        'responses': [i.group()],
                        'possible error':'yes',
                        'checked':'no'
                        }
                    })
                    
                else:
                    checkboxes['yes/no'][f'question {int(yes_no_ends.index(i.end())/2)}']['match_object'].append(i)
                    checkboxes['yes/no'][f'question {int(yes_no_ends.index(i.end())/2)}']['responses'].append(i.group())
                if 'x' in i.group() or 'X' in i.group():
                    checkboxes['yes/no'][f'question {int(yes_no_ends.index(i.end())/2)}'].update({
                    'checked': i.group().split(':')[0] })
                elif not 'checked' in checkboxes['yes/no'][f'question {int(yes_no_ends.index(i.end())/2)}'].keys():
                    checkboxes['yes/no'][f'question {int(yes_no_ends.index(i.end())/2)}'].update({
                        'checked':'N/A' })
            for i, q in enumerate(checkboxes['yes/no']):
                this_index = all_ends.index(min([checkboxes['yes/no'][q]['match_object'][0].end(), checkboxes['yes/no'][q]['match_object'][1].end()]))
                if this_index <1:
                    previous_question = 0
                else:
                    previous_question = all_ends[this_index-1]
                question_start =  min([checkboxes['yes/no'][q]['match_object'][0].start(), checkboxes['yes/no'][q]['match_object'][1].start()])

                checkboxes['yes/no'][q].update({'context':data[page][0][previous_question:question_start]})


            for i in checkboxes['others']:
                checkboxes['others'][i].pop('match_object')
            for i in checkboxes['yes/no']:
                checkboxes['yes/no'][i].pop('match_object')
            master_dict.update({f'Page {page}':checkboxes})
        return master_dict

    
    def get_bad_checkboxes(self, checkbox_data) -> dict:
        '''This method searches the two different kinds of checkboxes that may be extracted by the method find_checkboxes
        for derogatory information. Bad checkboxes are selected based on whether a "good" response is yes/no/other checked
        or not.

        It outputs a dictionary of 
                                page number : ["bad checkbox match", ...]
        '''

        output = {}
        with open('checkboxes.json') as f:
            bad_checkboxes = json.load(f)
        for page in checkbox_data:
            output.update({ page : [] })
            for checkbox_type in checkbox_data[page]:
                for checkbox in checkbox_data[page][checkbox_type].values():
                    print(checkbox)
                    if re.search("yes/no",checkbox_type):
                        if re.search('[Yy][Ee][Ss]', checkbox['checked']):
                            selected_bad_checkboxes = [k for k, v in bad_checkboxes['yes/no'].items() if v == 'yes']
                            for i in selected_bad_checkboxes:
                                match = re.search(i, checkbox['context'])
                                if match:
                                    output[page].extend(match.group())
                                    print(f'{i} in {checkbox}')
                        else:
                            selected_bad_checkboxes = [k for k, v in bad_checkboxes.items() if v == 'no']
                            for i in selected_bad_checkboxes:
                                match = re.search(i, checkbox['context'])
                                if match:
                                    output[page].extend(match.group())
                                    print(f'{i} in {checkbox}')
                    else:
                        #TODO others bad checkbox selecting
                        if checkbox['checked'] == 'yes':
                            selected_bad_checkboxes = [k for k, v in bad_checkboxes['others'].items() if v == 'yes']
                            for i in selected_bad_checkboxes:
                                match = re.search(i, checkbox['context'])
                                if match:
                                    output[page].extend([match.group()])
                            pass
                        else:
                            selected_bad_checkboxes = [k for k, v in bad_checkboxes['others'].items() if v == 'no']
                            for i in selected_bad_checkboxes:
                                match = re.search(i, checkbox['context'])
                                if match:
                                    output[page].extend([match.group()])
                            pass
            output= {k:v for k,v in output.items() if len(v)>0}
        return output

    

    def comment_bad_words(self, report_file:str) -> None:
        '''Use PyMuPDF to add comments to individual reports to help with SAF/AAZE indexing. '''
        # Comments real text. Modified from https://www.educative.io/courses/pdf-management-python/B8pGNP0loDQ 

        comments_already_added = {}
        with open('country_list.json') as country_file:
            countries =json.load(country_file)
        bad_words = self.original_bad_words["bad_words"]
        for word in bad_words:
            print(word)
            comments_already_added = []
            for pg, page in enumerate(self.report):
                pageID = pg+1
                add_comment_flag = True
                bad_word_matches = page.search_for(f' {word} ')
                #print(f'{str(pageID)} in interview_pages : {str(pageID) in self.interview_pages}')
                if str(pageID) in self.interview_pages:
                    for phrase in [x for x in self.original_good_words["investigation_phrases"] if re.search(self.no_case_regex_generator(word),x)]:
                        if page.search_for(phrase):
                            add_comment_flag=False
                            print(f'Comment set to {add_comment_flag}. Word {word} Page {pageID}')
                    
                    if bad_word_matches and add_comment_flag:
                        print(bad_word_matches)
                        for match in bad_word_matches:
                            annot = page.add_rect_annot(match)
                            annot.set_border({'dashes': [2], 'width': 0.2})
                            annot.set_colors({'stroke': (0, 0, 1)})
                            info = annot.info
                            info['title'] = f'Word Match'
                            info['content'] = f'Matched "{word}"'
                            annot.set_info(info)
                            annot.update()
                            comments_already_added.append(str(pageID))
            
            # Comment image's pages with bad words
            pages_with_bad_words = [p for p, v in self.page_to_text_dict.items() if 
                [k for k in v if re.search(self.no_case_regex_generator(word),k)]]
            pages_with_bad_words = [item for item in pages_with_bad_words if item in self.interview_pages]
            
            for page in comments_already_added:
                print(page, pages_with_bad_words)
                if str(page) in pages_with_bad_words:
                    pages_with_bad_words.remove(str(page))
            possible_false_flags =[]
            for p in self.original_good_words["investigation_phrases"]:
                if re.search(word, p, flags=re.I):
                    possible_false_flags.append(p)
            for page in pages_with_bad_words:
                for possible in possible_false_flags:
                    print(self.no_case_regex_generator(possible), word)
                    for sentence in self.page_to_text_dict[page]:
                        if re.search(self.no_case_regex_generator(possible), sentence):
                            while page in pages_with_bad_words:
                                pages_with_bad_words.remove(page)
                        

            print('pages to add comments to ', pages_with_bad_words)
            
            for pg, page in enumerate(self.report):
                if str(pg+1) in pages_with_bad_words:
                    annot = page.add_rect_annot(fitz.Rect(300, 300, 350, 350))
                    annot.set_border({'dashes': [2], 'width': 0.2})
                    annot.set_colors({'stroke': (0, 0, 1)})
                    info = annot.info
                    info['title'] = f'Word Match'
                    info['content'] = f"Matched '{word}'\nCouldn't get the exact location"
                    annot.set_info(info)
                    annot.update()
        for country in countries.values():
            pages_with_bad_words=[p for p, v in self.page_to_text_dict.items() if 
                    [k for k in v if re.search(self.no_case_regex_generator(country),k)]]
            print(f'pages with {country} || {pages_with_bad_words}')
            for pg, page in enumerate(self.report):
                    if str(pg+1) in pages_with_bad_words:
                        annot = page.add_rect_annot(fitz.Rect(300, 300, 350, 350))
                        annot.set_border({'dashes': [2], 'width': 0.2})
                        annot.set_colors({'stroke': (0, 0, 1)})
                        info = annot.info
                        info['title'] = f"Match '{country}'"
                        info['content'] = "Couldn't get the exact location"
                        annot.set_info(info)
                        annot.update()       
        
        

        return f'./processed_packages/annotated_{report_file.split("packages/")[1]}'

    def clear_images(self) -> None:
        '''Removes images in the workspace so that data doesn't bleed across reports'''
        files = glob.glob(f'{self.image_folder}/*.png')
        for f in files:
            try:
                os.remove(f)
            except:
                pass
        return

    def parse_text(self, file_path) -> None:
        '''Update dictionary with paragraphs/text with all of the parsed lines of 'real' text in a report'''

        with open(file_path, 'rb') as f:
            for page_layout in extract_pages(f):
                self.page_to_text_dict.update({page_layout.pageid:[]})
                print(f"Extracting page {page_layout.pageid}")
                for element in page_layout:
                    if isinstance(element, LTTextContainer):
                        element_info=element
                        element=element.get_text()
                        for line in element_info:
                            line_text =line.get_text()
                            self.page_to_text_dict[page_layout.pageid].append(line_text)

        return

    def parse_images(self) -> None:
        '''Extracted text from every image in "./images/Main Process/"'''
        # #TODO remove LONG comment for deployment
        files = glob.glob(f'{self.image_folder}*.png')
        try:    #16 processes
            print(f'{multiprocessing.cpu_count()/2}')
            pool_size = int(multiprocessing.cpu_count()/2)
            pool = multiprocessing.Pool(processes=pool_size,
                                        initializer=self.process_initializer,
                                        maxtasksperchild=2,
                                        )
            pool_outputs = pool.map(self.parallel_image_processor,  files)
            pool.close() # no more tasks
            pool.join()  # wrap up current tasks
            
        except:
            
            print(f"Exception, trying 10 workers")
            pool_size = 10
            pool = multiprocessing.Pool(processes=pool_size,
                                        initializer=self.process_initializer,
                                        maxtasksperchild=2,
                                        )
            pool_outputs = pool.map(self.parallel_image_processor, files)
            pool.close() # no more tasks
            pool.join()  # wrap up current tasks
        pool_dicts={}
        for i in pool_outputs:
            print(i)
            pool_dicts.update(i)
        with open('./image_data.json', 'w') as f:
            json.dump(pool_dicts, f)
        with open('./image_data.json', 'r') as f:
            pool_outputs=json.load(f)
        
        for key in pool_outputs.keys():
            if not key in self.page_to_text_dict.keys():
                self.page_to_text_dict.update({key:[]})
            if not isinstance( self.page_to_text_dict[key], list):
                self.page_to_text_dict[key]
            self.page_to_text_dict[key].extend(pool_outputs[key])
        return

    
    def parallel_image_processor(self, file_path) -> dict:
        '''This function uses computer vision and optical character recognition to extract text from images. It is 
        tasked images by a Process pool.
        
        Inputs:
        file_path (str) : The file path of a specific image assigned to the subprocess that called it

        Ouput:
        dict of page (key) to paragraphs (value)

        '''
        if  isinstance(file_path, str):
            print(f"Processing {file_path}")
            img = Image.open(file_path)
            
            result = pytesseract.image_to_string(img, lang="eng")
            #Split paragraphs

            paragraphs = result.splitlines()
            page = int(file_path[re.search('ss/',file_path).end():re.search('-',file_path).start()])         
            print(f"Parsed {file_path}")
        return {page:paragraphs}

    def extract_embedded_images(self, file_path) -> None:
        '''Saves .PNG files extracted from the report to ./images. Returns None'''
        doc = fitz.Document(file_path)
        image_counter = 0
        for i in range(len(doc)):
            for img in doc.get_page_images(i):
                image_counter+=1
                print(f'image counter {image_counter}\nextracting page {i+1} image xref {img[0]}')
                xref = img[0]
                pix = fitz.Pixmap(doc, xref)
                try:
                    pix= fitz.Pixmap(fitz.csRGB, pix)
                except:
                    print('Exception in image extraction')
                    pass
                if pix.n < 5:       # this is GRAY or RGB
                    pix.save("%s%s-%s.png" % (self.image_folder,i+1, xref))
                else:               # CMYK: convert to RGB first
                    pix1 = fitz.Pixmap(fitz.csRGB, pix)
                    pix1.save("%s%s-%s.png" % (self.image_folder,i+1, xref))
                    pix1 = None
                pix = None
            if image_counter > 5000:
                self.unable_to_extract_all_images = True
                return
        return

def list_objects_in_psp_bucket(client, bucket) -> list:
    response = client.list_objects_v2(Bucket=bucket)
    print(response.get('Contents'))
    return [key['Key'] for key in response.get('Contents') if re.search('^unprocessed_packages/', key['Key']) and not key['Key'] == 'unprocessed_packages/']

def upload_parsed_package_to_bucket(client, bucket) -> None:
    files=glob.glob('./processed_packages/*')
    
    for fp in files:
        print(fp)
        try:
            with open(fp, "rb") as f:
                client.upload_fileobj(f, bucket, fp[2:])
            os.remove(fp)
            #logging.info(f'Uploaded {fp} to the bucket')
        except:
            pass
            #logging.warning(f'Failure when attempting to upload {fp} to the bucket')
        

def delete_processed_report(client, bucket, item_key) ->None:
    try:
        os.remove(f'{item_key}')
        #logging.info(f'Removed {item_key} from the server')
    except:
        pass
        #logging.warning(f'Failure when attempting to remove {item_key} from the server')
    try:
        response = client.delete_object(Bucket=bucket, Key=item_key)
        print(response) #TODO
        logging.info(f'Removed {item_key} from the bucket')
    except:
        logging.warning(f'Failure when attempting to remove {item_key} from the bucket\n')
        traceback.print_exc()

def download_from_bucket(client, key, bucket) -> None:
    client.download_file(bucket, key, f'./unprocessed_packages/{key.split("packages")[1]}')
    #logging.info(f'Downloaded {key}')
    return


def update_good_words_list(client,bucket):
    try:
        last_updated = os.path.getmtime(r'goodwords.json')
        last_updated_string = time.ctime(last_updated)
        last_updated_formatted = datetime.strptime(
            last_updated_string, "%a %b %d %H:%M:%S %Y")
        head_object = client.head_object(Bucket=bucket, Key='words/goodwords.json')
        head_object_modified_time = head_object['ResponseMetadata']['HTTPHeaders']['last-modified']
        head_object_formatted = datetime.strptime(
            head_object_modified_time, "%a, %d %b %Y %H:%M:%S %Z")
        if head_object_formatted >= last_updated_formatted:  # newer
            client.download_file(bucket, '/words/goodwords.json', 'goodwords.json')
        else:
            pass
    except Exception as e:
        print(e)


def update_bad_words_list(client,bucket):
    try:
        last_updated = os.path.getmtime(r'badwords.json')
        last_updated_string = time.ctime(last_updated)
        last_updated_formatted = datetime.strptime(
            last_updated_string, "%a %b %d %H:%M:%S %Y")
        head_object = client.head_object(Bucket=bucket, Key='words/badwords.json')
        head_object_modified_time = head_object['ResponseMetadata']['HTTPHeaders']['last-modified']
        head_object_formatted = datetime.strptime(
            head_object_modified_time, "%a, %d %b %Y %H:%M:%S %Z")
        if head_object_formatted >= last_updated_formatted:  # newer
            client.download_file(bucket, '/words/badwords.json', 'badwords.json')
        else:
            pass
    except Exception as e:
        print(e)



def task_parsers() -> None:
    '''Listen for unprocessed packages and task parser with individual package. 
    Logs the amount of time it takes for individual packages to parse.'''
    s3 = boto3.client('s3', config=aws_config)
    bucket = "psp-report-bucket"
    idle_cycles = 0
    while True:
        update_bad_words_list(client=s3,bucket=bucket)
        update_good_words_list(client=s3,bucket=bucket)
        files = glob.glob('./unprocessed_packages/*.pdf')
        for i in files:
            os.remove(i)
        files = list_objects_in_psp_bucket(s3, bucket)
        print(files)
        #logging.info(f'Found {len(files)} objects in the PSP bucket:\n{files}')
        if len(files) > 0:
            for f in files: 
                download_from_bucket(client=s3, key=f, bucket=bucket)
                starttime=time.time()
                Report_Parser(f'./{f}')
                #logging.info(f'Processing package "{f}" took {(time.time() - starttime)/60} minutes')
                print(f'Processing package "{f}" took {(time.time() - starttime)/60} minutes')
                upload_parsed_package_to_bucket(s3, bucket)
                delete_processed_report(s3, bucket, f)
        idle_cycles+=1
        if idle_cycles > 60: #60 = five minutes
            stop_this_instance() 
        time.sleep(5)

def stop_this_instance()->None:
    try:
        ec2.stop_instances(InstanceIds=[INSTANCE_ID], DryRun=False)
    except ClientError as e:
        print(e)

### Daemon Begin ###
#logging.basicConfig(filename='parser.log', level=logging.DEBUG)
task_parsers()
