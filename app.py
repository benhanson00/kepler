# -*- coding: utf-8 -*-
"""
Created on Wed Dec 18 09:22:51 2024

@author: benja
"""

from flask import Flask, render_template, request, flash, Response
from wtforms import Form, DateField, SubmitField, StringField
import requests
import plotly.graph_objs as go
import plotly.io as pio
import pandas as pd
import io
from datetime import datetime
import json
from keplergl import KeplerGl


def convert_date_format(date_str):
    """
    Takes date given by user and puts it in format that can be understood by the api
    
    Parameters:
    - date_str: date in the form of a string

    Returns:
    - date_obj: date in format yyyy-mm-dd
    """
    # Define possible date formats
    date_formats = [
        "%m/%d/%Y", "%Y/%m/%d", "%m-%d-%Y", "%Y-%m-%d"
    ]
    
    for fmt in date_formats:
        try:
            # Try parsing the date with the current format
            date_obj = datetime.strptime(date_str, fmt)
            # Return the date in yyyy-mm-dd format
            return date_obj.strftime("%Y-%m-%d")
        except ValueError:
            continue

    # If no format matches, raise an error
    raise WrongFormatError("Date format not recognized. Please use mm/dd/yyyy, yyyy/mm/dd, mm-dd-yyyy, or yyyy-mm-dd.")
    
def outlier_filter(df, n_sigma=5):
    """
    Filters a Dataframe to only include points within n sigma of the mean value.
    
    Parameters:
    - df: pandas DataFrame containing geographic data.
    - n_sigma the number of std deviations away from the mean that will be allowed
    
    Returns:
    - Filtered Dataframe only containing points within set number of std deviations of mean.
    """
    
    lat_filt = df[df['lat'] < df['lat'].quantile(0.95)]
    lat_filt = lat_filt[lat_filt['lat'] > df['lat'].quantile(0.05)]
    
    lon_filt = df[df['lon'] < df['lon'].quantile(0.95)]
    lon_filt = lon_filt[lon_filt['lon'] > df['lon'].quantile(0.05)]    
    
    lat_sigma = lat_filt.lat.std()
    lon_sigma = lon_filt.lon.std()

    df = df[df['lat'] < df.lat.mean() + n_sigma*lat_sigma]
    df = df[df['lat'] > df.lat.mean() - n_sigma*lat_sigma]
    df = df[df['lon'] < df.lon.mean() + n_sigma*lon_sigma]
    df = df[df['lon'] > df.lon.mean() - n_sigma*lon_sigma]
    
    return df

def find_center(df):
    """
    Finds the mean value of latitude and longitude based on lat and lon values greater than the 5th percentile
    and less that the 95th percentile in the dataset
   
     Parameters:
     - df: pandas DataFrame containing geographic data.

     Returns:
     mean_lat : latitude value to center map around
     mean_lon : longitude value to center map around
     """
    
    lat_filt = df[df['lat'] < df['lat'].quantile(0.95)]
    lat_filt = lat_filt[lat_filt['lat'] > df['lat'].quantile(0.05)]
    
    lon_filt = df[df['lon'] < df['lon'].quantile(0.95)]
    lon_filt = lon_filt[lon_filt['lon'] > df['lon'].quantile(0.05)]
    
    mean_lat = lat_filt['lat'].mean()
    mean_lon = lat_filt['lon'].mean()  
    
    return mean_lat, mean_lon

def make_map(df, lat, lon):
    
    # JSON file
    f = open (r'.\config\config.json', "r")
 
    # Reading from file
    config = json.loads(f.read())
    
    config['config']['mapState']['latitude'] = lat
    config['config']['mapState']['longitude'] = lon

    # Generate Kepler.gl map
    map_1 = KeplerGl(config=config)
    map_1.add_data(data=df, name="Tickets")
    
    map_html = map_1._repr_html_()
    
    return map_html

class WrongFormatError(Exception):
    pass

URL_BASE = 'http://127.0.0.1:8212'


app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key_here'  # Used for flashing messages

# WTForm for date inputs
class DateForm(Form):
    begin_date = DateField('Begin Date', format='%Y-%m-%d')
    end_date = DateField('End Date', format='%Y-%m-%d')
    plants_input = StringField('plants_input')
    submit = SubmitField('Submit')

# Home route to display the form
@app.route("/", methods=["GET", "POST"])
def home():
    form = DateForm(request.form)
    if request.method == "POST" and form.validate():
        begin_date = form.begin_date.data
        end_date = form.end_date.data
        plants_input = form.plants_input.data
        
        if plants_input:
            if plants_input == "ALL":
                URL = f"{URL_BASE}/rest/kOLdashapi/v1/deliverybygpszone?begindate={begin_date}&enddate={end_date}&beginplant=00&endplant=z"
            else:
                plants = [plant.strip() for plant in plants_input.split(',') if plant.strip()]
                
                URL = 'list'
                
                url_list = []
                
                for plant in plants:
                    begin_plant = str(plant)
                    end_plant = str(plant)
                    url = f"{URL_BASE}/rest/kOLdashapi/v1/deliverybygpszone?begindate={begin_date}&enddate={end_date}&beginplant={begin_plant}&endplant={end_plant}"
                    url_list.append(url)
        else:
            URL = f"{URL_BASE}/rest/kOLdashapi/v1/deliverybygpszone?begindate={begin_date}&enddate={end_date}&beginplant=00&endplant=z"

        try:
            if URL == 'list':
                df_list = []
                for end in url_list:
                    # response = requests.get(URL, params=params)
                    response = requests.get(end)
                    response.raise_for_status()  # Raises an HTTPError for bad responses (4xx or 5xx)

                    # Parse API response (example structure assumed: [{"date": "2024-01-01", "value": 100}, ...])
                    api_data = response.json()
            
                    df_x = api_data['deliverybygpszone']
                    df_x = pd.DataFrame(df_x)
                    
                    df_list.append(df_x)
                df = pd.concat(df_list, ignore_index=True)
            else:
                # response = requests.get(URL, params=params)
                response = requests.get(URL)
                response.raise_for_status()  # Raises an HTTPError for bad responses (4xx or 5xx)

                # Parse API response (example structure assumed: [{"date": "2024-01-01", "value": 100}, ...])
                api_data = response.json()
            
                df = api_data['deliverybygpszone']
                df = pd.DataFrame(df)
            
            df = df.loc[:,~df.columns.duplicated()].copy()

            df['s'] = 'P'
            df['plantno'] = df['plantno'].astype({'plantno': str})
            df['plantno'] = df['s'] + df['plantno']
        
            df.drop(['s'], axis = 1)
            filtered_df = df.dropna(subset=['lat', 'lon'])
            
            filtered_df['date'] = pd.to_datetime(df['ticketdate'])
            filtered_df['Day_of_Week'] = filtered_df['date'].dt.day_name()
        
            filtered_df = filtered_df.drop(['date'], axis = 1)

        
            # filter out data that is either negative or zero
            filtered_df = filtered_df[filtered_df['tojobmin'] > 0]
            filtered_df = filtered_df[filtered_df['tojobmin'] != 0]
        
            mean_latitude, mean_longitude = find_center(filtered_df)
        
            filtered_df = outlier_filter(filtered_df)
        
            maps = make_map(filtered_df, mean_latitude, mean_longitude)

            # Send the graph as an image response
            return Response(maps, mimetype='text/html')

        except requests.exceptions.RequestException as e:
            flash(f"API call failed: {e}", "danger")

    return render_template("form.html", form=form)

if __name__ == "__main__":
    app.run(debug=True)
