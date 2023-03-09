from dash import html,dcc,ctx
from dash.dependencies import Input, Output, State
import dash_bootstrap_components as dbc
from app import app
import boto3
from botocore.config import Config
from pycognito import Cognito as cognito, AWSSRP
from dotenv import load_dotenv
import os
load_dotenv()
pool_id = 'poolid'
client_id = 'clientid'
client_secret = os.environ['CLIENT_SECRET']
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
client = boto3.client('cognito-idp',config=my_config)

layout = html.Div(
    id='login-div',
    children=[
    html.Div(id='login-form',children=[
    dcc.Input(type='text',id='username',placeholder='username',required=True),
    dcc.Input(type='password',id='password',placeholder='password',required=True),
    html.Button('Login',id='login-button',n_clicks=0),
    html.Div(id='login-hidden',children=[],style={'display':'none'}),
    html.A('Forgot password?',href=r'https://psp-parser.auth-fips.us-gov-west-1.amazoncognito.com/forgotPassword?client_id=70vjdi5gdlr4u8a13d96cvn2gl&response_type=code&scope=openid&redirect_uri=https%3A%2F%2Fpsp-parser.sparkxcell.com%2F')
        ])
    ]
)

@app.callback(
    Output('session','data'),
    State('username','value'),
    State('password','value'),
    Input('login-button','n_clicks'),
)
def get_login_token(username, password, n_clicks):
    if n_clicks > 0:
        try:
            aws = AWSSRP(username=username, password=password, pool_id=pool_id,client_id=client_id, client=client,client_secret=client_secret)
            auth_user = aws.authenticate_user()
            access_token = auth_user['AuthenticationResult']['AccessToken']
            id_token = auth_user['AuthenticationResult']['IdToken']
            refresh_token = auth_user['AuthenticationResult']['RefreshToken']
            tokens = {
                'access_token': access_token,
                'id_token': id_token,
                'refresh_token':refresh_token
            }
            return tokens
        except:
            raise Exception('User not found')

