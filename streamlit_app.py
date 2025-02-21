
import streamlit as st
import pandas as pd
import numpy as np
import random 
from datetime import date, timedelta
pd.options.display.max_columns = None
pd.options.display.max_rows = None


from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

# import chromedriver_binary

import geopandas as gpd
from shapely.geometry import Polygon, MultiPolygon
import matplotlib.pyplot as plt

from bokeh.io import output_notebook, output_file, show
from bokeh.plotting import figure
from bokeh.models import HoverTool, Select, ColumnDataSource, WheelZoomTool, LogColorMapper, LinearColorMapper, ColorBar, BasicTicker
from bokeh.palettes import Blues8 as palette
from bokeh.layouts import row
from bokeh.plotting import figure
from bokeh.models import Circle
from bokeh.models import ColumnDataSource
import altair as alt

# GET LOCATION ID DATA FRAME
# when deploying to external server, consider create LocationIDs manually instead of reading csv
@st.cache_data(show_spinner=False)
def get_LocationIDs():
    # 1. Import Location and Borough columns form NY TAXI ZONES dataset
    dfzones = pd.read_csv("NY_taxi_zones.csv", sep=',',
                          usecols=['LocationID', 'borough'])

    # 2. Filter Manhattan zones 
    dfzones = dfzones[dfzones['borough']=='Manhattan']\
                    .drop(['borough'], axis=1)\
                    .sort_values(by='LocationID')\
                    .drop_duplicates('LocationID').reset_index(drop=True)    
    dfzones = dfzones[:7]
    return dfzones

# CREATE DATETIME INFO AND APPEND LOCATION IDs
@st.cache_data(show_spinner=False)
def datetimeInfo_and_LocID(df_LocIds, start_date, NoOfDays):   

    from pandas.tseries.holiday import USFederalHolidayCalendar as calendar
    
    # repeat LocationIDs. All of them... for each hour
    location_id_col = pd.concat([df_LocIds]*24*NoOfDays).reset_index(drop=True)

    # create data frame with range of days with hourly period
    df_pred = pd.DataFrame()
    dates = pd.date_range(start = start_date, end = start_date + timedelta(days=NoOfDays), freq = "H")
    df_pred['datetime'] = dates
    df_pred.drop([df_pred.shape[0]-1], inplace=True)

    # Create new columns from datetime
    df_pred['month'] = df_pred['datetime'].dt.month
    df_pred['hour'] = df_pred['datetime'].dt.hour
    # 'dayhour' will serve as index to perform the join
    df_pred['dayhour'] = df_pred['datetime'].dt.strftime('%d%H')
    df_pred['week'] = df_pred['datetime'].dt.week
    df_pred['dayofweek'] = df_pred['datetime'].dt.dayofweek


    # Create date time index calendar
    drange = pd.date_range(start=str(start_date.year)+'-01-01', end=str(start_date.year)+'-12-31')
    cal = calendar()
    holidays = cal.holidays(start=drange.min(), end=drange.max())
    
    # 8.3 create new columns 'date' and 'isholiday'
    df_pred['date'] = pd.to_datetime(df_pred['datetime'].dt.date)
    df_pred['isholiday'] = df_pred['datetime'].isin(holidays).astype(int)
    
    # drop 'date' and 'datetime' column
    df_pred.drop(['datetime'], axis=1, inplace=True)
    df_pred.drop(['date'], axis=1, inplace=True)

    # repeat rows. 67 rows per hour
    df_pred = df_pred.iloc[np.arange(len(df_pred)).repeat(len(df_LocIds))].reset_index(drop=True)
    #df_index = df_index.iloc[np.arange(len(df_index)).repeat(67)].reset_index(drop=True)

    df_pred = df_pred.join(location_id_col)
    
    return df_pred

