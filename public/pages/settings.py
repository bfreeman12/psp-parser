from dash.dependencies import Input, Output
from dash import dcc, html
import json
from app import app
from botocore.config import Config
import boto3

my_config = Config(
    region_name='us-gov-west-1',
    signature_version='v4',
    retries={
        'max_attempts': 10,
        'mode': 'standard'
    }
)
s3 = boto3.client('s3',
                  config=my_config,
                  )

S3 = boto3.resource('s3')
bucket = "bucket"

layout = html.Div([
    html.Div(id='settings-wrapper',children=[
    html.Div(className='settings-block',
             children=('View or edit known bad words or phrases ', html.Button('Edit', id='bad-editor-button', n_clicks=0),),),
    html.Div(className='settings-block',
             children=('View or edit known good words or phrases ', html.Button('Edit', id='good-editor-button', n_clicks=0),),),
    html.Div(className='settings-block',
             children=('View or edit known good checkboxes ', html.Button('Edit', id='check-box-button', n_clicks=0),),),
    html.Div(className='settings-block', id='bad-list-div',
             children=''),
    html.Div(className='settings-block', id='good-list-div',
             children=''),
    html.Div(className='settings-block', id='check-box-div',
             children=''),
    html.Div(className='hidden-div', id='placeholder-div', children=''),
    html.Div(className='hidden-div', id='placeholder-div_2', children=''),
    html.Div(className='hidden-div', id='placeholder-div_3', children=''),
])])

# this callback will open the json file and display it to a text box
# if file does not exist, it will create it with the correct format


@ app.callback(
    Output('bad-list-div', 'children'),
    Input('bad-editor-button', 'n_clicks')
)
def bad_list_editor(n_clicks):
    if n_clicks > 0:
        try:
            f = open(r'assets/badwords.json')
            jsonlist = json.load(f)
            f.close()
            jsonstring = ', '.join(str(word)for word in jsonlist['bad_words'])
            return html.Div(children=[html.H5('Please seperate each BAD word or phrase with a comma. (ex. word1, word2)',style={'overflow':'hidden'}), dcc.Textarea(style={'width': '100%', 'height': '20vh', 'overflowY': 'auto'}, id='bad_text_area', value=jsonstring), html.Button('Save', id='bad-word-save-button', n_clicks=0, style={'textDecoration': 'none', 'border': 'none', 'backgroundColor': 'rgba(200, 200, 200, 0.8)', 'borderRadius': '5px', 'width': '5vw', 'float': 'right'}), ])
        except FileNotFoundError:
            f = open(r'assets/badwords.json', 'w+')
            initial_bad_list = {'bad_words': []}
            json.dump(initial_bad_list, f, indent=4)


@ app.callback(
    Output('placeholder-div', 'children'),
    Input('bad-word-save-button', 'n_clicks'),
    Input('bad_text_area', 'value')
)
def save_bad_word_list(n_clicks, value):
    if n_clicks > 0:
        stripped_string = value.strip()
        stripped_string_to_list = stripped_string.split(', ')
        new_json = {'bad_words': []}
        new_json['bad_words'] += stripped_string_to_list
        with open(r'assets/badwords.json', 'w') as f:
            json.dump(new_json, f, ensure_ascii=False, indent=4)
        s3.upload_file(f'./assets/badwords.json',
                       bucket, f'words/badwords.json')
        return dcc.Location(id='url', href='/settings', refresh=True)


@ app.callback(
    Output('good-list-div', 'children'),
    Input('good-editor-button', 'n_clicks')
)
def good_list_editor(n_clicks):
    if n_clicks > 0:
        try:
            f = open(r'assets/goodwords.json')
            jsonlist = json.load(f)
            f.close()
            jsonstring = ', '.join(str(word)for word in jsonlist['investigation_phrases'])
            return html.Div(children=[html.H5('Please seperate each GOOD word or phrase with a comma. (ex. word1, word2)',style={'overflow':'hidden'}), dcc.Textarea(style={'width': '100%', 'height': '20vh', 'overflowY': 'auto'}, id='good_text_area', value=jsonstring), html.Button('Save', id='good-word-save-button', n_clicks=0, style={'textDecoration': 'none', 'border': 'none', 'backgroundColor': 'rgba(200, 200, 200, 0.8)', 'borderRadius': '5px', 'width': '5vw', 'float': 'right'}), ])
        except FileNotFoundError:
            f = open(r'assets/goodwords.json', 'w+')
            initial_good_list = {'investigation_phrases': []}
            json.dump(initial_good_list, f, indent=4)


