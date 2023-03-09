from dash import dcc, html
from dash.dependencies import Input, Output, State
import dash_bootstrap_components as dbc
from dash.exceptions import PreventUpdate
from app import app
import pages
import boto3
from botocore.config import Config
from pycognito import Cognito as cognito


server = app.server
app._favicon = ('assets/favicon.ico')
app.config.suppress_callback_exceptions = True
pool_id = 'poolid'
client_id = 'clientid'

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




navbar = dbc.Navbar(
    dbc.Container([
        dbc.Col(html.Img(src='../assets/sparklogo.png',
                style={'height': 70, 'maxWidth': '100%', 'width': 'auto'})),
        dbc.Col(
            dbc.Nav(children=[
                dbc.NavItem(dbc.NavLink("Home", href="/home")),
                dbc.NavItem(dbc.NavLink("Settings", href="../settings")),
                dbc.NavItem(html.Button('Logout', id='logout-button',n_clicks=0))
            ],
                navbar=True,
            ),
            width="100vw",
        ),
    ],
    ),
    class_name='nav-bar-container',
    color="dark",
    dark=True,
    style={
        'maxWidth': '100wv',
        'position':'fixed',
        'width':'100%',
        'top':0,
    }
)

app.layout = html.Div([
    html.Div([
        navbar,
        dcc.Store(id='session',storage_type='session'),
    ]),
    dcc.Location(id='url'),
    html.Div(id='content'),
    html.Div(id='redirect-div',children=[],style={'display':'none'}),
    html.Div(id='redirect-div2',children=[],style={'display':'none'}),
    html.Div(id='redirect-div3',children=[],style={'display':'none'})
])

@app.callback(
    Output('content', 'children'),
    Input('url', 'pathname'),
    Input('session','data'),
)
def display_content(pathname,session_token):
    page_name = app.strip_relative_path(pathname)
    @plotly_validate_cognito
    def protected_routes(token):
        if not page_name:
            return dcc.Location(id='url', href='/home', refresh=True)
        if page_name == 'home':
            return pages.home.layout
        elif page_name == 'settings':
            return pages.settings.layout
    #do not need creds
    try:
        if not session_token:
            if not page_name:
                return pages.login.layout
    except Exception as e:
        print(e)
    else:
        return protected_routes(token=session_token)


def plotly_validate_cognito(get_function):
    def wrapper(token):
        try:
            u = cognito(pool_id,client_id,id_token=token['id_token'],refresh_token=token['refresh_token'],access_token=token['access_token'])
            auth = u.verify_tokens()
            return get_function(auth)
        except Exception as e:
            print(e)
    return wrapper


@app.callback(
    Output('session','clear_data'),
    Output('redirect-div3','children'),
    Input('logout-button','n_clicks'),
    Input('session','data')
)
def logout_func(n_clicks,token):
    try:
        if n_clicks is None:
            raise PreventUpdate
        elif n_clicks > 0:
            u = cognito(pool_id,client_id,id_token=token['id_token'],refresh_token=token['refresh_token'],access_token=token['access_token'])
            u.logout()
            return True,dcc.Location(id='url', href='/', refresh=True)
    except Exception as e:
        print(e)

if __name__ == '__main__':
    app.run_server(debug=False)
    