# SCRAPE PRECIPITATION FORECAST FROM wunderground.com
@st.cache_data(show_spinner=False)
def scrape_data(today, days_in):
    with st.spinner("I am scraping weather data from wunderground.com... please wait."):
        # Use .format(YYYY, M, D)
        # lookup_URL = 'https://www.wunderground.com/hourly/qa/doha/date/{}-{}-{}.html'   
        lookup_URL = 'https://www.wunderground.com/hourly/sa/riya/date/{}-{}-{}.html'
        # lookup_URL = 'https://www.wunderground.com/hourly/in/del/date/{}-{}-{}.html'
        # lookup_URL = 'https://www.wunderground.com/history/daily/ru/sunzha/URMS/date/{}-{}-{}.html'

        options = webdriver.ChromeOptions()

        options.add_argument('headless'); # to run chrome in the backbroung
        options.add_argument('--no-sandbox')
        options.add_argument("--disable-dev-shm-usage")


        driver = webdriver.Chrome(service=Service(),options=options, 
                                  executable_path = 'C:\\Users\\anageswaran\\Desktop\\MasterDataScience_FinalProject-master\MasterDataScience_FinalProject-master\\chromedriver.exe')

        start_date = today + pd.Timedelta(days=1)
        end_date = today + pd.Timedelta(days=days_in + 1)

        df_prep = pd.DataFrame()

        while start_date != end_date:
            timestamp = pd.Timestamp(str(start_date)+' 00:00:00')

            print('gathering data from: ', start_date)

            formatted_lookup_URL = lookup_URL.format(start_date.year,
                                                     start_date.month,
                                                     start_date.day)

            driver.get(formatted_lookup_URL)
            rows = WebDriverWait(driver, 90).until(EC.visibility_of_all_elements_located((By.XPATH, '//td[@class="mat-cell cdk-cell cdk-column-temperature mat-column-temperature ng-star-inserted"]')))
            for row in rows:
                hour = timestamp.strftime('%H')
                day = timestamp.strftime('%d')
                prep = row.find_element("xpath",'.//span[@class="wu-value wu-value-to"]').text
                # append new row to table
                # 'dayhour' column will serve as column index to perform the Join
                df_prep = df_prep.append(pd.DataFrame({"dayhour":[day+hour], 'Temperature':[prep]}),
                                         ignore_index = True)

                timestamp += pd.Timedelta('1 hour')

            start_date += timedelta(days=1)
            
    return df_prep

# GET INPUT DATA USING THE FUNCTIONS ABOVE: LocationIDs and Datetime info
@st.cache_data(show_spinner=False)
def get_input_data(start_date, NoOfDays):
    # get LocationIDs data frame
    df_LocIds = get_LocationIDs()

    # create datetime info and append LocationsIDs
    dtInfo_and_LocID = datetimeInfo_and_LocID(df_LocIds,start_date,NoOfDays)

    # get precipitation forecast
    prep_forecast = scrape_data(date.today(), NoOfDays)
    

    # merge both data frames
    df_merged = dtInfo_and_LocID.merge(prep_forecast, on="dayhour", how="left")

    # drop dayhour column
    df_merged = df_merged.drop(['dayhour'], axis=1)
    
    return df_merged

# GET OUPPUT DATA: get predictions, append to input_data and format it to be processed
@st.cache_data(show_spinner=False)
def get_output_data(pickle_file, input_data):
    with st.spinner("Making predictions..."):
        import pickle

        model = pickle.load(open(pickle_file,'rb'))

        # get prediction, convert to integer and convert Array into DataFrame
        model_predict = (model.predict(input_data)).astype(int)
        df_predict = pd.DataFrame({'pickups':model_predict})

        # join input_data with DataFrame
        joined = input_data.join(df_predict)

        output_data = joined[['hour','dayofweek','LocationID','pickups']]
    
    return output_data

