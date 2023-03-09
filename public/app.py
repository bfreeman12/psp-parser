import dash
import dash_bootstrap_components as dbc

app = dash.Dash(__name__, update_title=None,
                external_stylesheets=[dbc.themes.BOOTSTRAP])
app.config.suppress_callback_exceptions = True
app.title = 'PSP Parser'
