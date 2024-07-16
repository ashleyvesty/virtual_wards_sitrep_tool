import calendar
import json
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import functions

# load data
vw_data = pd.DataFrame(functions.get_vw_dataset())
with open(functions.convert_shape_to_json()) as geo_file:
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
    ['Year', 'Month']).values.tolist()

# streamlit date select box, conditional on the selected view
if view == "National Overview":
    selected_date = st.sidebar.selectbox('Select a Year and Month',
                                         options=date_combinations,
                                         format_func=lambda date: f"{calendar.month_name[date[1]]} {date[0]}")
    vw_data_time_filtered = vw_data[
    (vw_data['Date'].dt.year == selected_date[0]) & (vw_data['Date'].dt.month == selected_date[1])]
else:
    vw_data_time_filtered = vw_data


# streamlit selectbox for ICB, conditional on view
icb_locations = vw_data['ICB23NM'].unique().tolist()
icb_locations_with_select_all = ['All ICB'] + icb_locations
if view == "National Overview":
    selected_location = 'All ICB'
else:
    selected_location = st.sidebar.selectbox('Select an ICB Location', options=icb_locations_with_select_all)

if selected_location != 'All ICB':
    filtered_data = vw_data[vw_data['ICB23NM'] == selected_location]
else:
    filtered_data = vw_data

# created grouped dataframe for All_ICB selection
total_occupancy_capacity = filtered_data.groupby('Date')[
    ['Occupancy', 'Capacity', 'GP_Registered_Population']].sum().reset_index()
total_occupancy_capacity['Occupancy_Percent'] = ((total_occupancy_capacity['Occupancy'] / total_occupancy_capacity[
    'Capacity'].replace(0, np.nan)) * 100).round(2)
total_occupancy_capacity['Capacity_100k'] = ((total_occupancy_capacity['Capacity'] / total_occupancy_capacity[
    'GP_Registered_Population'].replace(0, np.nan)) * 10000).round(2)

# Construct Figure 0: Choropleth graph
fig = go.Figure(
    go.Choroplethmapbox(
        geojson=geojson_data,
        locations=vw_data_time_filtered['ICB23CD'],
        featureidkey='properties.ICB23CD',
        z=vw_data_time_filtered['Occupancy_Percent'],
        customdata=vw_data_time_filtered[['Occupancy', 'Capacity', 'Capacity_100k', 'GP_Registered_Population']],
        text=vw_data_time_filtered['ICB23NM'],
        colorscale=px.colors.diverging.RdYlGn[::-1],
        hovertemplate=(
            '%{text}<br>'
            '<extra><br>%{z:.2f}%</extra>'
            'Reported Occupancy: %{customdata[0]}<br>'
            'Reported Capacity: %{customdata[1]}<br>'
            'Capacity per 100k GP Registered Patients: %{customdata[2]}<br>'
            'GP Registered Population (over 16): %{customdata[3]:,.0f}<br>'),
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
    title="Snapshot Data by Month",
)
fig.update_layout(margin={"r": 0, "t": 0, "l": 0, "b": 0})

# Construct Figure 1: Choropleth graph
fig1 = go.Figure(
    go.Choroplethmapbox(
        geojson=geojson_data,
        locations=vw_data_time_filtered['ICB23CD'],
        featureidkey='properties.ICB23CD',
        z=vw_data_time_filtered['Capacity_100k'],
        customdata=vw_data_time_filtered[['Occupancy', 'Capacity', 'Occupancy_Percent', 'GP_Registered_Population']],
        text=vw_data_time_filtered['ICB23NM'],
        colorscale='RdYlGn',
        hovertemplate=(
            '%{text}<br>'
            '<extra>%{z}</extra>'
            'Reported Occupancy: %{customdata[0]}<br>'
            'Reported Capacity: %{customdata[1]}<br>'
            'Occupancy Percent: %{customdata[2]} %<br>'
            'GP Registered Population (over 16): %{customdata[3]:,}<br>'
        )
    )
)

fig1.update_layout(
    mapbox_style="carto-positron",
    mapbox_zoom=5,
    mapbox_center={"lat": 52.37, "lon": -0.5},
    width=800,
    height=600,
    title="Snapshot Data by Month",
)

fig1.update_layout(margin={"r": 0, "t": 0, "l": 0, "b": 0})

# Construct Figure 2: Line Graph
fig2 = go.Figure()
fig2.add_trace(
    go.Scatter(
        x=total_occupancy_capacity['Date'],
        y=total_occupancy_capacity['Occupancy'],
        mode='lines+markers',
        name='Occupancy',
    )
)

fig2.add_trace(
    go.Scatter(
        x=total_occupancy_capacity['Date'],
        y=total_occupancy_capacity['Capacity'],
        mode='lines+markers',
        name='Capacity',
    )
)

fig2.update_layout(
    title='Occupancy and Capacity over time for {}'.format(selected_location),
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
    )
)
fig3.update_layout(
    title='Occupancy % over time for {}'.format(selected_location),
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
    )
)
fig4.update_layout(
    title='Capacity per 100k GP Registered Patients over time for {}'.format(selected_location),
    xaxis_title='Date',
    yaxis_title='Value',
    )

# Construct Figure 5: Line Graph
fig5 = go.Figure()
fig5.add_trace(
    go.Scatter(
        x=total_occupancy_capacity['Date'],
        y=total_occupancy_capacity['GP_Registered_Population'],
        mode='lines+markers',
        name='GP Registered Population',
    )
)
fig5.update_layout(
    title='GP Registered Population (16+) for {}'.format(selected_location),
    xaxis_title='Date',
    yaxis_title='Value',
    )


# Update y-axis to 0 for scatters
fig2.update_yaxes(rangemode='tozero')
fig3.update_yaxes(rangemode='tozero')
fig4.update_yaxes(rangemode='tozero')
fig5.update_yaxes(rangemode='tozero')

# conditional rules for which plots to chart based on selected view
if view == "National Overview":
    st.write("#### **National Overview**")
    st.write("###### **Occupancy (% of Capacity)**")
    st.plotly_chart(fig)
    st.write("\n")
    st.write("###### **Capacity per 100k GP Registers Patients (>16 Years Old)**")
    st.plotly_chart(fig1)
else:
    st.write("#### **Time Series & ICB Performance**")
    st.plotly_chart(fig2)
    st.plotly_chart(fig3)
    st.plotly_chart(fig4)
    st.plotly_chart(fig5)