# GET DATA FRAME WITH SHAPE GEOMETRY INFO
@st.cache_data(show_spinner=False)
def load_shape_data():
    path = './taxi_zones/taxi_zones.shp'
    shape_data = gpd.read_file(path)
    geo_data = gpd.read_file(r"gadm36_SAU_1.shp")
    


    # filter Manhattan zones
    shape_data = shape_data[shape_data['borough'] == 'Manhattan'].reset_index(drop=True)

    shape_data = shape_data.drop(['borough'], axis=1)
    shape_data= shape_data[:13]
    shape_data['geometry'] = geo_data['geometry'].values
    shape_data['zone'] = geo_data['NAME_1'].values
    # print(shape_data)

    #EPSG-Code of Web Mercador
    shape_data.to_crs(epsg=3785, inplace=True)

    # Simplify Shape of Zones (otherwise slow peformance of plot)
    shape_data["geometry"] = shape_data["geometry"].simplify(100)

    data = []
    for zonename, LocationID, shape in shape_data[["zone", "LocationID", "geometry"]].values:
        #If shape is polygon, extract X and Y coordinates of boundary line:
        if isinstance(shape, Polygon):
            X, Y = shape.boundary.xy    
            X = [int(x) for x in X]
            Y = [int(y) for y in Y]
            data.append([LocationID, zonename, X, Y])
        # print(shape)
        #If shape is Multipolygon, extract X and Y coordinates of each sub-Polygon:
        if isinstance(shape, MultiPolygon):
            for poly in shape.geoms:
                X, Y = poly.exterior.xy
                X = [int(x) for x in X]
                Y = [int(y) for y in Y] 
                data.append([LocationID, zonename, X,    Y])

    #Create new DataFrame with X an Y coordinates separated:
    shape_data = pd.DataFrame(data, columns=["LocationID", "ZoneName", "X", "Y"])
    return shape_data

@st.cache_data(show_spinner=False)
def load_taxis_data(output_data, shape_data):
    df_to_visualize = shape_data.copy()
    pickups = output_data.groupby(['hour','dayofweek','LocationID']).sum()
    #start_day = pd.unique(output_data['dayofweek']).min()
    #end_day = pd.unique(output_data['dayofweek']).max()
    listofdays = pd.unique(output_data['dayofweek'])

    for hour in range(24):
        #for dayofweek in range(start_day,end_day+1,1):
        for dayofweek in listofdays:
            # get pickups for this hour and weekday
            p = pd.DataFrame(pickups.loc[(hour, dayofweek)]).reset_index()
            # print(p.info())
            p['LocationID'] = p['LocationID'].astype(int)
            # print(p.info())


        
            # add pickups to the Taxi Zones DataFrame       
            df_to_visualize = pd.merge(df_to_visualize, p, on="LocationID", how="left").fillna(0)
            # rename column as per day and hour
            df_to_visualize.rename(columns={"pickups" : "Passenger_%d_%d"%(dayofweek, hour)}, inplace=True)

    return df_to_visualize

@st.cache_data(show_spinner=False)
def select_day(gdf_merged, weekday1, weekday2, weekday3, selected_weekday):
    gdf_merged_c = gdf_merged.copy()
    day_list = [weekday1, weekday2, weekday3]
    day_list.remove(selected_weekday)
    for hour in range(24):
        for dayofweek in day_list:
            column_to_drop = "Passenger_%d_%d"%(dayofweek, hour)
            gdf_merged_c.drop([column_to_drop], axis=1, inplace=True)
    gdf_merged_c.reset_index(level=0, inplace=True)
    return gdf_merged_c

def create_altair_plots(long_df):
    # create selections
    selection = alt.selection_multi(fields=['ZoneName'])
    sel_size = alt.selection_single(empty='none')
    sel_size_legend = alt.selection_multi(fields=['ZoneName'], empty='none')
    sel_line_hover = alt.selection_single(on='mouseover', empty='none')

    opacity = alt.condition(selection, alt.value(1), alt.value(0.5))

    color = alt.condition(selection,
                         alt.Color('ZoneName:O', legend=None, scale=alt.Scale(scheme='category10')),
                         alt.value('lightgray'))

    line = alt.Chart(long_df).mark_line().encode(
        x='hour',
        y=alt.Y('Passenger_{0}_'.format(weekday), title='Orders(in m³)'),
        color=alt.Color('ZoneName', legend=None),
        size=alt.condition(sel_line_hover|sel_size|sel_size_legend, alt.value(4),alt.value(1)),
        opacity = opacity,
        tooltip = alt.Tooltip('ZoneName:O')
        ).properties(
        
        height=250,
        width=400
        ).add_selection(
        selection, sel_line_hover,sel_size,sel_size_legend
        )

    legend = alt.Chart(long_df).mark_point(
        filled=True, size=50
        ).encode(
        y=alt.Y('ZoneName', axis=alt.Axis(orient='right'), title=None),
        color=color,
        ).properties(
        width=25,
        height=250,
        ).add_selection(
        selection,sel_size_legend
        )
    
    return line, legend


