import os
import geopandas
import numpy as np
import pandas as pd

HEADER_KEYWORD = 'Region'
EXCEL_SHEET = 'Virtual Ward Data'
FILE_PREFIX = 'VW'
FILE_EXT = '.xlsx'
LOCATION_DATA_FILE = './data/subICSLocations.csv'
SHAPEFILE = 'shapefile/ICB_Shape.zip'
GEOJSON_OUTPUT = './data/ICB2023.geojson'
DATA_PATH = './data'

def load_data():
    print(os.getcwd())
    all_data = pd.DataFrame()
    excel_files = [f for f in os.listdir(DATA_PATH) if f.startswith(FILE_PREFIX) and f.endswith(FILE_EXT)]
    # Iterate through the Excel files and extract the relevant data
    for file in excel_files:
        file_path = os.path.join(DATA_PATH, file)
        file_date = file.split(FILE_PREFIX)[1].split(FILE_EXT)[0]
        xl = pd.ExcelFile(file_path)
        df = pd.read_excel(xl, sheet_name=EXCEL_SHEET)

        # find the index of the row that contains the keyword
        header_index = df[df.apply(lambda row: row.astype(str).str.contains(HEADER_KEYWORD).any(), axis=1)].index[0]

        # get the required table data
        table_data = df.iloc[header_index:].copy()
        table_data.columns = table_data.iloc[0]
        table_data = table_data[1:]
        table_data.rename_axis('Index', axis=1, inplace=True)
        table_data['Date'] = file_date

        # clean the data of summary rows
        table_data = table_data[~(table_data == 'ENGLAND').any(axis=1)]
        table_data = table_data[~(table_data == 'ENGLAND*').any(axis=1)]

        # append data to all_data dataframe
        all_data = pd.concat([all_data, table_data])
        all_data.dropna(axis=1, how='all', inplace=True)

    # clean all_data
    all_data = all_data.apply(lambda x: x.strip() if isinstance(x, str) else x)
    # get columns based in their index for renaming
    cols = list(all_data.columns)
    # Replace 'Occupancy %' with new calculated field
    all_data[cols[8]] = all_data[cols[7]] / all_data[cols[4]].replace(0, np.nan)
    # set dtypes
    all_data = all_data.astype({
        cols[0]: 'object',
        cols[1]: 'object',
        cols[2]: 'object',
        cols[3]: 'object',
        cols[4]: 'int64',
        cols[5]: 'float64',
        cols[6]: 'int64',
        cols[7]: 'int64',
        cols[8]: 'float64'})

    # rename columns using dictionary
    rename_dict = {
        cols[4]: 'Capacity',
        cols[5]: 'Capacity_100k',
        cols[6]: 'GP_Registered_Population',
        cols[7]: 'Occupancy',
        cols[8]: 'Occupancy_Percent'}

    all_data.rename(columns=rename_dict, inplace=True)
    all_data['Date'] = pd.to_datetime(all_data['Date'], format='%Y%m') + pd.offsets.MonthEnd(1)

    all_data.reset_index(drop=True, inplace=True)

    return all_data


def get_vw_dataset():
    vw_data = load_data()
    # clean whitespace data
    vw_data = vw_data.apply(lambda x: x.str.strip() if x.dtype == 'object' else x)

    # merge vw_data and icb location data using temp fields for case insensitivity
    ics_data = pd.read_csv(LOCATION_DATA_FILE)

    vw_data['temp_name'] = vw_data['Name'].str.lower()
    ics_data['temp_location'] = ics_data['ICB_Name'].str.lower()
    merged_df = pd.merge(left=vw_data, right=ics_data, left_on='temp_name', right_on='temp_location', how='left')

    # remove temporary columns and calculated columns that may be incorrect from final dataframe
    del merged_df['temp_name']
    del merged_df['temp_location']
    del merged_df['Capacity_100k']
    del merged_df['Occupancy_Percent']

    # group and aggregate fields
    merged_df = merged_df.groupby(['Date', 'ICB23CD']).agg({
        'Capacity': 'sum',
        'GP_Registered_Population': 'sum',
        'Occupancy': 'sum',
        'ICB23NM': 'first',
        'NHSER23NM': 'first',
    }).reset_index()

    # replace calculated fields
    merged_df['Capacity_100k'] = (
                merged_df['Capacity'] / merged_df['GP_Registered_Population'].replace(0, np.nan) * 100000).round(2)
    merged_df['Occupancy_Percent'] = (merged_df['Occupancy'] / merged_df['Capacity'].replace(0, np.nan) * 100).round(2)

    return merged_df


def convert_shape_to_json():
    shape_data = geopandas.read_file(SHAPEFILE)
    shape_data.to_crs(epsg=4326, inplace=True)
    shape_data.to_file(GEOJSON_OUTPUT, driver='GeoJSON')
    return GEOJSON_OUTPUT
