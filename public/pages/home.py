from dash.dependencies import Input, Output, State
import dash_uploader as du
from app import app
import os
from dash import html, dcc, ctx, ALL
import boto3
from botocore.config import Config
import re
import time
from flask import send_file, request
import dash_bootstrap_components as dbc
UPLOAD_FOLDER = "/home/webapp/tempupload/"
du.configure_upload(app, UPLOAD_FOLDER, use_upload_id=False)

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
    html.Div(
        id='homediv',
        children=[html.Div(
            children=html.Div(
                id='homeblock',
                children=[
                    html.Div(
                        id='upload-title',
                        children=html.Div([
                            html.H1('Please upload a PDF below',style={'overflow':'hidden'})
                        ]),
                        style={
                            'textAlign': 'center',
                        }
                    ),
                    du.Upload(
                        id='upload-data',
                        text='Drag and Drop Files Here or Click to Search',
                        text_completed='',
                        pause_button=False,
                        cancel_button=True,
                        filetypes=['pdf'],
                        max_files=10,
                        disabled=False,
                    ),
                    html.Div(
                        id='files-headers',
                        children=[
                            html.P('Unprocessed Packages', id='inprog-header'),
                            html.P('Completed', id='completed-header'),
                        ]),
                    html.Div([
                        html.Div(
                            className='files-wrapper',
                            children=[
                                html.Ul(
                                    id='inprogress-files', className='files-box', children=html.H4('')),
                                html.Ul(
                                    id='completed-files', className='files-box', children=html.H4('',)),
                            ]
                        )
                    ]),
                    dcc.Interval(
                        id='files-interval',
                        interval=1*10000,
                        n_intervals=0
                    ),
                    html.Div(id='hidden_div'),
                    html.Div(id='hidden_div3')
                ]),
        ),
            html.Div(id='download-modal',children=[]),
            html.Footer(
                "Downloads may take a few seconds, If your file doesn't download please try again.", style={'fontSize': '0.8em', 'fontStyle': 'italic', 'marginLeft': '55vw'})
        ])
]),


def uploaded_files():
    # List the files in the unfinished directory.
    result = s3.list_objects_v2(
        Bucket=bucket, Prefix='unprocessed_packages/')
    return [key['Key'][re.search('^unprocessed_packages/', key['Key']).end():] for key in result.get('Contents') if re.search('^unprocessed_packages/', key['Key']) and not key['Key'] == 'unprocessed_packages/']

def completed_files():
    # List the files in the completed directory.
    result = s3.list_objects_v2(
        Bucket=bucket, Prefix='processed_packages/')
    return [key['Key'][re.search('^processed_packages/', key['Key']).end():] for key in result.get('Contents') if re.search('^processed_packages/', key['Key']) and not key['Key'] == 'processed_packages/']


# below callbacks are responsible for dynamically updating files boxes based on an interval count


@app.callback(Output('inprogress-files', 'children'),
              Input('files-interval', 'n_intervals'))
def update_inprogress_files(n):
    files = uploaded_files()
    if len(files) == 0:
        return [html.Ul("No files yet!")]
    else:
        return [html.Ul(children=html.A(filenames, style={'color': 'red', 'fontSize': '.9vw'}),style={'overflow':'hidden'}) for filenames in files]


@app.callback(Output('completed-files', 'children'),
              Input('files-interval', 'n_intervals'))
def update_completed_files(n):
    comp_files = completed_files()
    if len(comp_files) == 0:
        return [html.Ul("No files yet!")]
    else:
        return [html.Ul(children=[html.A(html.Button(filenames, value=filenames, id={'type': 'button', 'index': f'{filenames}'}, n_clicks=0, style={'marginTop': 2, 'all': 'unset', 'color': 'green', 'cursor': 'pointer', 'fontSize': '.9vw','overflow':'hidden'})), html.Button('delete', n_clicks=0, id={'type': 'delete-button', 'index': f'{filenames}'}, style={'float': 'right', 'marginTop': '2px','height':'2.7vh','overflow':'hidden'})]) for filenames in comp_files]

# below function will allow users to delete files directly from their respective directory


@app.callback(
    Output('hidden_div', 'children'),
    Input({'type': 'delete-button', 'index': ALL}, 'n_clicks'),
    prevent_initial_call=True
)
def remove__files(n_clicks):
    for click in n_clicks:
        if click > 0:
            s3.delete_object(Bucket=bucket, Key='processed_packages/' +
                             ctx.triggered_id['index'])


@app.callback(
    Output('download-modal', 'children'),
    Input({'type': 'button', 'index': ALL}, 'n_clicks'),
    Input({'type': 'button', 'index': ALL}, 'value'),
)
def download_processed_pdf(n_clicks, value):
    for click in n_clicks:
        try:
            if click > 0:
                if not os.path.isdir('/var/app/current/assets'):
                    os.mkdir('/var/app/current/assets')
                s3.download_file(
                    bucket, f'processed_packages/'+ctx.triggered_id['index'], f'/var/app/current/assets/'+ctx.triggered_id['index'])
                
                #this is the creation of the modal
                modal = html.Div(
                    [
                     dbc.Modal(
            [
                dbc.ModalHeader(dbc.ModalTitle("Are you sure?"), close_button=True),
                dbc.ModalBody('You are about to download '+ctx.triggered_id['index']),
                dbc.ModalFooter(children=[
                    dbc.Button(
                        "Download",
                        href='assets/'+ctx.triggered_id['index'],
                        download='test.pdf',
                        external_link=True,
                    ),
                    dbc.Button(
                        "Close",
                        id="close-centered",
                        className="ms-auto",
                        n_clicks=0,
                    )]
                ),
            ],
            id="modal-centered",
            centered=True,
            is_open=True,
        ),   
                    ]
                )
                return modal
        except Exception as e:
            print(e)

@du.callback(
    output=Output('hidden_div3', 'children'),
    id='upload-data',
)
def upload_to_bucket(filenames):
    while True:
        lambda_client = boto3.client('lambda', config=my_config)
        response = lambda_client.invoke(FunctionName='start_parser',InvocationType='Event',LogType='Tail',Payload='{"Start":"True"}')
        for file in os.listdir('/home/webapp/tempupload/'):
            if os.path.isfile('/home/webapp/tempupload/'+file):
                try:
                    s3.upload_file(
                        f'/home/webapp/tempupload/{file}', bucket, f'unprocessed_packages/{file}')
                    if len(os.listdir('/home/webapp/tempupload/')) == 0:
                        return
                    continue
                except (TypeError, ValueError, IndexError) as e:
                    print(e)
            else:
                pass


@app.callback(
    Output("modal-centered", "is_open"),
    Input("close-centered", "n_clicks"),
    [State("modal-centered", "is_open")],
)
def toggle_modal(n1, is_open):
    if n1 :
        return not is_open
    return is_open