def create_map_plot(df_to_visualize, _weekday , _hour):

    random_water_presence = str(random.randint(200, 800))
    df_for_map = df_to_visualize.copy()
    # ColumnDataSource transforms the data into something that Bokeh and Java understand
    df_for_map["Passengers"] = df_for_map["Passenger_" + str(_weekday) + "_" + str(_hour)]

    source = ColumnDataSource(df_for_map)

    max_passengers_per_hour = df_for_map[filter(lambda x: "Passenger_" in x, df_for_map.columns)].max().max()

    color_mapper = LinearColorMapper(palette=palette[::-1], high=max_passengers_per_hour, low=0)

    ##### Color Bar
    color_bar = ColorBar(color_mapper = color_mapper,
                         ticker = BasicTicker(),
                        label_standoff=8,
                         location=(0,0), background_fill_alpha = 0.0,
                         orientation='vertical')

    p = figure( plot_height=470, plot_width=550,
               toolbar_location=None,
               tools='pan,wheel_zoom,box_zoom,reset,save', background_fill_alpha = 0.0
)
    p.xaxis.visible = False
    p.yaxis.visible = False

    p.xgrid.grid_line_color = None
    p.ygrid.grid_line_color = None
    p.outline_line_color = None

    # Get rid of zoom on axes:
    for t in p.tools:
        if type(t) == WheelZoomTool:
            t.zoom_on_axis = False


    patches = p.patches(xs="X", ys="Y", source=source,fill_alpha=1,
                      fill_color={'field': 'Passengers',
                                  'transform': color_mapper},
                      line_color="black", alpha=0.5)

    hovertool = HoverTool(tooltips=[('Zone:', "@ZoneName"),
                                    ("Orders(in m³):", "@Passengers"),
                                    ("water presence in storage plant(in m³) :", random_water_presence)])
    p.add_tools(hovertool)
    p.add_layout(color_bar, 'right' )
    
    return p

# from bokeh.models import Circle
# def create_map_plot(df_to_visualize, _weekday, _hour):
#     df_for_map = df_to_visualize.copy()
#     df_for_map["Passengers"] = df_for_map["Passenger_" + str(_weekday) + "_" + str(_hour)]

#     source = ColumnDataSource(df_for_map)

#     max_passengers_per_hour = df_for_map[filter(lambda x: "Passenger_" in x, df_for_map.columns)].max().max()

#     color_mapper = LinearColorMapper(palette=palette[::-1], high=max_passengers_per_hour, low=0)

#     color_bar = ColorBar(color_mapper=color_mapper,
#                          ticker=BasicTicker(),
#                          label_standoff=8,
#                          location=(0, 0),
#                          background_fill_alpha=0.0,
#                          orientation='vertical')

#     p = figure(plot_height=470, plot_width=550,
#                toolbar_location=None,
#                tools='pan,wheel_zoom,box_zoom,reset,save',
#                background_fill_alpha=0.0)
#     p.xaxis.visible = False
#     p.yaxis.visible = False

#     p.xgrid.grid_line_color = None
#     p.ygrid.grid_line_color = None
#     p.outline_line_color = None

#     # Get rid of zoom on axes:
#     for t in p.tools:
#         if type(t) == WheelZoomTool:
#             t.zoom_on_axis = False

#     patches = p.patches(xs="X", ys="Y", source=source, fill_alpha=1,
#                         fill_color={'field': 'Passengers',
#                                     'transform': color_mapper},
#                         line_color="black", alpha=0.5)

#     # Generate random values for "water presence in storage plant" for each zone name
#     water_presence_values = {}
#     for zone_name in df_for_map["ZoneName"].unique():
#         water_presence_values[zone_name] = random.randint(200, 800)

#     # Add markers at all locations with tooltips
#     for zone_name, water_presence in water_presence_values.items():
#         filtered_source = ColumnDataSource(df_for_map[df_for_map["ZoneName"] == zone_name])
#         marker = Circle(x="X", y="Y", size=10, fill_color="red", line_color="black")
#         renderer = p.add_glyph(filtered_source, marker)
#         hovertool = HoverTool(tooltips=[('Zone:', f"{zone_name}"),
#                                         ("Orders(in m³):", "@Passengers"),
#                                         ("water presence in storage plant(in m³) :", water_presence)],
#                              renderers=[renderer])
#         p.add_tools(hovertool)

