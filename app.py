import calendar
import json
import os
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import functions

GEOJSON_PATH = "./data/geodata/ICB2023.geojson"

# load virtual ward data
vw_data = pd.DataFrame(functions.get_vw_dataset())

# open geodata
if os.path.exists(GEOJSON_PATH):
    pass
else:
    functions.convert_shape_to_json()

with open(GEOJSON_PATH) as geo_file:
    geojson_data = json.load(geo_file)

# streamlit formatting
st.title("NHS Virtual Wards SITREP Data")
st.sidebar.title('Selections')

# streamlit views select box
views = ["National Overview", "Time Series & ICB Performance"]
view = st.sidebar.selectbox("Select a View", views)

# instantiate date selection variable
dates_df = pd.DataFrame()
dates_df['Year'] = vw_data['Date'].dt.year
dates_df['Month'] = vw_data['Date'].dt.month
date_combinations = dates_df.drop_duplicates(subset=['Year', 'Month'])[['Year', 'Month']].sort_values(
    ['Year', 'Month'], ascending=False).values.tolist()

# streamlit date select box, conditional on the selected view
if view == "National Overview":
    selected_date = st.sidebar.selectbox('Select a Year and Month',
                                         options=date_combinations,
                                         format_func=lambda date: f"{calendar.month_name[date[1]]} {date[0]}")

    vw_data_time_filtered = vw_data[(vw_data['Date'].dt.year == selected_date[0]) & (vw_data['Date'].dt.month == selected_date[1])]

    # new variable for displaying date time in titles
    formatted_date = f"{calendar.month_name[selected_date[1]]} {selected_date[0]}"
else:
    vw_data_time_filtered = vw_data
    formatted_date = ""

# streamlit select box for ICB, conditional on view
icb_locations = sorted(vw_data['ICB23NMS'].unique().tolist())
icb_locations_with_select_all = ['National'] + icb_locations
if view == "National Overview":
    selected_location = 'National'
else:
    selected_location = st.sidebar.selectbox('Select an ICB Location', options=icb_locations_with_select_all)

if selected_location != 'National':
    filtered_data = vw_data[vw_data['ICB23NMS'] == selected_location]
else:
    filtered_data = vw_data

# created grouped dataframe for All_ICB selection
total_occupancy_capacity = filtered_data.groupby('Date')[
    ['Occupancy', 'Capacity', 'GP_Registered_Population']].sum().reset_index()
total_occupancy_capacity['Occupancy_Percent'] = ((total_occupancy_capacity['Occupancy'] / total_occupancy_capacity[
    'Capacity'].replace(0, np.nan)) * 100).round(2)
total_occupancy_capacity['Capacity_100k'] = ((total_occupancy_capacity['Capacity'] / total_occupancy_capacity[
    'GP_Registered_Population'].replace(0, np.nan)) * 100000).round(2)



# streamlit refresh data button
st.sidebar.write("")
st.sidebar.write("")
if st.sidebar.button('Check for New Reports & Refresh Data'):
    new_download_count, total_download_count = functions.download_and_rename_files()
    st.success(f'Data refreshed successfully! {new_download_count} new monthly report(s), {total_download_count} existing monthly report(s) loaded.')

# Construct Figure 0: Choropleth graph
fig = go.Figure(
    go.Choroplethmapbox(
        geojson=geojson_data,
        locations=vw_data_time_filtered['ICB23CD'],
        featureidkey='properties.ICB23CD',
        z=vw_data_time_filtered['Occupancy_Percent'],
        customdata=vw_data_time_filtered[['Occupancy', 'Capacity', 'Capacity_100k', 'GP_Registered_Population']],
        text=vw_data_time_filtered['ICB23NMS'],
        colorscale=px.colors.diverging.RdYlGn[::-1],
        hovertemplate=(
            '<b>%{text}</b><br>'
            '<extra><br><br><b>%{z:.2f}%</b></extra>'
            'Reported Occupancy: %{customdata[0]}<br>'
            'Reported Capacity: %{customdata[1]}<br>'
            'Capacity per 100k GP Registered Patients: %{customdata[2]}<br>'
            'GP Registered Population: %{customdata[3]:,.0f}<br>'),
        zmin=0,
        zmax=100,
    )
)
fig.update_layout(
    mapbox_style="carto-positron",
    mapbox_zoom=5,
    mapbox_center={"lat": 52.37, "lon": -0.5},
    width=800,
    height=600,
    title=dict(text=f"National Snapshot of Occupancy (% of Capacity) for {formatted_date}", font=dict(size=18, family='sans-serif')),
    margin={"r": 0, "t": 30, "l": 0, "b": 0},
    hoverlabel=dict(bgcolor="white", font_size=13, font_family="sans-serif")
)

# Construct Figure 1: Choropleth graph
fig1 = go.Figure(
    go.Choroplethmapbox(
        geojson=geojson_data,
        locations=vw_data_time_filtered['ICB23CD'],
        featureidkey='properties.ICB23CD',
        z=vw_data_time_filtered['Capacity_100k'],
        customdata=vw_data_time_filtered[['Occupancy', 'Capacity', 'Occupancy_Percent', 'GP_Registered_Population']],
        text=vw_data_time_filtered['ICB23NMS'],
        colorscale='RdYlGn',
        zmin=0,
        zmax=40,
        hovertemplate=(
            '<b>%{text}</b><br>'
            '<extra><b><br><br>%{z}</b></extra>'
            'Reported Occupancy: %{customdata[0]}<br>'
            'Reported Capacity: %{customdata[1]}<br>'
            'Occupancy Percent: %{customdata[2]} %<br>'
            'GP Registered Population:</b> %{customdata[3]:,}<br>'
        )
    )
)

