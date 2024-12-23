# -*- coding: utf-8 -*-
"""
Created on Mon Nov 25 10:15:23 2024

@author: benja
"""
from flask import Flask, render_template, request, send_file, jsonify
import pandas as pd
import json
from keplergl import KeplerGl
import requests
from datetime import datetime


def api_get(URL):
    
    r = requests.get(url = URL)
    data = r.json()
    
    return data

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

URL_BASE = 'http://127.0.0.1:8212'

app = Flask(__name__)

# Custom error class for blank input
class BlankInputError(Exception):
    pass

class WrongFormatError(Exception):
    pass

# Error handler for BlankInputError
@app.errorhandler(BlankInputError)
def handle_blank_input_error(error):
    html_content = f"""
    <html>
    <head>
        <title>Error: No Data Returned</title>
    </head>
    <body>
        <h1>Error: No Data Returned</h1>
        <p>{str(error)}</p>
    </body>
    </html>
    """
    return html_content, 400  # Return a 400 Bad Request status code

@app.errorhandler(WrongFormatError)
def wrong_format_error(error):
    html_content = f"""
    <html>
    <head>
        <title>Error: Date Format Incorrect</title>
    </head>
    <body>
        <h1>Error: Date format not recognized.</h1>
        <p>{str(error)}</p>
    </body>
    </html>
    """
    return html_content, 400  # Return a 400 Bad Request status code

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/generate_map', methods=['POST'])
def generate_map():
    begin_date = request.form['begin_date']
    end_date = request.form['end_date']
    plants_input = request.form['plants']
    
    end_date = convert_date_format(end_date)
    
    begin_date = convert_date_format(begin_date)
    
    if type(plants_input) is str:
        plants_input = plants_input.upper()
        
    if plants_input:    
        if plants_input == 'ALL':
            URL = f"{URL_BASE}/rest/kOLdashapi/v1/deliverybygpszone?begindate={begin_date}&enddate={end_date}&beginplant=00&endplant=z"
        
            data = api_get(URL)
        
            df = data['deliverybygpszone']
            df = pd.DataFrame(df)      
    
        else:
        
            plants = [plant.strip() for plant in plants_input.split(',') if plant.strip()]

            df_list = []
        
            for plant in plants:
                begin_plant = str(plant)
                end_plant = str(plant)

                URL = f"{URL_BASE}/rest/kOLdashapi/v1/deliverybygpszone?begindate={begin_date}&enddate={end_date}&beginplant={begin_plant}&endplant={end_plant}"
        
                data = api_get(URL)
        
                dfx = data['deliverybygpszone']
                dfx = pd.DataFrame(dfx)
                
                df_list.append(dfx)
                    
            
            if df_list == []:
                raise BlankInputError("No delivery data found for selected plant parameters")
                
            df = pd.concat(df_list, ignore_index=True)  
    else:
        URL = f"{URL_BASE}/rest/kOLdashapi/v1/deliverybygpszone?begindate={begin_date}&enddate={end_date}&beginplant=00&endplant=z"
        
        data = api_get(URL)
        
        df = data['deliverybygpszone']
        df = pd.DataFrame(df)  
        
    if data['deliverybygpszone'] == []:
        raise BlankInputError("No delivery data found for selected parameters.")
        
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
    
    # JSON file
    f = open (r'.\config\config.json', "r")
 
    # Reading from file
    config = json.loads(f.read())
    
    config['config']['mapState']['latitude'] = mean_latitude
    config['config']['mapState']['longitude'] = mean_longitude

    # Generate Kepler.gl map
    map_1 = KeplerGl(config=config)
    map_1.add_data(data=filtered_df, name="Tickets")
    
    map_html = map_1._repr_html_()

    return map_html


    

if __name__ == '__main__':
    app.run(debug=True)