#     p.add_layout(color_bar, 'right')

#     return p

#############################   DEFINE FUNCTIONS END   #############################

# INITIAL SET PAGE CONFIG

st.set_page_config(
page_title ="Demand Predictor",
layout="wide",
initial_sidebar_state ="expanded")

with open('style.css') as f:
    st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)

st.write('<style>div.block-container{padding-top:0.5rem;}</style>', unsafe_allow_html=True)

reduce_header_height_style = """
    <style>
         .sidebar{padding-top:0.5rem;
         width:15%}
    </style>
"""
st.markdown(reduce_header_height_style, unsafe_allow_html=True)

st.title("Water Demand Prediction system(Saudi Arabia)")


# SHOW TITLE AND DESCRIPTION
hide_menu_style = """
        <style>
        # MainMenu {visibility: hidden;}
        .css-18ni7ap{visibility: hidden;}
        .contract-trigger{visibility: hidden;}
        </style>
        """
st.markdown(hide_menu_style, unsafe_allow_html=True)

margins_css = """
    <style>
        .main > div {
            padding-left: 2rem;
            padding-right: 2rem;
            padding-top: -10rem;
            background-image: url(MicrosoftTeams-image__3_-removebg-preview.png);
            
        }
    </style>
"""

st.markdown(margins_css, unsafe_allow_html=True)


trained = pd.read_csv('trainpreds.csv', index_col='Date')
trained = trained[-1000:]
future = pd.read_csv('futurepreds.csv')
# print(trained.head(7))

# DECLARE VARIABLES: start date, NoOfDays, pickle_file
start_date = date.today() + timedelta(days=1) # start day is tomorrow
NoOfDays = 3 # number of days for prediction
pickle_file = r'model_GB.pickle'

# SCRAPE WEATHER, PREPARE DATA, MAKE PREDICTIONS
input_data = get_input_data(start_date, NoOfDays)

output_data = get_output_data(pickle_file, input_data)

shape_data = load_shape_data()

df_to_visualize = load_taxis_data(output_data,shape_data)

# st.sidebar.image("logo.png")
# st.sidebar.markdown(
#     """"
    
#     <style>
#         .sidebar .sidebar-content {
#         background-color: (10, 9, 82);
#         color: white;
#         }
#     </style>

#     """,

#     unsafe_allow_html=True,
# )
# SIDE BAR - TITLE
st.sidebar.title('Your options:')

# choose_graph = st.sidebar.selectbox(
#     'Choose your prefered visualization:',
#      ['Map', 'Line Chart'])

# SIDE BAR - SLIDER: DAYS
day1 = date.today() + pd.Timedelta(days=1)
day2 = date.today() + pd.Timedelta(days=2)
day3 = date.today() + pd.Timedelta(days=3)

choosen_day = st.sidebar.selectbox('Day to look at:', [day1, day2, day3])
selected_day = str(choosen_day)
weekday = choosen_day.weekday()

# SIDE BAR - SLIDER: HOURS
hour=7
hour = st.sidebar.slider("Hour to look at:",min_value=0, max_value=23, value=7, step=1)
col1, col2 = st.columns([1.40,3])
# col3,= st.columns(1)


# PREPARE DATA FOR LINE CHART    
# filter selected day data to show on map
gdf_selected_day = select_day(df_to_visualize,
                              day1.weekday(),
                              day2.weekday(),
                              day3.weekday(),
                              weekday)

# transform format from wide to long    
long_df = pd.wide_to_long(gdf_selected_day, ["Passenger_{0}_".format(weekday)], i='index', j="hour")
long_df = long_df.reset_index()

# filter wrong negative predictions
long_df.loc[long_df["Passenger_{0}_".format(weekday)]<0, 'Passenger_{0}_'.format(weekday)] = 0

# CREATE PLOTS
line, legend = create_altair_plots(long_df)
#map_plot = create_map_plot(df_to_visualize)