fig1.update_layout(
    mapbox_style="carto-positron",
    mapbox_zoom=5,
    mapbox_center={"lat": 52.37, "lon": -0.5},
    width=800,
    height=600,
    margin={"r": 0, "t": 30, "l": 0, "b": 0},
    title=dict(text=f"National Snapshot of Capacity (per 100K GP Registered Patients) for {formatted_date}", font=dict(size=18, family='sans-serif')),
    hoverlabel=dict(bgcolor="white", font_size=13, font_family="sans-serif")
)

# Construct Figure 2: Line Graph
fig2 = go.Figure()
fig2.add_trace(
    go.Scatter(
        x=total_occupancy_capacity['Date'],
        y=total_occupancy_capacity['Occupancy'],
        mode='lines+markers',
        name='Occupancy',
        customdata=total_occupancy_capacity['Date'].dt.strftime('%B %Y')
    )
)

fig2.add_trace(
    go.Scatter(
        x=total_occupancy_capacity['Date'],
        y=total_occupancy_capacity['Capacity'],
        mode='lines+markers',
        name='Capacity',
        customdata=total_occupancy_capacity['Date'].dt.strftime('%B %Y')
    )
)

fig2.update_layout(
    title='Occupancy and Capacity Over Time for {}'.format(selected_location),
    xaxis_title='Date',
    yaxis_title='Value',
)

# Construct Figure3: Line Graph
fig3 = go.Figure()
fig3.add_trace(
    go.Scatter(
        x=total_occupancy_capacity['Date'],
        y=total_occupancy_capacity['Occupancy_Percent'],
        mode='lines+markers',
        name='Occupancy',
        customdata=total_occupancy_capacity['Date'].dt.strftime('%B %Y')
    )
)
fig3.update_layout(
    title='Occupancy % Over Time for {}'.format(selected_location),
    xaxis_title='Date',
    yaxis_title='Percent (%)',
    )
# Construct Figure 4: Line Graph
fig4 = go.Figure()
fig4.add_trace(
    go.Scatter(
        x=total_occupancy_capacity['Date'],
        y=total_occupancy_capacity['Capacity_100k'],
        mode='lines+markers',
        name='Capacity per 100K',
        customdata=total_occupancy_capacity['Date'].dt.strftime('%B %Y')
    )
)
fig4.update_layout(
    title='Capacity per 100k GP Registered Patients Over Time for {}'.format(selected_location),
    xaxis_title='Date',
    yaxis_title='Capacity per 100k',
    )

# Construct Figure 5: Line Graph
fig5 = go.Figure()
fig5.add_trace(
    go.Scatter(
        x=total_occupancy_capacity['Date'],
        y=total_occupancy_capacity['GP_Registered_Population'],
        mode='lines+markers',
        name='GP Registered Population',
        customdata=total_occupancy_capacity['Date'].dt.strftime('%B %Y')
    )
)
fig5.update_layout(
    title='GP Registered Population for {}'.format(selected_location),
    xaxis_title='Date',
    yaxis_title='Population',
    )

# Update y-axis to 0 for scatters
fig2.update_yaxes(rangemode='tozero')
fig3.update_yaxes(rangemode='tozero')
fig4.update_yaxes(rangemode='tozero')
fig5.update_yaxes(rangemode='tozero')

# Remove display of day of the month from line graph hoverboxes
fig2.update_traces(hovertemplate='Date: %{customdata}<br>Value: %{y}')
fig3.update_traces(hovertemplate='Date: %{customdata}<br>Value: %{y}')
fig4.update_traces(hovertemplate='Date: %{customdata}<br>Value: %{y}')
fig5.update_traces(hovertemplate='Date: %{customdata}<br>Value: %{y}')

# conditional rules for which plots to chart based on selected view
if view == "National Overview":
    st.plotly_chart(fig)
    st.write("\n")
    st.plotly_chart(fig1)
    st.write("\n")
    st.write(f"##### **Top 5 ICB With the Largest Capacity Increase in {formatted_date} from the Month Prior**")
    st.table(functions.calculate_capacity_increase(vw_data, selected_date[0], selected_date[1]))
    st.write("Note 1: GP registered population does not include patients less than 16 years old prior to April 2024.")
    st.write("Note 2: The data contains the number of patients on a virtual ward, at 8am Thursday prior to the sitrep submission period. For example, 8am Thursday 23rd May 2024 for May 2024 published data.")
    st.write("More information regarding virtual wards can be found on the NHS England website: https://www.england.nhs.uk/virtual-wards/")
else:
    st.write("#### **Time Series & ICB Performance**")
    st.plotly_chart(fig2)
    st.plotly_chart(fig3)
    st.plotly_chart(fig4)
    st.plotly_chart(fig5)
    st.write("Note 1: GP registered population does not include patients less than 16 years old prior to April 2024.")
    st.write("Note 2: The data contains the number of patients on a virtual ward, at 8am Thursday prior to the sitrep submission period. For example, 8am Thursday 23rd May 2024 for May 2024 published data.")
    st.write("More information regarding virtual wards can be found on the NHS England website: https://www.england.nhs.uk/virtual-wards/")