@ app.callback(
    Output('placeholder-div_2', 'children'),
    Input('good-word-save-button', 'n_clicks'),
    Input('good_text_area', 'value')
)
def save_good_word_list(n_clicks, value):
    if n_clicks > 0:
        stripped_string = value.strip()
        stripped_string_to_list = stripped_string.split(', ')
        new_json = {'investigation_phrases': []}
        new_json['investigation_phrases'] += stripped_string_to_list
        with open(r'assets/goodwords.json', 'w') as f:
            json.dump(new_json, f, ensure_ascii=False, indent=4)
        s3.upload_file(f'./assets/goodwords.json',
                       bucket, f'words/goodwords.json')
        return dcc.Location(id='url', href='/settings', refresh=True)

@ app.callback(
    Output('check-box-div', 'children'),
    Input('check-box-button', 'n_clicks')
)
def check_box_editor(n_clicks):
    if n_clicks > 0:
        try:
            f = open(r'assets/checkboxes.json')
            jsonlist = json.load(f)
            f.close()

            other_str = ''
            for key, value in jsonlist['others'].items():
                other_str += key + ' : ' + value + ' ,'
            other_str = other_str.rstrip(other_str[-1])

            #reads through the json and presents the data in user friendly format
            yes_no_str = ''
            for key, value in jsonlist['yes/no'].items():
                yes_no_str += key + ' : ' + value + ' ,'
            yes_no_str = yes_no_str.rstrip(yes_no_str[-1])


            return html.Div(children=[html.H5('Please seperate each question and answer with a comma (ex. word1 : Yes, word2 : No)',style={'overflow':'hidden'}),html.H5('Enter yes or no questions to be whitelisted below',style={'overflow':'hidden'}), dcc.Textarea(style={'width': '100%', 'height': '20vh', 'overflowY': 'auto'}, id='check_box_text_area_yes_no', value=yes_no_str), html.H5('Other questions',style={'overflow':'hidden'}),dcc.Textarea(style={'width': '100%', 'height': '20vh', 'overflowY': 'auto'}, id='check_box_text_area_others', value=other_str), html.Button('Save', id='check-box-save-button', n_clicks=0, style={'textDecoration': 'none', 'border': 'none', 'backgroundColor': 'rgba(200, 200, 200, 0.8)', 'borderRadius': '5px', 'width': '5vw', 'float': 'right'}), ])
        except FileNotFoundError:
            f = open(r'assets/checkboxes.json', 'w+')
            initial_good_list = {'others': [],'yes/no':[]}
            json.dump(initial_good_list, f, indent=4)
@ app.callback(
    Output('placeholder-div_3', 'children'),
    Input('check-box-save-button', 'n_clicks'),
    Input('check_box_text_area_others', 'value'),
    Input('check_box_text_area_yes_no', 'value')
)
def save_good_word_list(n_clicks, others,yes_no):
    if n_clicks > 0:
        #formatting others
        end_json = {'others': {},'yes/no':{}}
        print(others)
        print('\n'+yes_no)
        others_new = others
        others_res = dict(item.split(":") for item in others_new.split(" ,"))
        
        end_json['others'] = others_res

        #formatting yes no
        yes_no_res = dict(item.split(":") for item in yes_no.split(" ,"))
        end_json['yes/no'] = yes_no_res

        with open(r'assets/checkboxes.json', 'w') as f:
            json.dump(end_json, f, ensure_ascii=False, indent=4)
        s3.upload_file(f'./assets/checkboxes.json',
                       bucket, f'words/checkboxes.json')
        return dcc.Location(id='url', href='/settings', refresh=True)