# if choose_graph == 'Map':
# col3.markdown("Pickups between %i:00 and %i:00: " % (hour, (hour + 1) % 24) + selected_day)
# col3.bokeh_chart(create_map_plot(df_to_visualize,weekday,hour),use_container_width=True)
# if choose_graph == 'Line Chart':
# col2.markdown("Evolution over the day: " + selected_day)
# col2.altair_chart(line | legend, theme="streamlit")   
st.markdown(
    """
<style>
button[title="View fullscreen"] {
    display: none;
}


</style>
""",
    unsafe_allow_html=True,
)

# SIDE BAR - TOP 3 TABLES
column_name = "Passenger_{0}_".format(weekday)
top5_hour = long_df.copy()
top5_hour = top5_hour[top5_hour['hour']==hour]
top5_hour = top5_hour.groupby(['ZoneName']).mean().sort_values(column_name, ascending=False)
top5_hour.rename(columns={column_name:'Orders(in m³)'}, inplace=True)
top5_hour['Orders(in m³)'] = top5_hour['Orders(in m³)'].astype(int)

# print(top5_hour)
max_per_hr = top5_hour['Orders(in m³)'].sum()
# col1.metric(label='Passengers per hour', value = max_per_hr)

a = top5_hour[ 'Orders(in m³)'].head(3)
# st.sidebar.subheader('Top 3 areas per HOUR:')
# s = figure(x_range=top5_hour[ 'Passengers'].head(3), height=350, title="Passengers",
#            toolbar_location=None, tools="")
# st.bokeh_chart(s)

# col4.bar_chart(a, use_container_width=True)

top5_day = long_df.copy()
top5_day = top5_day.groupby('ZoneName').mean().sort_values(column_name, ascending=False)
top5_day.rename(columns={column_name: 'Orders(in m³)'}, inplace=True)
top5_day['Orders(in m³)'] = top5_day['Orders(in m³)'].astype(int)
top5_day['Orders(in m³)'] = top5_day['Orders(in m³)']*24
max_per_day = top5_day['Orders(in m³)'].sum()

st.markdown(
    """
    <style>
    div.element-container.css-s73z22.e1tzin5v2 
 {

        background-color: #EEEEEE;
        border: 2px solid #CCCCCC;
        padding: 5% 5% 5% 10%;
        border-radius: 5px;
    }
    </style>
    

    """,
     unsafe_allow_html=True,
)


# col1.metric(label='Passengers per day'+ selected_day , value = max_per_day)
# st.sidebar.subheader('Top 3 areas per DAY:')
# col5.bar_chart(top5_day[ 'Passengers'].head(3), y='Passengers',width=200, use_container_width=True)

# a = figure(width=200, height=200)
# a.circle(top5_day[ 'Passengers'],top5_day.index, size=2, color="navy", alpha=0.5)




with st.container():
    col1.metric(label='Total Volume Ordered per hour(in m³)', value = max_per_hr)
    col1.metric(label='Total Volume on '+ selected_day +'(in m³)' , value = max_per_day)
    col1.metric(label='Model Accuracy', value = "92.02%")

    col2.markdown("Orders(in m³) between %i:00 and %i:00: " % (hour, (hour + 1) % 24) + selected_day)
    col2.bokeh_chart(create_map_plot(df_to_visualize,weekday,hour))


    col1.markdown('Top 3 locations per HOUR:')
    col1.table(top5_hour[ 'Orders(in m³)'].head(3)) 

    col1.markdown('Top 3 locations per DAY:')
    col1.table(top5_day[ 'Orders(in m³)'].head(3))
    col2.markdown("Evolution over the day: " + selected_day)
    col2.altair_chart(line | legend, theme="streamlit",use_container_width=True )
    # col2.markdown("Model Performance:") 
    # col2.line_chart(data= trained)
    # col1.bokeh_chart(a)




with st.container():

    # col3.markdown("Pickups between %i:00 and %i:00: " % (hour, (hour + 1) % 24) + selected_day)
    # col3.bokeh_chart(create_map_plot(df_to_visualize,weekday,hour),use_container_width=True)
    # st.markdown("Evolution over the day: " + selected_day)
    # st.altair_chart(line | legend, theme="streamlit",use_container_width=True )
    st.markdown("Model Performance:") 
    st.line_chart(data= trained)

    # col4.markdown('Top 3 areas per HOUR:')
    # col4.table(top5_hour[ 'Passengers'].head(3))








